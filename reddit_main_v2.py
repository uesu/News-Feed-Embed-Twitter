# ---------------------------------------------------------------------------
# ■ Reddit RSS Feed Monitor — V2 (Components V2 rich card via EmbedEZ API)
# ---------------------------------------------------------------------------
# Same monitoring as reddit_main.py (V1), but each post is rendered as a
# Discord Components V2 card (type 17 container, media gallery, stats, buttons
# nested inside) using data from the EmbedEZ API.
#
# ■ EmbedEZ API (documented two-step flow, per https://embedez.com/docs):
#     1. GET /api/v1/providers/search?url=<post url>          -> returns a key
#     2. GET /api/v1/providers/preview?search_key=<key>       -> post data
#        (send header  Authorization: Bearer <EMBEDEZ_API_KEY> for full data)
#
# ■ IMPORTANT CONCERNS (please read):
#   1. API KEY / CREDITS — the EmbedEZ API key is NOT fully free. The dashboard
#      shows a credit balance (e.g. 100 credits); heavier use requires payment.
#      Every new post costs 2 API calls (search + preview). Watch your balance.
#      If you don't want to pay, use reddit_main.py (V1) instead — no key needed.
#   2. WITHOUT a valid key, the preview endpoint still returns PUBLIC data
#      (author + title + thumbnail). This script detects that and posts a
#      limited card instead of skipping the post.
#   3. EmbedEZ officially warns that "large changes will be made to the API in
#      the future, and these might break the current API". Field names are
#      parsed defensively below (media url OR media.source.url), but if the API
#      changes shape again, check the Actions logs and adjust the getters.
#   4. The old unofficial "/providers/combined?q=" endpoint from early docs is
#      no longer documented — this script uses only the documented endpoints.
# ---------------------------------------------------------------------------
import os
import re
import json
import time
import asyncio
import logging
import aiohttp
import feedparser
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
load_dotenv()

SUBREDDITS_STR = os.getenv("SUBREDDITS", "Zenlesszonezeroleaks_")
SUBREDDITS = [s.strip() for s in SUBREDDITS_STR.split(",") if s.strip()]

DEFAULT_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
EMBEDEZ_API_KEY = os.getenv("EMBEDEZ_API_KEY")

CACHE_FILE = "posted_reddit.json"
MAX_CACHE_SIZE = 500
MAX_AGE_SECONDS = 6 * 3600

REDDIT_RSS_INSTANCES = [
    "https://www.reddit.com",
    "https://old.reddit.com",
    "https://redlib.perennialte.ch",
]

EMBEDEZ_SEARCH_URL = "https://embedez.com/api/v1/providers/search"
EMBEDEZ_PREVIEW_URL = "https://embedez.com/api/v1/providers/preview"
EMBEDEZ_BASE = "https://embedez.com"

IS_COMPONENTS_V2 = 1 << 15

STATIC_BUTTONS = [
    {"label": "Citlali News", "url": "https://discord.gg/HyrVP9wRXu", "emoji": {"name": "✨"}},
    {"label": "Support", "url": "https://ko-fi.com/jieunlatte", "emoji": {"name": "☕"}},
]


def get_webhook_for_subreddit(subreddit: str) -> str | None:
    sanitized = re.sub(r"[^A-Za-z0-9]", "_", subreddit).upper()
    env_key = f"WEBHOOK_REDDIT_{sanitized}"
    webhook = os.getenv(env_key)
    if webhook:
        return webhook
    if DEFAULT_WEBHOOK_URL:
        return DEFAULT_WEBHOOK_URL
    return None


def load_posted() -> set:
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception as e:
            logging.error(f"Error reading cache: {e}")
    return set()


def save_posted(posted: set):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(list(posted)[-MAX_CACHE_SIZE:], f, indent=2)
    except Exception as e:
        logging.error(f"Error saving cache: {e}")


def normalize_reddit_path(link: str) -> str | None:
    match = re.search(r"(/r/[^\s?]+)", link)
    return match.group(1).rstrip("/") + "/" if match else None


def extract_post_id(path: str) -> str | None:
    match = re.search(r"/comments/([a-zA-Z0-9]+)/", path)
    return match.group(1) if match else None


def strip_html(value: str | None) -> str:
    """Removes tags (<a>, <br>...) from EmbedEZ's HTML-ish preview title."""
    if not value:
        return ""
    value = re.sub(r"(?i)<br\s*/?>", " ", value)
    value = re.sub(r"<[^>]+>", "", value)
    return re.sub(r"\s{2,}", " ", value).strip()


