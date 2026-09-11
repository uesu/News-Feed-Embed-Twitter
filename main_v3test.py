# ---------------------------------------------------------------------------
# ■ Components V2 Edition (Buttons Inside Container) — main_v3.py
# ---------------------------------------------------------------------------
# This is a separate file — your V1 main.py and V2 main_v2.py stay untouched.
# To use it: change the workflow's run line to:  python main_v3.py
#
# Same behavior as main_v2.py, but the action row (Read Post / Citlali News /
# Support) is NESTED INSIDE the type-17 container, giving the all-in-one-card
# look with the accent color wrapping the buttons too.
#
# ■ What's new in this revision:
#   • Hashtags and @mentions are clickable masked links (x.com/hashtag/...).
#   • SMART VIDEO HANDLING — Discord's Components V2 gallery can't play big
#     video files (verified live, 2026-09-11):
#         3840x2160 / 24 min / 905 MB  -> "image failed to load"
#         1920x1080 / 56 min / 578 MB  -> loads, won't play
#         2560x1440 /  5:12 / 405 MB   -> "image failed to load"
#         2560x1440 /  1:28 / 120 MB   -> plays fine
#         3440x1440 /  0:24 /  22 MB   -> plays fine
#         2340x1080 /  4:29 / 191 MB   -> plays fine
#     So the rule is FILE SIZE, not resolution. Each video's real size is
#     probed with an HTTP HEAD first (Content-Length); over VIDEO_SIZE_LIMIT
#     the script swaps in the biggest smaller mp4 from FxTwitter's formats[]
#     list that fits (so it still plays in Discord), and if nothing fits,
#     shows the video's thumbnail + a "Watch on X" link instead.
#     If the size can't be probed, the video is left untouched (never forced)
#     unless it is clearly risky (> 5 min AND >= 1080p) — then thumbnail+link.
#   • A Discord-format timestamp (🕐 <t:...:f>) on the stats line.
#   • Non-English tweets auto-translated via FxTwitter's /en suffix.
#   • Null-safe accent_color parsing (tweet color can be null).
# ---------------------------------------------------------------------------
import os
import re
import json
import time
import asyncio
import logging
import aiohttp
import feedparser
from email.utils import parsedate_to_datetime
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
load_dotenv()

ACCOUNTS_STR = os.getenv("ACCOUNTS", "TYPEII_EN,PomPom_HonkaiSR,Wuthering_Waves,HonkaiNA")
ACCOUNTS = [acc.strip() for acc in ACCOUNTS_STR.split(",") if acc.strip()]

DEFAULT_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

CACHE_FILE = "posted_tweets.json"
MAX_CACHE_SIZE = 500
MAX_AGE_SECONDS = 3 * 3600

RSS_INSTANCES = [
    "https://nitter.perennialte.ch",
    "https://nitter.privacydev.net",
    "https://nitter.net",
    "https://xcancel.com",
]

FXTWITTER_API_BASE = "https://api.fxtwitter.com"
IS_COMPONENTS_V2 = 1 << 15  # Flag for rich card layout

# ---------------------------------------------------------------------------
# ■ VIDEO GALLERY LIMITS (from live Discord tests, 2026-09-11 — see header)
# 191 MB confirmed plays, 405 MB confirmed fails -> 256 MiB sits safely
# between them. Tune here if Discord changes its behaviour.
# ---------------------------------------------------------------------------
VIDEO_SIZE_LIMIT = 256 * 1024 * 1024          # 256 MiB
RISKY_DURATION_SECONDS = 300                   # > 5 min ...
RISKY_MIN_PIXELS = 1920 * 1080                 # ... AND >= 1080p = risky when size unknown
MAX_VARIANT_PROBES = 3                         # smaller mp4s to try before giving up

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
}

