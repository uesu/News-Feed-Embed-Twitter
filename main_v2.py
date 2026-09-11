---------------------------------------------------------------------------
📋 Components V2 Edition (Buttons Outside Container) — main_v2.py
---------------------------------------------------------------------------
This is a separate file — your V1 main.py stays untouched
To use it: change the workflow's run: python main.py
line to run: main_v2.py
Note: buttons are outside the component v2
---------------------------------------------------------------------------
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
IS_COMPONENTS_V2 = 1 << 15 # Discord message flag required for Components V2

---------------------------------------------------------------------------
🔘 BUTTON CONFIGURATION
---------------------------------------------------------------------------
READ_POST_LABEL = "Read Post"
READ_POST_EMOJI = {"name": "🔗"}

STATIC_BUTTONS = [
{"label": "Citlali News", "url": "https://discord.gg/HyrVP9wRXu", "emoji": {"name": "📰"}},
{"label": "Support", "url": "https://ko-fi.com/jieunlatte", "emoji": {"name": "☕"}},
]

def get_webhook_for_account(account: str) -> str | None:
sanitized = re.sub(r"[^A-Za-z0-9]", "", account).upper()
env_key = f"WEBHOOK{sanitized}"
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
"Accept": "application/rss+xml, application/xml, text/xml, /"
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
return feed
except Exception as e:
logging.debug(f"Error fetching from {instance} for @{account}: {e}")
logging.warning(f"Could not fetch valid RSS feed for @{account} from any instance.")
return None

async def fetch_tweet_details(session: aiohttp.ClientSession, account: str, tweet_id: str) -> dict | None:
"""Fetches rich tweet data (text, media, stats) from the FxTwitter API."""
url = f"{FXTWITTER_API_BASE}/{account}/status/{tweet_id}"
headers = {"User-Agent": "NewsFlashBot/2.0"} # FxTwitter requires a User-Agent header
try:
async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
if response.status != 200:
logging.error(f"FxTwitter API returned {response.status} for {tweet_id}")
return None
data = await response.json()
# API nests the tweet under "tweet" (current schema)
return data.get("tweet") or data.get("status")
except Exception as e:
logging.error(f"Error fetching FxTwitter API data for {tweet_id}: {e}")
return None

def hex_color_to_int(hex_str: str | None, default: int = 1942002) -> int:
if not hex_str:
return default
try:
return int(hex_str.lstrip("#"), 16)
except Exception:
return default

def build_action_row(read_post_url: str) -> dict:
read_button = {"type": 2, "style": 5, "label": READ_POST_LABEL, "url": read_post_url}
if READ_POST_EMOJI:
read_button["emoji"] = READ_POST_EMOJI

text

buttons = [read_button]
for btn in STATIC_BUTTONS:
    b = {"type": 2, "style": 5, "label": btn["label"], "url": btn["url"]}
    if btn.get("emoji"):
        b["emoji"] = btn["emoji"]
    buttons.append(b)

return {"type": 1, "components": buttons[:5]}
def build_v2_container(account: str, tweet: dict, read_post_url: str) -> dict:
author = tweet.get("author", {})
author_name = author.get("name", account)
screen_name = author.get("screen_name", account)
text = tweet.get("text", "")

text

media = tweet.get("media") or {}
photos = media.get("photos") or []
videos = media.get("videos") or []

replies = tweet.get("replies", 0)
retweets = tweet.get("retweets", 0)
likes = tweet.get("likes", 0)
views = tweet.get("views", "N/A")

container_components = [
    {"type": 10, "content": f"### [{author_name}](https://x.com/{screen_name}) just tweeted:"},
    {"type": 10, "content": text},
]

media_items = []
for v in videos:
    if v.get("url"):
        media_items.append({"media": {"url": v["url"]}})
for p in photos:
    if p.get("url"):
        media_items.append({"media": {"url": p["url"]}})

if media_items:
    container_components.append({"type": 14, "divider": True, "spacing": 1})
    container_components.append({"type": 12, "items": media_items[:10]})

container_components.append({
    "type": 10,
    "content": f"-# 💬 {replies}  🔁 {retweets}  ❤️ {likes}  👁️ {views}"
})

return {
    "type": 17,
    "accent_color": hex_color_to_int(tweet.get("color")),
    "components": container_components,
}
async def send_v2_webhook(session: aiohttp.ClientSession, webhook_url: str,
account: str, tweet: dict, read_post_url: str) -> bool:
container = build_v2_container(account, tweet, read_post_url)
action_row = build_action_row(read_post_url)

text

payload = {
    "flags": IS_COMPONENTS_V2,
    "components": [container, action_row],
}

request_url = f"{webhook_url}?with_components=true"
try:
    async with session.post(request_url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as response:
        if response.status in (200, 204):
            logging.info("Successfully posted V2 message to Discord Webhook.")
            return True
        body = await response.text()
        logging.error(f"Discord Webhook returned status {response.status}: {body}")
        return False
except Exception as e:
    logging.error(f"Error posting V2 webhook: {e}")
    return False
async def main():
if not ACCOUNTS:
logging.error("No accounts configured in ACCOUNTS environment variable.")
return

text

posted_urls = load_posted_urls()
is_first_run = len(posted_urls) == 0
now = time.time()

account_tweets = {account: [] for account in ACCOUNTS}

async with aiohttp.ClientSession() as session:
    tasks = [fetch_working_feed(session, account) for account in ACCOUNTS]
    feeds = await asyncio.gather(*tasks)

    for account, feed in zip(ACCOUNTS, feeds):
        if not feed or not feed.entries:
            continue

        entries_to_inspect = [feed.entries[0]] if is_first_run else feed.entries

        for entry in entries_to_inspect:
            raw_link = getattr(entry, "link", "")
            match = re.search(r"/status/(\d+)", raw_link)
            if not match:
                continue

            tweet_id = match.group(1)
            unique_key = f"{account}_{tweet_id}"

            if unique_key in posted_urls:
                continue

            published_parsed = entry.get("published_parsed")
            published_ts = time.mktime(published_parsed) if published_parsed else now

            if not is_first_run and (now - published_ts > MAX_AGE_SECONDS):
                continue

            account_tweets[account].append({
                "account": account,
                "tweet_id": tweet_id,
                "unique_key": unique_key,
                "published_ts": published_ts,
            })

    total_found = sum(len(v) for v in account_tweets.values())
    if total_found == 0:
        logging.info("No new tweets to post.")
        save_posted_urls(posted_urls)
        return

    logging.info(f"Found {total_found} new tweets. Posting (V2 layout)...")

    for account, tweets in account_tweets.items():
        if not tweets:
            continue

        webhook_url = get_webhook_for_account(account)
        if not webhook_url:
            logging.error(f"No webhook configured for @{account}. Skipping.")
            continue

        tweets.sort(key=lambda item: item["published_ts"])

        for tweet_info in tweets:
            tweet_id = tweet_info["tweet_id"]
            unique_key = tweet_info["unique_key"]
            read_post_url = f"https://fxtwitter.com/{account}/status/{tweet_id}"

            tweet_data = await fetch_tweet_details(session, account, tweet_id)
            if not tweet_data:
                logging.warning(f"Skipping {unique_key}: could not fetch FxTwitter API data.")
                continue

            success = await send_v2_webhook(session, webhook_url, account, tweet_data, read_post_url)
            if success:
                posted_urls.add(unique_key)
                await asyncio.sleep(1.5)

save_posted_urls(posted_urls)
logging.info("V2 RSS Feed Monitor execution finished.")
if name == "main":
asyncio.run(main())
