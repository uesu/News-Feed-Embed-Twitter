"""Offline smoke test — no network, no secrets.

Run:  python tests/test_smoke.py
Purpose (also used by CI as the safety gate for Dependabot PRs):
  1. every monitor script imports cleanly (catches import-time breakage
     from dependency bumps),
  2. the Reddit V3 card pipeline still behaves (body cleaning, media
     extraction/dedup, OP comment, components-v2 layout, button set).
"""
import os
import sys
import types
import importlib.util

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# In offline environments (no aiohttp/feedparser/dotenv installed) use stubs —
# this test never opens a connection, so stubs are safe.
try:
    import aiohttp  # noqa: F401
    import feedparser  # noqa: F401
    import dotenv  # noqa: F401
except ImportError:
    for name in ("aiohttp", "feedparser", "dotenv"):
        if name not in sys.modules:
            sys.modules[name] = types.ModuleType(name)
    sys.modules["aiohttp"].ClientSession = object
    sys.modules["aiohttp"].ClientTimeout = lambda total=None: None
    sys.modules["feedparser"].parse = lambda *a, **k: None
    sys.modules["dotenv"].load_dotenv = lambda *a, **k: None

failures = []


def check(label, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + label + (f"  {extra}" if extra and not cond else ""))
    if not cond:
        failures.append(label)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---- 1. every monitor script must import --------------------------------
SCRIPTS = [
    "main.py",
    "testing area/reddit_maintest.py",
    "testing area/reddit_main_v2test.py",
    "testing area/reddit_main_v3test.py",
    "testing area/main_v2testpro.py",
    "testing area/main_v2testproround10.py",
    "testing area/main_v3testpro.py",
    "testing area/main_v3testproround10.py",
    "testing area/video_diag.py",
]
v3 = None
for rel in SCRIPTS:
    try:
        m = load_module("smoke_" + rel.replace(os.sep, "_").replace(" ", "_"), rel)
        check(f"import {rel}", True)
        if rel.endswith("reddit_main_v3test.py"):
            v3 = m
    except Exception as e:
        check(f"import {rel}", False, repr(e))

if v3 is None:
    print("FATAL: reddit_main_v3test.py could not be imported.")
    sys.exit(1)

# ---- 2. body cleaning -----------------------------------------------------
html = ('<table><tr><td><p><a href="https://preview.redd.it/abc123.png?width=1280&s=x">'
        'https://preview.redd.it/abc123.png?width=1280&s=x</a></p>'
        '<p>Keep me</p></td></tr></table>\nsubmitted by /u/x to r/y')
body = v3.clean_rss_body(html)
check("body: redd.it URL line stripped", "preview.redd.it" not in body, body)
check("body: text kept", "Keep me" in body, body)

# ---- 3. native media extraction (order + dedup + best rendition) ----------
content = (
    '<a href="https://preview.redd.it/post-slug-v0-aaaa1111bbbb.jpg?width=140&crop=1:1,smart&auto=webp&s=1"><img></a> '
    '<a href="https://i.redd.it/aaaa1111bbbb.jpg"><img></a> '
    '<a href="https://preview.redd.it/post-slug-v0-cccc2222dddd.jpg?width=1080&crop=smart&auto=webp&s=2"><img></a> '
    '<a href="https://i.redd.it/eeee3333ffff.gif"><img></a> '
    '<a href="https://external-preview.redd.it/ext.png?width=640&s=3"><img></a>'
)
items = v3.extract_native_media(content)
check("media: 4 distinct items (deduped)", len(items) == 4, str(items))
check("media: photo1 full-res swap", items[0] == {"kind": "image", "url": "https://i.redd.it/aaaa1111bbbb.jpg"}, str(items[0]))
check("media: photo2 (signed jpg only) swapped to i.redd.it",
      items[1] == {"kind": "image", "url": "https://i.redd.it/cccc2222dddd.jpg"}, str(items[1]))
check("media: gif kind", items[2] == {"kind": "gif", "url": "https://i.redd.it/eeee3333ffff.gif"}, str(items[2]))
check("media: external-preview kept for caller", "external-preview" in items[3]["url"], str(items[3]))

# ---- 4. i_reddit_swap reduces slug-prefixed names to the bare file id ------
check("swap: bare id", v3.i_reddit_swap("https://preview.redd.it/yjexawtg9nph1.jpg?width=1280&s=x")
      == "https://i.redd.it/yjexawtg9nph1.jpg")
check("swap: slug -> bare id", v3.i_reddit_swap(
    "https://preview.redd.it/heist-mode-v0-8la7js0h9nph1.jpg?width=1080&s=x")
    == "https://i.redd.it/8la7js0h9nph1.jpg")
