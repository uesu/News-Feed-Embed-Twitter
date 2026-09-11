# ---------------------------------------------------------------------------
# ■ Reddit RSS Feed Monitor — V1 (plain content + auto-embed via redditez)
# ---------------------------------------------------------------------------
# Monitors subreddits via RSS and posts the redditez.com mirror link, letting
# Discord auto-unfurl it into a rich embed (same idea as fxtwitter for X).
#
# No API key required. 100% free.
#
# Features:
#   • Read Post button -> the ORIGINAL reddit.com permalink
#   • YouTube detection -> bare YouTube URL on its own line (auto-embeds a
#     playable video in Discord) + an optional "YouTube" link button
#   • Mod-queue safe -> approved posts resurface via the RSS "updated" stamp,
#     with a 48-hour catch window (see MAX_AGE_SECONDS below)
#
# To use the rich Components V2 version instead (requires an EmbedEZ API key),
# change the workflow run line to: python reddit_main_v2.py
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

# ---------------------------------------------------------------------------
# ■ SUBREDDITS TO TRACK
# ---------------------------------------------------------------------------
SUBREDDITS_STR = os.getenv("SUBREDDITS", "Zenlesszonezeroleaks_")
SUBREDDITS = [s.strip() for s in SUBREDDITS_STR.split(",") if s.strip()]

# Optional fallback webhook used only if a subreddit has no dedicated secret
DEFAULT_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

CACHE_FILE = "posted_reddit.json"
MAX_CACHE_SIZE = 500

# How old a post's latest activity may be before we skip it.
# Kept WIDE (48h) on purpose: subreddits with moderator approval queues can
# surface a post a day or more after submission. When a queued post gets
# approved, Reddit bumps its RSS "updated" timestamp — we use that (see
# activity_ts below), so newly-approved posts are still caught and never
# left out. If you track very slow subreddits, you can widen this further.
MAX_AGE_SECONDS = 48 * 3600

# ---------------------------------------------------------------------------
# ■ RSS SOURCES (tried in order)
#
#   • www.reddit.com  -> native Reddit RSS; works and returns real Atom feeds.
#   • old.reddit.com  -> often returns an HTML "Welcome to Reddit" interstitial
#                        to datacenter IPs (0 entries) — fallback only.
#   • redlib.*        -> frequently behind a Cloudflare challenge (403) —
#                        fallback only.
# The script validates that the response actually CONTAINS reddit permalinks
# before accepting it, and logs why each source was skipped.
# ---------------------------------------------------------------------------
REDDIT_RSS_INSTANCES = [
    "https://www.reddit.com",
    "https://old.reddit.com",
    "https://redlib.perennialte.ch",
]

# ---------------------------------------------------------------------------
# ■ BUTTON CONFIGURATION — customize labels, URLs, and emojis here
# Discord button "style" 5 = Link button (MUST use "url", no "custom_id")
# Unicode emoji: {"name": "🔔"} | Custom emoji: {"id": "123", "name": "x", "animated": False}
# Note: click-to-rotate embed mirrors are NOT possible with plain webhooks
# (that needs a 24/7 bot answering Discord interactions), so the buttons are
# fixed link buttons only — Reddit-side mirrors were removed by request.
# ---------------------------------------------------------------------------
STATIC_BUTTONS = [
    {"label": "Citlali News", "url": "https://discord.gg/HyrVP9wRXu", "emoji": {"name": "✨"}},
    {"label": "Support", "url": "https://ko-fi.com/jieunlatte", "emoji": {"name": "☕"}},
]

# Matches watch / shorts / youtu.be links inside the RSS entry HTML
YOUTUBE_RE = re.compile(
    r"https?://(?:www\.)?(?:youtube\.com/(?:watch\?[^\s\"'<>)\]]+|shorts/[^\s\"'<>)\]]+)"
    r"|youtu\.be/[^\s\"'<>)\]]+)",
    re.IGNORECASE,
)


def get_webhook_for_subreddit(subreddit: str) -> str | None:
    sanitized = re.sub(r"[^A-Za-z0-9]", "_", subreddit).upper()
    env_key = f"WEBHOOK_REDDIT_{sanitized}"
    webhook = os.getenv(env_key)
    if webhook:
        return webhook
    if DEFAULT_WEBHOOK_URL:
        logging.warning(f"No dedicated webhook for r/{subreddit} (expected {env_key}). Using fallback.")
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
    """Extracts the /r/subreddit/comments/.../ path regardless of source domain."""
    match = re.search(r"(/r/[^\s?]+)", link)
    return match.group(1).rstrip("/") + "/" if match else None


def extract_post_id(path: str) -> str | None:
    match = re.search(r"/comments/([a-zA-Z0-9]+)/", path)
    return match.group(1) if match else None


def extract_youtube_url(entry) -> str | None:
    """Finds a YouTube link (watch / shorts / youtu.be) in the RSS entry HTML."""
    html_parts = []
    if entry.get("content"):
        html_parts.extend(c.get("value", "") for c in entry.content)
    if entry.get("summary"):
        html_parts.append(entry.summary)
    for html in html_parts:
        match = YOUTUBE_RE.search(html or "")
        if match:
            return match.group(0)
    return None