async def fetch_working_reddit_feed(session: aiohttp.ClientSession, subreddit: str):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
    }
    for instance in REDDIT_RSS_INSTANCES:
        feed_url = f"{instance}/r/{subreddit}/new/.rss"
        try:
            async with session.get(feed_url, headers=headers,
                                   timeout=aiohttp.ClientTimeout(total=15)) as response:
                if response.status != 200:
                    logging.info(f"[{instance}] HTTP {response.status} for r/{subreddit} — trying next source.")
                    continue
                content = await response.text()
                feed = await asyncio.to_thread(feedparser.parse, content)
                if not feed.entries:
                    logging.info(f"[{instance}] returned no RSS entries for r/{subreddit} "
                                 f"(HTML block/interstitial page?) — trying next source.")
                    continue
                if not any("/comments/" in str(getattr(e, "link", "")) for e in feed.entries[:5]):
                    logging.info(f"[{instance}] feed for r/{subreddit} contains no reddit post links — "
                                 f"trying next source.")
                    continue
                logging.info(f"Successfully fetched r/{subreddit} from {instance}")
                return feed
        except Exception as e:
            logging.info(f"[{instance}] error for r/{subreddit}: {e} — trying next source.")
    logging.warning(f"Could not fetch valid RSS feed for r/{subreddit} from any instance.")
    return None