check("swap: png not swapped", v3.i_reddit_swap("https://preview.redd.it/xyz.png?width=1280&s=x") is None)

# ---- 4b. redlib gallery scoping ---------------------------------------------
redlib_page = """
<html><head><style>.post_title{font-size:20px}</style></head><body>
<header><img src="https://i.redd.it/subicon.jpg"></header>
<h1 class="post_title"><a href="/r/X/comments/abc/t/">Title</a></h1>
<div class="post_content">
  <img src="https://preview.redd.it/photo-a-v0-111aaa1.jpg?width=140&crop=1:1,smart&auto=webp&s=x">
  <img src="https://i.redd.it/222bbb2.jpg">
  <img src="https://preview.redd.it/photo-b-v0-333ccc3.jpg?width=1080&crop=smart&auto=webp&s=y">
  <img src="https://i.redd.it/444ddd4.gif">
</div>
<div id="comment-9"><img src="https://i.redd.it/commentside.jpg"></div>
<div class="sidebar"><img src="https://i.redd.it/sidebar.jpg"></div>
</body></html>
"""
g = v3.extract_redlib_gallery(redlib_page)
check("redlib: 4 items (sub icon + comment/sidebar imgs excluded)", len(g) == 4, str(g))
check("redlib: photo-a deduped to full-res", g[0] == {"kind": "image", "url": "https://i.redd.it/111aaa1.jpg"}, str(g[0]))
check("redlib: order kept (signed jpg/jpeg swapped to i.redd.it)",
      [x["url"] for x in g][:3]
      == ["https://i.redd.it/111aaa1.jpg", "https://i.redd.it/222bbb2.jpg",
          "https://i.redd.it/333ccc3.jpg"], str(g))
check("redlib: gif kind", g[3] == {"kind": "gif", "url": "https://i.redd.it/444ddd4.gif"}, str(g[3]))
check("redlib: empty page -> []", v3.extract_redlib_gallery("") == [])
check("redlib: bot-challenge page -> []", v3.extract_redlib_gallery("<html><h1>Please verify</h1></html>") == [])

# ---- 5. OP comment selection + card line ----------------------------------
pj = {"author": "OP", "permalink": "/r/Sub/comments/abc/title/"}
pj["_top_comments"] = [
    {"data": {"author": "other", "body": "nope"}},
    {"data": {"author": "OP", "body": "first"}},
    {"data": {"author": "OP", "body": "stickied!", "stickied": True, "id": "p9"}},
]
oc = v3.extract_op_comment(pj)
check("op: stickied wins", oc and oc["stickied"] and oc["text"] == "stickied!", str(oc))
check("op: permalink", oc and oc["permalink"] == "https://www.reddit.com/r/Sub/comments/abc/title/comment/p9/", str(oc))
check("op: none when absent", v3.extract_op_comment({"author": "A", "permalink": "/r/S/comments/x/",
                                                     "_top_comments": []}) is None)

# ---- 6. card layout ---------------------------------------------------------
data = {"title": "T", "author": "A", "body": "b" * 50,
        "media": [{"kind": "image", "url": f"https://i.redd.it/{i}.jpg"} for i in range(12)],
        "stats": {"comments": 3, "ups": 9}, "crosspost": None,
        "op_comment": {"text": "op note", "permalink": "https://pc", "stickied": True},
        "youtube_url": "https://youtube.com/shorts/ABCDEFGHI12", "full_mode": True}
p = v3.build_v3_payload("AnantaLeaks", data, "https://www.reddit.com/r/AnantaLeaks/comments/x/", 1)
check("layout: 2 containers for 12 media", len(p["components"]) == 2)
check("layout: flags", p["flags"] == 32768)
c2 = p["components"][1]
g2 = [c for c in c2["components"] if c.get("type") == 12]
check("layout: 2nd gallery has 2 items", len(g2) == 1 and len(g2[0]["items"]) == 2, str(len(g2)))
row = [c for c in c2["components"] if c.get("type") == 1][0]
labels = [b["label"] for b in row["components"]]
check("buttons: Read Post, YouTube, statics", labels == ["Read Post", "YouTube", "Citlali News", "Support"], str(labels))
yt = row["components"][1]
check("buttons: youtube uses starwardspark3",
      yt["emoji"] == {"id": "1483083423290490891", "name": "starwardspark3", "animated": True}, str(yt))
texts = [c["content"] for ct in p["components"] for c in ct["components"] if c.get("type") == 10]
check("op line in card", any("OP comment" in t for t in texts), str(texts))
total = sum(len(t) for t in texts)
check("char budget under 4000", total < 4000, str(total))

print()
if failures:
    print(f"SMOKE TEST FAILURES ({len(failures)}): {failures}")
    sys.exit(1)
print("SMOKE TEST: ALL PASS")