async def fetch_working_reddit_feed(session: aiohttp.ClientSession, subreddit: str):
    """
    Tries each RSS source in order. A source is only accepted if:
      1. HTTP 200,
      2. feedparser finds entries,
      3. the first entries actually contain reddit /comments/ permalinks
         (rejects HTML interstitial/block pages that return 200 with junk).
    Every rejection is logged so Actions logs show exactly why a source failed.
    """
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


def build_components(reddit_url: str, youtube_url: str | None = None) -> list:
    """Read Post (original reddit URL) [+ YouTube if detected] + static buttons (max 5/row)."""
    buttons = [
        {"type": 2, "style": 5, "label": "Read Post", "url": reddit_url, "emoji": {"name": "📖"}},
    ]
    if youtube_url:
        buttons.append({"type": 2, "style": 5, "label": "YouTube", "url": youtube_url,
                        "emoji": {"name": "▶️"}})
    for btn in STATIC_BUTTONS:
        b = {"type": 2, "style": 5, "label": btn["label"], "url": btn["url"]}
        if btn.get("emoji"):
            b["emoji"] = btn["emoji"]
        buttons.append(b)
    return [{"type": 1, "components": buttons[:5]}]


async def send_discord_webhook(session: aiohttp.ClientSession, webhook_url: str, content: str,
                               reddit_url: str, youtube_url: str | None = None) -> bool:
    payload = {
        "content": content,
        "components": build_components(reddit_url, youtube_url),
    }
    # Discord requires this query param or components are silently dropped
    request_url = f"{webhook_url}?with_components=true"
    try:
        async with session.post(request_url, json=payload,
                                timeout=aiohttp.ClientTimeout(total=10)) as response:
            if response.status in (200, 204):
                logging.info("Successfully posted to Discord Webhook.")
                return True
            body = await response.text()
            logging.error(f"Discord Webhook returned status {response.status}: {body}")
            return False
    except Exception as e:
        logging.error(f"Error posting to Discord Webhook: {e}")
        return False


async def main():
    if not SUBREDDITS:
        logging.error("No subreddits configured in SUBREDDITS environment variable.")
        return

    posted = load_posted()
    is_first_run = len(posted) == 0
    now = time.time()
    subreddit_posts = {sub: [] for sub in SUBREDDITS}

    async with aiohttp.ClientSession() as session:
        tasks = [fetch_working_reddit_feed(session, sub) for sub in SUBREDDITS]
        feeds = await asyncio.gather(*tasks)

        for subreddit, feed in zip(SUBREDDITS, feeds):
            if not feed or not feed.entries:
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

                # --- mod-queue safe age check ---------------------------------
                # Pending posts can be APPROVED hours/days later; Reddit bumps
                # the entry's "updated" stamp on approval, so we age-check the
                # most RECENT of (published, updated) instead of publish time.
                published_parsed = entry.get("published_parsed")
                updated_parsed = entry.get("updated_parsed")
                published_ts = time.mktime(published_parsed) if published_parsed else now
                updated_ts = time.mktime(updated_parsed) if updated_parsed else published_ts
                activity_ts = max(published_ts, updated_ts)
                if not is_first_run and (now - activity_ts > MAX_AGE_SECONDS):
                    continue
                # --------------------------------------------------------------

                subreddit_posts[subreddit].append({
                    "path": path,
                    "unique_key": unique_key,
                    "published_ts": published_ts,
                    "youtube_url": extract_youtube_url(entry),
                    "title": getattr(entry, "title", "New post"),
                })

        total_found = sum(len(v) for v in subreddit_posts.values())
        if total_found == 0:
            logging.info("No new Reddit posts to post.")
            save_posted(posted)
            return

        logging.info(f"Found {total_found} new Reddit posts. Posting per-channel...")

        for subreddit, posts in subreddit_posts.items():
            if not posts:
                continue
            webhook_url = get_webhook_for_subreddit(subreddit)
            if not webhook_url:
                logging.error(f"No webhook configured for r/{subreddit}. Skipping.")
                continue
            posts.sort(key=lambda p: p["published_ts"])
            for post in posts:
                path = post["path"]
                reddit_url = f"https://www.reddit.com{path}"        # original permalink
                redditez_url = f"https://www.redditez.com{path}"    # rich auto-embed mirror
                youtube_url = post["youtube_url"]

                # Header + masked redditez link (auto-embeds) + bare YouTube URL
                # on its own line so Discord also unfurls a playable YT player.
                lines = [f"🔔 **New post in r/{subreddit}**", redditez_url]
                if youtube_url:
                    lines.append(youtube_url)
                message = "\n".join(lines)

                success = await send_discord_webhook(
                    session, webhook_url, message, reddit_url, youtube_url
                )
                if success:
                    posted.add(post["unique_key"])
                    await asyncio.sleep(1.5)

    save_posted(posted)
    logging.info("Reddit RSS Monitor execution finished successfully.")


if __name__ == "__main__":
    asyncio.run(main())