# ---------------------------------------------------------------------------
# ■ LANGUAGE NAMES (for the "Translated from X" header)
# Add more ISO 639-1 codes here if you track accounts in other languages.
# ---------------------------------------------------------------------------
LANGUAGE_NAMES = {
    "ja": "Japanese", "ko": "Korean", "zh": "Chinese", "fr": "French",
    "de": "German", "es": "Spanish", "pt": "Portuguese", "ru": "Russian",
    "ar": "Arabic", "it": "Italian", "id": "Indonesian", "th": "Thai",
    "vi": "Vietnamese", "tl": "Filipino", "hi": "Hindi", "tr": "Turkish",
    "nl": "Dutch", "pl": "Polish", "uk": "Ukrainian", "sv": "Swedish",
}

# ---------------------------------------------------------------------------
# ■ BUTTON CONFIGURATION (NESTED INSIDE V2 CONTAINER)
# ---------------------------------------------------------------------------
READ_POST_LABEL = "Read Post"
READ_POST_EMOJI = {"name": "📖"}
STATIC_BUTTONS = [
    {
        "label": "Citlali News",
        "url": "https://discord.gg/HyrVP9wRXu",
        # TEST CUSTOM EMOJI: Replace with your actual emoji ID and Name
        "emoji": {
            "id": "1509026327548657914",
            "name": "starwardfans",
            "animated": True,
        },
    },
    {
        "label": "Support",
        "url": "https://ko-fi.com/jieunlatte",
        "emoji": {"name": "☕"},
    },
]


def get_webhook_for_account(account: str) -> str | None:
    sanitized = re.sub(r"[^A-Za-z0-9]", "_", account).upper()
    env_key = f"WEBHOOK_{sanitized}"
    webhook = os.getenv(env_key)
    if webhook:
        return webhook
    if DEFAULT_WEBHOOK_URL:
        return DEFAULT_WEBHOOK_URL
    return None


def load_posted_urls() -> set:
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()


def save_posted_urls(posted_urls: set):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(list(posted_urls)[-MAX_CACHE_SIZE:], f, indent=2)
    except Exception as e:
        logging.error(f"Error saving cache: {e}")


def accent_from_color(color) -> int:
    """Null-safe hex color -> int (tweet color can legitimately be null)."""
    try:
        if not color:
            return 0x1DA1F2
        return int(str(color).lstrip("#"), 16)
    except (ValueError, TypeError):
        return 0x1DA1F2


def linkify_text(text: str) -> str:
    """
    Makes #hashtags and @mentions clickable inside tweet text, exactly like
    FxTwitter's own auto-embeds do:
        #zzzero   -> [#zzzero](https://x.com/hashtag/zzzero)
        @user     -> [@user](https://x.com/user)
    Lookbehinds protect URLs (example.com/path#anchor) and emails (a@b.com).
    Bare http(s) links in the text are already auto-linked by Discord.
    """
    if not text:
        return ""
    text = re.sub(r"(?<![\w/])#(\w+)", r"[#\1](https://x.com/hashtag/\1)", text)
    text = re.sub(r"(?<![\w@/])@([A-Za-z0-9_]{1,15})", r"[@\1](https://x.com/\1)", text)
    return text


def resolve_tweet_ts(tweet: dict, fallback_ts: float) -> int:
    """Best-effort tweet creation time for the Discord <t:...> timestamp."""
    stamp = tweet.get("created_timestamp")
    if isinstance(stamp, (int, float)) and stamp > 0:
        return int(stamp)
    created_at = tweet.get("created_at")
    if created_at:
        try:
            return int(parsedate_to_datetime(str(created_at)).timestamp())
        except Exception:
            pass
    return int(fallback_ts)


# ---------------------------------------------------------------------------
# ■ SMART VIDEO HANDLING
# ---------------------------------------------------------------------------
def ranked_mp4_variants(video: dict) -> list:
    """FxTwitter's formats[] list, mp4s only, highest bitrate first."""
    formats = [f for f in (video.get("formats") or []) if isinstance(f, dict)]
    mp4s = [f for f in formats if f.get("container") == "mp4" and f.get("url")]
    mp4s.sort(key=lambda f: f.get("bitrate") or 0, reverse=True)
    return [f["url"] for f in mp4s]


