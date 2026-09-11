# ---------------------------------------------------------------------------
# 📋 Components V2 Edition (Buttons Inside Container) — main_v3.py
# ---------------------------------------------------------------------------
# V3: Same as V2 but buttons are nested INSIDE the container component
# for a cleaner, unified card look.
# To use: change workflow's run line to: python main_v3.py
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
IS_COMPONENTS_V2 = 1 << 15

# ---------------------------------------------------------------------------
# 🌐 LANGUAGE NAMES (for the "Translated from X" header)
# ---------------------------------------------------------------------------
LANGUAGE_NAMES = {
    "ja": "Japanese", "ko": "Korean", "zh": "Chinese", "fr": "French",
    "de": "German", "es": "Spanish", "pt": "Portuguese", "ru": "Russian",
    "ar": "Arabic", "it": "Italian", "id": "Indonesian", "th": "Thai",
    "vi": "Vietnamese", "tl": "Filipino", "hi": "Hindi", "tr": "Turkish",
    "nl": "Dutch", "pl": "Polish", "uk": "Ukrainian", "sv": "Swedish",
}

# ---------------------------------------------------------------------------
# 🔘 BUTTON CONFIGURATION (NESTED INSIDE V2 CONTAINER)
# ---------------------------------------------------------------------------
READ_POST_LABEL = "Read Post"
READ_POST_EMOJI = {"name": "🔗"}

STATIC_BUTTONS = [
    {
        "label": "Citlali News",
        "url": "https://discord.gg/HyrVP9wRXu",
        "emoji": {"name": "📰"},
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
        logging.warning(f"No dedicated webhook for @{account}. Using DISCORD_WEBHOOK_URL fallback.")
        return DEFAULT_WEBHOOK_URL
    return None


def load_posted_urls() -> set:
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception as e:
            logging.error(f"Error reading cache file: {e}")
    return set()


def save_posted_urls(posted_urls: set):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(list(posted_urls)[-MAX_CACHE_SIZE:], f, indent=2)
    except Exception as e:
        logging.error(f"Error saving cache file: {e}")


async def fetch_working_feed(session: aiohttp.ClientSession, account: str):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/rss+xml, application/xml, text/xml, */*"
    }
    for instance in RSS_INSTANCES:
        feed_url = f"{instance}/{account}/rss"
        try:
            async with session.get(feed_url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    content = await response.text()
                    feed = await asyncio.to_thread(feedparser.parse, content)
                    title = str(feed.feed.get("title", ""))
                    if feed.entries and "whitelisted" not in title.lower():
                        logging.info(f"Successfully fetched feed for @{account} from {instance}")
                        return feed
        except Exception as e:
            logging.debug(f"Error fetching from {instance} for @{account}: {e}")
    logging.warning(f"Could not fetch valid RSS feed for @{account} from any instance.")
    return None


async def fetch_tweet_details(session: aiohttp.ClientSession, account: str, tweet_id: str,
                                lang_suffix: str = "") -> dict | None:
    url = f"{FXTWITTER_API_BASE}/{account}/status/{tweet_id}{lang_suffix}"
    headers = {"User-Agent": "NewsFlashBot/3.0"}
    try:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("tweet") or data.get("status")
            else:
                logging.error(f"FxTwitter API returned {response.status} for {tweet_id}{lang_suffix}")
    except Exception as e:
        logging.error(f"Error fetching FxTwitter data ({lang_suffix or 'original'}) for {tweet_id}: {e}")
    return None


def hex_color_to_int(hex_str, default: int = 1942002) -> int:
    """Safely parses a hex color string. Handles None, missing, or malformed values."""
    if not hex_str:
        return default
    try:
        return int(str(hex_str).lstrip("#"), 16)
    except (ValueError, TypeError):
        return default


def build_nested_action_row(read_post_url: str) -> dict:
    read_button = {"type": 2, "style": 5, "label": READ_POST_LABEL, "url": read_post_url, "emoji": READ_POST_EMOJI}
    buttons = [read_button]
    for btn in STATIC_BUTTONS:
        b = {"type": 2, "style": 5, "label": btn["label"], "url": btn["url"]}
        if btn.get("emoji"):
            b["emoji"] = btn["emoji"]
        buttons.append(b)
    return {"type": 1, "components": buttons[:5]}


def build_v3_payload(account: str, tweet: dict, read_post_url: str, display_text: str | None = None) -> dict:
    author = tweet.get("author", {})
    author_name = author.get("name", account)
    screen_name = author.get("screen_name", account)
    text = display_text if display_text is not None else tweet.get("text", "")

    media = tweet.get("media", {}) or {}
    media_items = []
    for v in media.get("videos", []) or []:
        if v.get("url"):
            media_items.append({"media": {"url": v["url"]}})
    for p in media.get("photos", []) or []:
        if p.get("url"):
            media_items.append({"media": {"url": p["url"]}})

    replies = tweet.get("replies", 0)
    retweets = tweet.get("retweets", 0)
    likes = tweet.get("likes", 0)
    views = tweet.get("views", "N/A")

    inner_components = [
        {"type": 10, "content": f"### [{author_name}](https://x.com/{screen_name}) just tweeted:"},
        {"type": 10, "content": text}
    ]

    if media_items:
        inner_components.append({"type": 14, "divider": True, "spacing": 1})
        inner_components.append({"type": 12, "items": media_items[:10]})

    inner_components.append({"type": 10, "content": f"-# 💬 {replies}  🔁 {retweets}  ❤️ {likes}  👁️ {views}"})
    inner_components.append({"type": 14, "divider": True, "spacing": 1})
    inner_components.append(build_nested_action_row(read_post_url))

    container = {
        "type": 17,
        "accent_color": hex_color_to_int(tweet.get("color")),
        "components": inner_components
    }

    return {"flags": IS_COMPONENTS_V2, "components": [container]}


async def main():
    if not ACCOUNTS:
        logging.error("No accounts configured in ACCOUNTS environment variable.")
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
                logging.error(f"No webhook configured for @{account}. Skipping.")
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
                published_ts = time.mktime(published_parsed) if published_parsed else now
                if not is_first_run and (now - published_ts > MAX_AGE_SECONDS):
                    logging.info(f"Skipping older tweet {unique_key} (published > 3h ago)")
                    continue

                tweet_data = await fetch_tweet_details(session, account, tweet_id)
                if not tweet_data:
                    logging.warning(f"Skipping {unique_key}: could not fetch FxTwitter API data.")
                    continue

                read_post_url = f"https://fxtwitter.com/{account}/status/{tweet_id}"
                display_text = None

                lang = (tweet_data.get("lang") or "").lower()
                if lang and lang != "en":
                    translated_data = await fetch_tweet_details(session, account, tweet_id, lang_suffix="/en")
                    if translated_data and translated_data.get("translation"):
                        translation = translated_data["translation"]
                        translated_text = translation.get("text", tweet_data.get("text", ""))
                        original_text = tweet_data.get("text", "")
                        lang_name = LANGUAGE_NAMES.get(lang, lang.upper())

                        display_text = (
                            f"📑 Translated from {lang_name}\n\n"
                            f"{translated_text}\n\n"
                            f"**Original text**\n{original_text}"
                        )
                        tweet_data = translated_data
                    read_post_url += "/en"

                payload = build_v3_payload(account, tweet_data, read_post_url, display_text=display_text)

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
    logging.info("V3 RSS Feed Monitor execution finished.")


if __name__ == "__main__":
    asyncio.run(main())
