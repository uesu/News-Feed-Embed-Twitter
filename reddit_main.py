# ---------------------------------------------------------------------------
# 📋 Reddit Plain Embed V1 Edition — reddit_main.py
# ---------------------------------------------------------------------------
# To use it: change the workflow's run: python main.py
# line to run: reddit_main.py
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
# 📋 SUBREDDITS TO TRACK
# ---------------------------------------------------------------------------
SUBREDDITS_STR = os.getenv("SUBREDDITS", "Zenlesszonezeroleaks_")
SUBREDDITS = [s.strip() for s in SUBREDDITS_STR.split(",") if s.strip()]

DEFAULT_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

CACHE_FILE = "posted_reddit.json"
MAX_CACHE_SIZE = 500
MAX_AGE_SECONDS = 6 * 3600  # Reddit posts move slower than tweets; 6h window

REDDIT_RSS_INSTANCES = [
    "https://redlib.perennialte.ch",
    "https://old.reddit.com",
]

# ---------------------------------------------------------------------------
# 🔘 BUTTON CONFIGURATION
# ---------------------------------------------------------------------------
STATIC_BUTTONS = [
    {"label": "Citlali News", "url": "https://discord.gg/HyrVP9wRXu", "emoji": {"name": "📰"}},
    {"label": "Support", "url": "https://ko-fi.com/jieunlatte", "emoji": {"name": "☕"}},
]


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


async def fetch_working_reddit_feed(session: aiohttp.ClientSession, subreddit: str):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/rss+xml, application/xml, text/xml, */*"
    }
    for instance in REDDIT_RSS_INSTANCES:
        feed_url = f"{instance}/r/{subreddit}/new/.rss"
        try:
            async with session.get(feed_url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    content = await response.text()
                    feed = await asyncio.to_thread(feedparser.parse, content)
                    if feed.entries:
                        logging.info(f"Successfully fetched r/{subreddit} from {instance}")
                        return feed
        except Exception as e:
            logging.debug(f"Error fetching r/{subreddit} from {instance}: {e}")
    logging.warning(f"Could not fetch valid RSS feed for r/{subreddit} from any instance.")
    return None


def build_components(redditez_url: str, embeddit_url: str, vxreddit_url: str) -> list:
    buttons = [
        {"type": 2, "style": 5, "label": "Read Post", "url": redditez_url, "emoji": {"name": "🔗"}},
        {"type": 2, "style": 5, "label": "Embeddit", "url": embeddit_url, "emoji": {"name": "🎬"}},
        {"type": 2, "style": 5, "label": "vxReddit", "url": vxreddit_url, "emoji": {"name": "🔁"}},
    ]
    for btn in STATIC_BUTTONS:
        b = {"type": 2, "style": 5, "label": btn["label"], "url": btn["url"]}
        if btn.get("emoji"):
            b["emoji"] = btn["emoji"]
        buttons.append(b)
    return [{"type": 1, "components": buttons[:5]}]


async def send_discord_webhook(session: aiohttp.ClientSession, webhook_url: str, content: str,
                                 redditez_url: str, embeddit_url: str, vxreddit_url: str) -> bool:
    payload = {
        "content": content,
        "components": build_components(redditez_url, embeddit_url, vxreddit_url),
    }
    request_url = f"{webhook_url}?with_components=true"
    try:
        async with session.post(request_url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as response:
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

                published_parsed = entry.get("published_parsed") or entry.get("updated_parsed")
                published_ts = time.mktime(published_parsed) if published_parsed else now

                if not is_first_run and (now - published_ts > MAX_AGE_SECONDS):
                    continue

                subreddit_posts[subreddit].append({
                    "path": path,
                    "unique_key": unique_key,
                    "published_ts": published_ts,
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
                redditez_url = f"https://www.redditez.com{path}"
                embeddit_url = f"https://embeddit.deltandy.me{path}"
                vxreddit_url = f"https://vxreddit.com{path}"

                message = f"📰 **New post in r/{subreddit}**\n{redditez_url}"

                success = await send_discord_webhook(
                    session, webhook_url, message, redditez_url, embeddit_url, vxreddit_url
                )
                if success:
                    posted.add(post["unique_key"])
                    await asyncio.sleep(1.5)

    save_posted(posted)
    logging.info("Reddit RSS Monitor execution finished successfully.")


if __name__ == "__main__":
    asyncio.run(main())