def is_risky_unknown_video(video: dict) -> bool:
    """
    Used ONLY when the file size can't be probed: > 5 min AND >= 1080p is
    treated as risky (the verified failures were all long + high-res).
    """
    duration = video.get("duration") or 0
    pixels = (video.get("width") or 0) * (video.get("height") or 0)
    return duration > RISKY_DURATION_SECONDS and pixels >= RISKY_MIN_PIXELS


async def probe_video_size(session: aiohttp.ClientSession, url: str,
                           timeout: int = 8) -> int | None:
    """
    Returns the video's real byte size, or None if it can't be determined.
    HEAD request first (fast, no download); falls back to a 1-byte Range GET
    and parses Content-Range. Follows redirects so FxTwitter's proxy-wrapped
    /2/go?url= links resolve to the real file.
    """
    try:
        async with session.head(url, headers=BROWSER_HEADERS, allow_redirects=True,
                                timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
            cl = resp.headers.get("Content-Length")
            if cl and cl.isdigit() and int(cl) > 0:
                return int(cl)
    except Exception:
        pass
    try:
        headers = {**BROWSER_HEADERS, "Range": "bytes=0-0"}
        async with session.get(url, headers=headers, allow_redirects=True,
                               timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
            content_range = resp.headers.get("Content-Range")  # e.g. "bytes 0-0/949197256"
            if content_range and "/" in content_range:
                total = content_range.rsplit("/", 1)[1].strip()
                if total.isdigit() and int(total) > 0:
                    return int(total)
            cl = resp.headers.get("Content-Length")
            if cl and cl.isdigit() and int(cl) > 0:
                return int(cl)
    except Exception:
        pass
    return None


async def collect_media(session: aiohttp.ClientSession, tweet: dict) -> tuple[list, list]:
    """
    Returns (gallery_items, notes) for the card.

    Per video:
      • size <= VIDEO_SIZE_LIMIT            -> playable in the gallery, kept as-is
      • size >  limit, smaller variant fits -> gallery swaps in the smaller mp4 +
                                               a "showing smaller version" note
      • size >  limit, nothing fits         -> video's thumbnail in the gallery +
                                               a "watch on X" note
      • size unknown                        -> left untouched unless clearly risky
                                               (> 5 min AND >= 1080p), then thumbnail
    """
    gallery_items = []
    notes = []
    media = tweet.get("media", {}) or {}

    for v in media.get("videos", []) or []:
        video_url = v.get("url")
        if not video_url:
            continue
        size = await probe_video_size(session, video_url)

        if size is None:  # can't detect -> don't force a change (safe default)
            if is_risky_unknown_video(v):
                thumbnail = v.get("thumbnail_url")
                if thumbnail:
                    gallery_items.append({"media": {"url": thumbnail}})
                minutes = round((v.get("duration") or 0) / 60)
                notes.append(f"⚠️ Long high-res video (~{minutes} min) likely won't play in this "
                             f"card — [▶️ Watch it on X]({video_url})")
            else:
                gallery_items.append({"media": {"url": video_url}})
            continue

        if size <= VIDEO_SIZE_LIMIT:
            gallery_items.append({"media": {"url": video_url}})
            continue

        # --- too big for Discord's gallery ---
        mb = size / (1024 * 1024)
        swapped = False
        for variant_url in ranked_mp4_variants(v)[:MAX_VARIANT_PROBES]:
            if variant_url == video_url:
                continue
            variant_size = await probe_video_size(session, variant_url)
            if variant_size is not None and variant_size <= VIDEO_SIZE_LIMIT:
                vmb = variant_size / (1024 * 1024)
                gallery_items.append({"media": {"url": variant_url}})
                notes.append(f"🔽 Original video is ~{mb:.0f} MB — showing a smaller version "
                             f"(~{vmb:.0f} MB) so it plays in Discord. "
                             f"[▶️ Watch full quality on X]({video_url})")
                logging.info(f"Video downgraded: {mb:.0f}MB -> {vmb:.0f}MB variant")
                swapped = True
                break
        if not swapped:
            thumbnail = v.get("thumbnail_url")
            if thumbnail:
                gallery_items.append({"media": {"url": thumbnail}})
            notes.append(f"⚠️ Video is ~{mb:.0f} MB — too large for this card. "
                         f"[▶️ Watch it on X]({video_url})")

    for p in media.get("photos", []) or []:
        if p.get("url"):
            gallery_items.append({"media": {"url": p["url"]}})

    return gallery_items, notes


async def fetch_working_feed(session: aiohttp.ClientSession, account: str):
    headers = {"User-Agent": "Mozilla/5.0"}
    for instance in RSS_INSTANCES:
        feed_url = f"{instance}/{account}/rss"
        try:
            async with session.get(feed_url, headers=headers,
                                   timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    content = await response.text()
                    feed = await asyncio.to_thread(feedparser.parse, content)
                    if feed.entries:
                        return feed
        except Exception:
            continue
    return None


async def fetch_tweet_details(session: aiohttp.ClientSession, account: str, tweet_id: str,
                              lang_suffix: str = "") -> dict | None:
    """
    Fetches tweet data from FxTwitter's API.
    lang_suffix example: '/en' to request an English translation.
    """
    url = f"{FXTWITTER_API_BASE}/{account}/status/{tweet_id}{lang_suffix}"
    headers = {"User-Agent": "NewsFlashBot/3.0"}
    try:
        async with session.get(url, headers=headers,
                               timeout=aiohttp.ClientTimeout(total=10)) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("tweet") or data.get("status")
    except Exception as e:
        logging.error(f"Error fetching FxTwitter data ({lang_suffix or 'original'}) for {tweet_id}: {e}")
    return None


def build_nested_action_row(read_post_url: str) -> dict:
    """Creates the button components list to be placed INSIDE the container."""
    read_button = {
        "type": 2, "style": 5, "label": READ_POST_LABEL,
        "url": read_post_url, "emoji": READ_POST_EMOJI,
    }
    buttons = [read_button]
    for btn in STATIC_BUTTONS:
        b = {"type": 2, "style": 5, "label": btn["label"], "url": btn["url"]}
        if btn.get("emoji"):
            b["emoji"] = btn["emoji"]
        buttons.append(b)
    return {"type": 1, "components": buttons[:5]}


def build_v3_payload(account: str, tweet: dict, read_post_url: str,
                     display_text: str | None = None, posted_ts: int | None = None,
                     gallery_items: list | None = None, media_notes: list | None = None) -> dict:
    """Constructs the V3 layout with buttons nested inside the type 17 container."""
    author = tweet.get("author", {}) or {}
    author_name = author.get("name", account)
    screen_name = author.get("screen_name", account)

    raw_text = display_text if display_text is not None else tweet.get("text", "")
    text = linkify_text(raw_text)

    # gallery_items/media_notes come from collect_media (probed sizes); the naive
    # fallback below is only used when collect_media wasn't run (shouldn't happen in main()).
    if gallery_items is None:
        gallery_items, media_notes = [], []
        media = tweet.get("media", {}) or {}
        for v in media.get("videos", []) or []:
            if v.get("url"):
                gallery_items.append({"media": {"url": v["url"]}})
        for p in media.get("photos", []) or []:
            if p.get("url"):
                gallery_items.append({"media": {"url": p["url"]}})

    replies = tweet.get("replies", 0)
    retweets = tweet.get("retweets", 0)
    likes = tweet.get("likes", 0)
    views = tweet.get("views", "N/A")

    inner_components = [
        {"type": 10, "content": f"### [{author_name}](https://x.com/{screen_name}) just tweeted:"},
        {"type": 10, "content": text},
    ]
    if gallery_items:
        inner_components.append({"type": 14, "divider": True, "spacing": 1})
        inner_components.append({"type": 12, "items": gallery_items[:10]})
    for note in media_notes or []:
        inner_components.append({"type": 10, "content": note})
    ts_suffix = f"   •   🕐 <t:{posted_ts}:f>" if posted_ts else ""
    inner_components.append({
        "type": 10,
        "content": f"-# 💬 {replies} 🔁 {retweets} ❤️ {likes} 👁️ {views}{ts_suffix}",
    })

    # --- NESTED BUTTONS START HERE ---
    inner_components.append({"type": 14, "divider": True, "spacing": 1})
    inner_components.append(build_nested_action_row(read_post_url))

    container = {
        "type": 17,
        "accent_color": accent_from_color(tweet.get("color")),
        "components": inner_components,
    }
    return {"flags": IS_COMPONENTS_V2, "components": [container]}


async def main():
    if not ACCOUNTS:
        return
    posted_urls = load_posted_urls()
    is_first_run = len(posted_urls) == 0
    now = time.time()

    async with aiohttp.ClientSession() as session:
        feeds_tasks = [fetch_working_feed(session, acc) for acc in ACCOUNTS]
        feeds = await asyncio.gather(*feeds_tasks)

        for account, feed in zip(ACCOUNTS, feeds):
            if not feed or not feed.entries:
                continue
            webhook_url = get_webhook_for_account(account)
            if not webhook_url:
                continue
            entries = [feed.entries[0]] if is_first_run else feed.entries
            for entry in entries:
                match = re.search(r"/status/(\d+)", getattr(entry, "link", ""))
                if not match:
                    continue
                tweet_id = match.group(1)
                unique_key = f"{account}_{tweet_id}"
                if unique_key in posted_urls:
                    continue

                published_parsed = entry.get("published_parsed")
                rss_ts = time.mktime(published_parsed) if published_parsed else now

                tweet_data = await fetch_tweet_details(session, account, tweet_id)
                if not tweet_data:
                    continue

                read_post_url = f"https://fxtwitter.com/{account}/status/{tweet_id}"
                display_text = None

                # --- auto-translation for non-English tweets ---
                lang = (tweet_data.get("lang") or "").lower()
                if lang and lang != "en":
                    translated_data = await fetch_tweet_details(session, account, tweet_id,
                                                                lang_suffix="/en")
                    if translated_data and translated_data.get("translation"):
                        translation = translated_data["translation"]
                        translated_text = translation.get("text", tweet_data.get("text", ""))
                        original_text = tweet_data.get("text", "")
                        lang_name = LANGUAGE_NAMES.get(lang, lang.upper())
                        display_text = (
                            f"🌐 Translated from {lang_name}\n\n"
                            f"{translated_text}\n\n"
                            f"**Original text**\n{original_text}"
                        )
                        # Use translated payload as the base (media/stats should match)
                        tweet_data = translated_data
                        read_post_url += "/en"
                # ------------------------------------------------

                # --- probe video sizes and build the gallery ---
                gallery_items, media_notes = await collect_media(session, tweet_data)

                posted_ts = resolve_tweet_ts(tweet_data, rss_ts)
                payload = build_v3_payload(account, tweet_data, read_post_url,
                                           display_text=display_text, posted_ts=posted_ts,
                                           gallery_items=gallery_items, media_notes=media_notes)
                target_url = f"{webhook_url}?with_components=true"
                async with session.post(target_url, json=payload) as resp:
                    if resp.status in (200, 204):
                        posted_urls.add(unique_key)
                        logging.info(f"V3 Posted: {unique_key} (lang={lang or 'en'})")
                        await asyncio.sleep(1.5)
                    else:
                        body = await resp.text()
                        logging.error(f"Discord error {resp.status} for {unique_key}: {body}")

    save_posted_urls(posted_urls)
    logging.info("Twitter V3 Monitor execution finished.")


if __name__ == "__main__":
    asyncio.run(main())