async def fetch_embedez_data(session: aiohttp.ClientSession, reddit_url: str) -> dict | None:
    """
    Documented two-step EmbedEZ flow:
      step 1: /providers/search?url=...    -> data.key
      step 2: /providers/preview?search_key=... (+ Authorization: Bearer <key>)
    Returns the preview `data` dict, or None on hard failure.
    Note: without a valid API key the response still succeeds but only contains
    public fields (type / user / preview) — no `content`/`media`/`statistics`.
    """
    headers = {}
    if EMBEDEZ_API_KEY:
        headers["Authorization"] = f"Bearer {EMBEDEZ_API_KEY}"
    else:
        logging.info("EMBEDEZ_API_KEY not set — falling back to public (limited) preview data.")

    browser_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    }
    try:
        # — step 1: search for a key —
        async with session.get(EMBEDEZ_SEARCH_URL, headers={**browser_headers, **headers},
                               params={"url": reddit_url},
                               timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                logging.error(f"EmbedEZ search returned {resp.status}: {await resp.text()}")
                return None
            search = await resp.json()
        if not search.get("success"):
            logging.error(f"EmbedEZ search error: {search.get('message')}")
            return None
        key = (search.get("data") or {}).get("key")
        if not key:
            logging.error("EmbedEZ search returned no key.")
            return None

        # — step 2: preview with the key —
        async with session.get(EMBEDEZ_PREVIEW_URL, headers={**browser_headers, **headers},
                               params={"search_key": key},
                               timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                logging.error(f"EmbedEZ preview returned {resp.status}: {await resp.text()}")
                return None
            preview = await resp.json()
        if not preview.get("success"):
            logging.error(f"EmbedEZ preview error: {preview.get('message')}")
            return None
        return preview.get("data") or {}
    except Exception as e:
        logging.error(f"Error calling EmbedEZ API for {reddit_url}: {e}")
        return None


def extract_media_urls(data: dict) -> list:
    """
    Pulls media URLs defensively from the EmbedEZ payload:
      • full (authorized) data: content.media[].url            (current docs)
      • legacy combined shape:  content.media[].source.url     (early docs)
      • public (no-key) data:   preview.img.url / preview.img (str)
    """
    urls = []
    content = data.get("content") or {}
    for m in (content.get("media") or []):
        if not isinstance(m, dict):
            continue
        u = m.get("url")
        if not u and isinstance(m.get("source"), dict):
            u = m["source"].get("url")
        if isinstance(u, dict):  # some payloads nest {url: {url: ...}}
            u = u.get("url")
        if u:
            urls.append(u)
    if urls:
        return urls
    img = (data.get("preview") or {}).get("img")
    if isinstance(img, dict):
        img = img.get("url")
    if isinstance(img, str) and img:
        urls.append(img)
    return urls


def build_nested_action_row(redditez_url: str, embeddit_url: str, vxreddit_url: str) -> dict:
    buttons = [
        {"type": 2, "style": 5, "label": "Read Post", "url": redditez_url, "emoji": {"name": "📖"}},
        {"type": 2, "style": 5, "label": "Embeddit", "url": embeddit_url, "emoji": {"name": "🧩"}},
        {"type": 2, "style": 5, "label": "vxReddit", "url": vxreddit_url, "emoji": {"name": "🛰️"}},
    ]
    for btn in STATIC_BUTTONS:
        b = {"type": 2, "style": 5, "label": btn["label"], "url": btn["url"]}
        if btn.get("emoji"):
            b["emoji"] = btn["emoji"]
        buttons.append(b)
    return {"type": 1, "components": buttons[:5]}


def build_v2_payload(subreddit: str, data: dict, redditez_url: str,
                     embeddit_url: str, vxreddit_url: str) -> dict:
    content = data.get("content") or {}
    user = data.get("user") or {}
    preview = data.get("preview") or {}
    limited = not bool(content)  # True when no (valid) API key -> public data only

    # — text fields (full data first, then public-preview fallbacks) —
    title = content.get("title") or strip_html(preview.get("title")) or f"New post in r/{subreddit}"
    description = content.get("description") or content.get("text") or strip_html(preview.get("description"))
    author_name = user.get("displayName") or user.get("name") or f"r/{subreddit}"
    link = redditez_url

    inner_components = [
        {"type": 10, "content": f"### [{title}]({link})\n*by {author_name} in r/{subreddit}*"},
    ]
    if description:
        inner_components.append({"type": 10, "content": description})

    # — media gallery —
    media_urls = extract_media_urls(data)
    if media_urls:
        items = [{"media": {"url": u}} for u in media_urls[:10]]
        inner_components.append({"type": 14, "divider": True, "spacing": 1})
        inner_components.append({"type": 12, "items": items})

    # — stats line (full data only) or a small "limited preview" note —
    if limited:
        inner_components.append({
            "type": 10,
            "content": "-# ℹ️ Limited preview — set a valid EMBEDEZ_API_KEY for full stats & media",
        })
    else:
        stats = content.get("statistics") or {}
        comments = stats.get("comments", 0)
        shares = stats.get("shares", 0)
        likes = stats.get("likes", 0)
        views = stats.get("views", "N/A")
        inner_components.append({
            "type": 10,
            "content": f"-# 💬 {comments} 🔁 {shares} ❤️ {likes} 👁️ {views}",
        })

    inner_components.append({"type": 14, "divider": True, "spacing": 1})
    inner_components.append(build_nested_action_row(redditez_url, embeddit_url, vxreddit_url))

    container = {
        "type": 17,
        "accent_color": 16729344,  # 0xFF4500 — Reddit orange
        "components": inner_components,
    }
    return {"flags": IS_COMPONENTS_V2, "components": [container]}


async def main():
    if not SUBREDDITS:
        logging.error("No subreddits configured in SUBREDDITS environment variable.")
        return
    if not EMBEDEZ_API_KEY:
        logging.warning("EMBEDEZ_API_KEY is missing — cards will use limited public preview data. "
                        "For full media/stats, add the EMBEDEZ_API_KEY secret (watch your credit balance), "
                        "or switch the workflow to reddit_main.py (V1, free, no key).")

    posted = load_posted()
    is_first_run = len(posted) == 0
    now = time.time()

    async with aiohttp.ClientSession() as session:
        tasks = [fetch_working_reddit_feed(session, sub) for sub in SUBREDDITS]
        feeds = await asyncio.gather(*tasks)

        for subreddit, feed in zip(SUBREDDITS, feeds):
            if not feed or not feed.entries:
                continue
            webhook_url = get_webhook_for_subreddit(subreddit)
            if not webhook_url:
                logging.error(f"No webhook configured for r/{subreddit}. Skipping.")
                continue
            entries = [feed.entries[0]] if is_first_run else feed.entries
            for entry in entries:
                raw_link = getattr(entry, "link", "")
                path = normalize_reddit_path(raw_link)
                if not path:
                    continue
                post_id = extract_post_id(path)
                if not post_id:
                    continue
                unique_key = f"{subreddit}_{post_id}"
                if unique_key in posted:
                    continue
                published_parsed = entry.get("published_parsed") or entry.get("updated_parsed")
                published_ts = time.mktime(published_parsed) if published_parsed else now
                if not is_first_run and (now - published_ts > MAX_AGE_SECONDS):
                    continue

                redditez_url = f"https://www.redditez.com{path}"
                embeddit_url = f"https://embeddit.deltandy.me{path}"
                vxreddit_url = f"https://vxreddit.com{path}"

                reddit_url = f"https://www.reddit.com{path}"
                embedez_data = await fetch_embedez_data(session, reddit_url)
                if embedez_data is None:
                    logging.warning(f"Skipping {unique_key}: could not fetch EmbedEZ data.")
                    continue

                payload = build_v2_payload(subreddit, embedez_data, redditez_url, embeddit_url, vxreddit_url)
                target_url = f"{webhook_url}?with_components=true"
                async with session.post(target_url, json=payload) as resp:
                    if resp.status in (200, 204):
                        posted.add(unique_key)
                        logging.info(f"Reddit V2 Posted: {unique_key}")
                        await asyncio.sleep(1.5)
                    else:
                        body = await resp.text()
                        logging.error(f"Discord error {resp.status} for {unique_key}: {body}")

    save_posted(posted)
    logging.info("Reddit V2 Monitor execution finished.")


if __name__ == "__main__":
    asyncio.run(main())
