# ---------------------------------------------------------------------------
# ■ Reddit RSS Feed Monitor — V3 (Components V2 rich card — NATIVE media, NO EmbedEZ)
# ---------------------------------------------------------------------------
# Same monitoring as V1/V2 (combined feed, feed token, 429 retries, mod-queue
# safe 48h window, per-channel webhooks, dedup cache, auto-commit), but the
# card media comes from REDDIT'S OWN URLs — no EmbedEZ API, no mirror links,
# no credits. Round 11 (2026-09-15).
#
# ■ DATA PATHS (every fact below was live-verified 2026-09-15 from a
#   datacenter IP with the Discordbot/2.0 UA):
#
#   FULL MODE — activates automatically when post JSON is reachable:
#     a) OAuth app: REDDIT_CLIENT_ID + REDDIT_CLIENT_SECRET secrets (create at
#        reddit.com/prefs/apps, type "script", redirect http://localhost).
#        2026 note: new API access may require Reddit's approval form
#        (Responsible Builder Policy) — not guaranteed, so V3 never depends
#        on it. If you get one, just add the two secrets; no code change.
#     b) FEED TOKEN ON .json (workaround, tried automatically):
#        www.reddit.com/comments/<id>.json?…&feed=<REDDIT_FEED_TOKEN>.
#        Anonymous .json is 403 from datacenters (verified); whether your
#        feed token lifts that is answered by your FIRST test run — the log
#        line says exactly which path worked. Tried once per run; a 403
#        result is remembered for that run.
#     FULL MODE adds: every photo (20-photo posts → 2nd container),
#     upvotes/comments stats, video fallback_url (with audio), and true
#     crosspost full-embeds (fetches the original post, 1 level).
#
#   NATIVE MODE — default, zero setup, works when JSON is unavailable:
#     • photo: i.redd.it "swap" of the feed thumbnail (full-res, unsigned —
#       verified 206 for jpg/jpeg; PNGs 404 there → signed preview URL as-is)
#     • GIF: i.redd.it .gif (unsigned) / signed preview .gif as-is
#     • video: v.redd.it ID from the feed's [link] → CMAF files (open, no
#       sig: CMAF_720.mp4 is video-only, so the AUDIO is muxed in via a
#       public proxy chain, verified: h264 720p + AAC out):
#           1. proxy.embedez.com/render/video.mp4?videoUrl=…&audioUrl=…
#           2. vxreddit.com/redditvideo.mp4?video_url=…&audio_url=…
#       (both keyless, both returned a correctly muxed mp4 in testing)
#     • NEVER a silent video: if the chain fails → first-frame thumbnail +
#       Read Post button.
#   • signed preview.redd.it URLs MUST be used verbatim — changing ANY query
#     param (even width) breaks the signature (403, verified).
#   • YouTube: i.ytimg.com thumbnail (no sig) + official oembed title +
#     "YouTube" button with the starwardspark3 animated emoji; when
#     YOUTUBE_MEDIA_EMBED is True it also tries seaof.glass/yt/<id>.mp4
#     (playable mp4, verified 206 with Discordbot UA; 502 on cold start once —
#     handled by range-check + 1 retry, else thumb+button). youtube.com/live
#     links → thumb+button only.
#   • redgifs link posts: media.redgifs.com/<name>.mp4 (open, verified).
#
# ■ DISCORD COMPONENTS-V2 LIMITS (verified against Discord docs, 2026-09-15):
#   40 components per message, 10 per container, 10 items per media gallery,
#   5 buttons per row, 4000 chars total text. → 20 photos = 2 containers × 10.
#
# ■ WORKFLOW: identical to V1/V2. Test-area first:
#   run: python "testing area/reddit_main_v3test.py"
#   On pass → copy to reddit_main_v3.py and point the run line at it.
# ---------------------------------------------------------------------------
import os
import re
import json
import time
import base64
import asyncio
import logging
import html as html_lib
import aiohttp
import feedparser
from urllib.parse import quote
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
load_dotenv()

# ---------------------------------------------------------------------------
# ■ SUBREDDITS TO TRACK
# ---------------------------------------------------------------------------
SUBREDDITS_STR = os.getenv("SUBREDDITS", "Zenlesszonezeroleaks_,Genshin_Impact_Leaks,HonkaiStarRail_leaks,WutheringWavesLeaks,HonkaiNexusAnimaLeaks,AnantaLeaks")
SUBREDDITS = [s.strip() for s in SUBREDDITS_STR.split(",") if s.strip()]

DEFAULT_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# Personal Reddit feed token (old.reddit.com -> Preferences -> Feeds).
# Still used for the RSS feed (rate tier) AND now also attempted on the
# .json endpoints (workaround for the 2026 datacenter JSON wall — see header).
REDDIT_FEED_TOKEN = os.getenv("REDDIT_FEED_TOKEN", "").strip()

# OPTIONAL (FULL MODE, path a): Reddit script app credentials.
# reddit.com/prefs/apps -> create another app -> type "script" ->
# redirect http://localhost. Client ID = under the app name; secret via the
# "get secret" button. Add as repo secrets when/ if you get an app approved.
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "").strip()
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "").strip()
# Reddit requires a descriptive User-Agent for OAuth API calls.
REDDIT_API_USER_AGENT = "python:uesu.news-feed-embed:v3 (personal rss monitor)"

CACHE_FILE = "posted_reddit.json"
MAX_CACHE_SIZE = 500

# Wide window (48h) so posts approved from a subreddit's moderator queue a day
# or more later are still caught (approval bumps the RSS "updated" stamp).
MAX_AGE_SECONDS = 48 * 3600

# ---------------------------------------------------------------------------
# ■ RSS SOURCES (unchanged from V1/V2 — see round 8/9 notes)
# ---------------------------------------------------------------------------
REDDIT_RSS_INSTANCES = [
    "https://www.reddit.com",
    "https://old.reddit.com",
    "https://safereddit.com",           # 2026-09-13: Anubis bot check (fallback lottery)
    "https://red.artemislena.eu",       # 2026-09-13: Anubis bot check (fallback lottery)
    "https://redlib.privacyredirect.com",  # 2026-09-13: Anubis bot check (fallback lottery)
]

RATE_LIMIT_RETRY_DELAY_1 = 6
RATE_LIMIT_RETRY_DELAY_2 = 45
FEED_FETCH_STAGGER = 1.2
COMBINED_FEED_LIMIT = 100

# ---------------------------------------------------------------------------
# ■ V3 — NATIVE MEDIA SETTINGS
# ---------------------------------------------------------------------------
IS_COMPONENTS_V2 = 1 << 15

# Media gallery / container layout (Discord limits: 10 items per gallery,
# 10 components per container, 40 total per message).
MEDIA_PER_GALLERY = 10
MAX_GALLERIES = 2                      # -> max 20 photos per post (Reddit's own cap)

# Video: which CMAF quality to request from the proxies (360 / 720 / 1080).
CMAF_QUALITY = 720
# Skip any candidate media file larger than this (bytes) — same 256 MiB+ headroom
# logic proven on the X engines (234 MB plays, 521 MB+ fails in tiles).
MAX_MEDIA_BYTES = 256 * 1024 * 1024

# Audio video proxy chain (both verified keyless 2026-09-15, muxed h264+AAC out):
VIDEO_PROXY_EMBEDEZ = ("https://proxy.embedez.com/render/video.mp4"
                       "?videoUrl={video_url}&audioUrl={audio_url}&headers=%7B%7D")
VIDEO_PROXY_VXREDDIT = ("https://vxreddit.com/redditvideo.mp4"
                        "?video_url={video_url}&audio_url={audio_url}")

# YouTube: also try to PLAY the video in the media block via seaof.glass
# (quartz) — range-checked with 1 retry; on failure it degrades to
# thumbnail + button automatically. (Live-test in the test channel; set to
# False for thumbnail+button only.)
YOUTUBE_MEDIA_EMBED = True
YOUTUBE_MP4_TEMPLATE = "https://seaof.glass/yt/{video_id}.mp4"

# Text display budget (Discord: 4000 chars total per message across all
# text components; we keep header+body+stats comfortably under it).
MAX_BODY_CHARS = 3000

# Buttons (style 5 = Link). YouTube button uses the animated starwardspark3.
READ_POST_EMOJI = {"id": "1472388018689282261", "name": "starwardhmm", "animated": True}
YOUTUBE_EMOJI = {"id": "1483083423290490891", "name": "starwardspark3", "animated": True}
STATIC_BUTTONS = [
    {"label": "Citlali News", "url": "https://discord.gg/HyrVP9wRXu", "emoji": {"id": "1439878792653832253", "name": "starward11", "animated": True}},
    {"label": "Support", "url": "https://ko-fi.com/jieunlatte", "emoji": {"id": "1509026327548657914", "name": "starwardfans", "animated": True}},
]

# ---------------------------------------------------------------------------
# ■ URL PATTERNS
# ---------------------------------------------------------------------------
# watch / shorts / youtu.be / live (live = no mp4 possible -> thumb+button)
YOUTUBE_RE = re.compile(
    r"https?://(?:www\.)?(?:youtube\.com/(?:watch\?[^\"'<>)\]\s]*v=|shorts/|live/)[^\"'<>)\]\s]*"
    r"|youtu\.be/[^\"'<>)\]\s]+)",
    re.IGNORECASE,
)
YOUTUBE_ID_RE = re.compile(r"(?:v=|youtu\.be/|shorts/|live/)([A-Za-z0-9_-]{11})")
VREDDIT_RE = re.compile(r"https?://v\.redd\.it/([a-z0-9]+)")
REDGIFS_RE = re.compile(r"https?://(?:www\.)?redgifs\.com/(?:watch|gallery|redeyes?)/([A-Za-z0-9]+)")

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
}

# ---------------------------------------------------------------------------
# ■ RUNTIME STATE (per run)
# ---------------------------------------------------------------------------
_oauth_token = None          # cached for the run
_feedtoken_json_failed = False  # set True after a 403 on ?feed= .json (per run)


# ---------------------------------------------------------------------------
# ■ SMALL HELPERS (same as V1/V2 unless noted)
# ---------------------------------------------------------------------------
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
    match = re.search(r"(/r/[^\s?]+)", link)
    return match.group(1).rstrip("/") + "/" if match else None


def extract_subreddit(path: str) -> str | None:
    match = re.match(r"/r/([^/]+)/", path or "")
    return match.group(1) if match else None


def extract_post_id(path: str) -> str | None:
    match = re.search(r"/comments/([a-zA-Z0-9]+)/", path)
    return match.group(1) if match else None


def _subreddit_by_name(name: str) -> str | None:
    for sub in SUBREDDITS:
        if sub.lower() == (name or "").lower():
            return sub
    return None


def strip_html(value: str | None) -> str:
    """Removes tags from HTML-ish strings (used for JSON selftext etc.)."""
    if not value:
        return ""
    value = re.sub(r"(?i)<br\s*/?>", " ", value)
    value = re.sub(r"<[^>]+>", "", value)
    value = html_lib.unescape(value)
    return re.sub(r"\s{2,}", " ", value).strip()


def clean_rss_body(value: str | None) -> str:
    """
    Turn the RSS entry's content HTML into clean plain text.
    The feed wraps post HTML in <table><tr><td>…</td></tr></table> and appends
    a 'submitted by /u/… to r/…' footer plus [link]/[comments] spans — all of
    that is stripped; paragraphs are kept on separate lines.
    """
    if not value:
        return ""
    text = value
    text = re.sub(r"(?i)<\s*(br|/p|/div|/li|/table|/tr|/td|h[1-6])[^>]*>", "\n", text)
    text = re.sub(r"(?i)<span>\s*<a[^>]*>\[(?:link|comments)\]</a>\s*</span>", " ", text)
    text = re.sub(r"(?i)<img[^>]*>", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_lib.unescape(text)
    text = re.sub(r"submitted by\s+/u/\S+\s+to\s+r/\S+", " ", text)
    lines = [re.sub(r"\s{2,}", " ", ln).strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# ■ RSS FEED FETCHING (identical logic to V1/V2 — combined feed primary)
# ---------------------------------------------------------------------------
async def _fetch_feed(session: aiohttp.ClientSession, feed_url: str, label: str):
    """
    GETs one feed URL with two 429 retries (6s, then 45s). A response is only
    accepted if it is HTTP 200, contains real feedparser entries, and those
    entries carry reddit /comments/ permalinks. Every rejection is logged.
    """
    headers = {
        **BROWSER_HEADERS,
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
    }
    retry_delays = [RATE_LIMIT_RETRY_DELAY_1, RATE_LIMIT_RETRY_DELAY_2]
    attempt = 0
    while True:
        attempt += 1
        try:
            async with session.get(feed_url, headers=headers,
                                   timeout=aiohttp.ClientTimeout(total=15)) as response:
                if response.status == 429:
                    if attempt - 1 < len(retry_delays):
                        delay = retry_delays[attempt - 1]
                        logging.info(f"[{label}] HTTP 429 (rate limited) — retry {attempt} in {delay}s.")
                        await asyncio.sleep(delay)
                        continue
                    logging.info(f"[{label}] still HTTP 429 after {attempt - 1} retries — giving up.")
                    return None
                if response.status != 200:
                    logging.info(f"[{label}] HTTP {response.status} — rejected.")
                    return None
                content = await response.text()
                feed = await asyncio.to_thread(feedparser.parse, content)
                if not feed.entries:
                    logging.info(f"[{label}] no RSS entries (bot-check/interstitial/HTML page?) — rejected.")
                    return None
                if not any("/comments/" in str(getattr(e, "link", "")) for e in feed.entries[:5]):
                    logging.info(f"[{label}] entries contain no reddit /comments/ links — rejected.")
                    return None
                return feed
        except Exception as e:
            logging.info(f"[{label}] error: {e}")
            return None


def _combined_feed_url() -> str:
    """ONE feed for all tracked subreddits: /r/a+b+c/new.rss?limit=100 (+ token)."""
    url = "https://www.reddit.com/r/" + "+".join(SUBREDDITS) + f"/new.rss?limit={COMBINED_FEED_LIMIT}"
    if REDDIT_FEED_TOKEN:
        url += f"&feed={REDDIT_FEED_TOKEN}"
    return url


async def fetch_combined_feed(session: aiohttp.ClientSession):
    logging.info(f"Fetching combined feed for {len(SUBREDDITS)} subreddits in 1 request...")
    feed = await _fetch_feed(session, _combined_feed_url(), "combined")
    if feed:
        covered = set()
        for e in feed.entries:
            path = normalize_reddit_path(str(getattr(e, "link", "")))
            sub = _subreddit_by_name(extract_subreddit(path)) if path else None
            if sub:
                covered.add(sub)
        logging.info(f"Combined feed OK: {len(feed.entries)} entries covering {len(covered)} subreddit(s).")
    return feed


async def fetch_working_reddit_feed(session: aiohttp.ClientSession, subreddit: str):
    """Fallback mode: tries each RSS source in order for one subreddit."""
    for instance in REDDIT_RSS_INSTANCES:
        feed_url = f"{instance}/r/{subreddit}/new/.rss"
        if REDDIT_FEED_TOKEN and "reddit.com" in instance:
            feed_url += f"?feed={REDDIT_FEED_TOKEN}"
        feed = await _fetch_feed(session, feed_url, instance)
        if feed:
            logging.info(f"Successfully fetched r/{subreddit} from {instance}")
            return feed
    logging.warning(f"Could not fetch valid RSS feed for r/{subreddit} from any instance.")
    return None


def extract_youtube_url(*html_parts: str | None) -> str | None:
    """Finds a YouTube link (watch / shorts / youtu.be / live) in HTML text."""
    for html in html_parts:
        match = YOUTUBE_RE.search(html or "")
        if match:
            return match.group(0)
    return None


def extract_youtube_id(url: str | None) -> tuple[str | None, bool]:
    """Returns (video_id, is_live)."""
    if not url:
        return None, False
    if "youtube.com/live/" in url:
        m = re.search(r"live/([A-Za-z0-9_-]{11})", url)
        return (m.group(1) if m else None), True
    m = YOUTUBE_ID_RE.search(url)
    return (m.group(1) if m else None), False


# ---------------------------------------------------------------------------
# ■ POST JSON — full-mode data (OAuth, then feed-token workaround)
# ---------------------------------------------------------------------------
async def get_oauth_token(session: aiohttp.ClientSession) -> str | None:
    """
    Application-only OAuth token (grant_type=client_credentials) — the same
    flow Embeddit uses. No user login, no password. Returns None if the
    secrets are missing/invalid.
    """
    global _oauth_token
    if _oauth_token:
        return _oauth_token
    if not (REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET):
        return None
    basic = base64.b64encode(f"{REDDIT_CLIENT_ID}:{REDDIT_CLIENT_SECRET}".encode()).decode()
    try:
        async with session.post(
            "https://www.reddit.com/api/v1/access_token",
            data={"grant_type": "client_credentials"},
            headers={
                "Authorization": f"Basic {basic}",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": REDDIT_API_USER_AGENT,
            },
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            if resp.status != 200:
                logging.info(f"OAuth token request HTTP {resp.status} — {await resp.text()[:200]}")
                return None
            data = await resp.json()
        _oauth_token = data.get("access_token")
        if _oauth_token:
            logging.info("OAuth application token acquired (FULL MODE path a).")
        else:
            logging.info(f"OAuth token response had no access_token: {str(data)[:200]}")
    except Exception as e:
        logging.info(f"OAuth token request error: {e}")
    return _oauth_token


async def fetch_post_json(session: aiohttp.ClientSession, post_id: str, use_oauth: bool) -> dict | None:
    """
    Fetches ONE post's JSON (the full data: all media, stats, crosspost link).
    Paths: OAuth token -> oauth.reddit.com ; else feed token on www .json
    (workaround — 403 result remembered for the run). Returns the post dict
    or None (caller falls back to native/RSS-only data).
    """
    global _feedtoken_json_failed
    url = f"https://oauth.reddit.com/comments/{post_id}.json?limit=1&raw_json=1"
    headers = {"User-Agent": REDDIT_API_USER_AGENT}
    token = await get_oauth_token(session) if use_oauth else None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    elif not _feedtoken_json_failed and REDDIT_FEED_TOKEN:
        # Workaround attempt: the personal feed token on a .json endpoint.
        # Anonymous .json is 403 from datacenters; the token MIGHT lift it.
        url = (f"https://www.reddit.com/comments/{post_id}.json"
               f"?limit=1&raw_json=1&feed={REDDIT_FEED_TOKEN}")
        headers = dict(BROWSER_HEADERS)
        await asyncio.sleep(65)  # be polite to the anonymous tier (1 req/min)
    else:
        return None

    try:
        async with session.get(url, headers=headers,
                               timeout=aiohttp.ClientTimeout(total=20)) as resp:
            if resp.status == 429:
                logging.info(f"[{post_id}] post JSON 429 — one retry in 45s.")
                await asyncio.sleep(45)
                async with session.get(url, headers=headers,
                                       timeout=aiohttp.ClientTimeout(total=20)) as resp2:
                    if resp2.status != 200:
                        logging.info(f"[{post_id}] post JSON retry HTTP {resp2.status} — native mode.")
                        return None
                    body = await resp2.text()
            elif resp.status != 200:
                if "feed=" in url:
                    _feedtoken_json_failed = True
                logging.info(f"[{post_id}] post JSON HTTP {resp.status} — native mode "
                             f"({'feed token will not be retried this run' if 'feed=' in url else 'no JSON path'})")
                return None
            else:
                body = await resp.text()
        data = json.loads(body)
        post = data[0]["data"]["children"][0]["data"]
        source = "oauth" if token else "feed-token"
        logging.info(f"[{post_id}] post JSON OK via {source} (FULL MODE).")
        return post
    except Exception as e:
        logging.info(f"[{post_id}] post JSON error: {e} — native mode.")
        return None


# ---------------------------------------------------------------------------
# ■ MEDIA VERIFICATION + RESOLUTION (V3 core)
# ---------------------------------------------------------------------------
async def media_url_ok(session: aiohttp.ClientSession, url: str, timeout: int = 20,
                       video: bool = False) -> tuple[bool, int]:
    """
    Range-checks a media URL the way a fetch would. Returns (ok, total_bytes).
    ok = 200/206 with a sane content-type and size under MAX_MEDIA_BYTES.
    """
    try:
        async with session.get(url, headers={"User-Agent": "Discordbot/2.0", "Range": "bytes=0-0"},
                               timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
            if resp.status in (200, 206):
                ctype = (resp.headers.get("Content-Type") or "").lower()
                want = ("video" in ctype or "octet-stream" in ctype) if video else (
                    "image" in ctype or "video" in ctype or "octet-stream" in ctype)
                size = 0
                cr = resp.headers.get("Content-Range")  # e.g. "bytes 0-0/12345"
                if cr and "/" in cr:
                    try:
                        size = int(cr.rsplit("/", 1)[1])
                    except ValueError:
                        size = 0
                cl = resp.headers.get("Content-Length")
                if not size and cl and resp.status == 200:
                    size = int(cl)
                if want and (size == 0 or size <= MAX_MEDIA_BYTES):
                    return True, size
                logging.info(f"media check rejected {url[:90]} — type={ctype} size={size}")
                return False, size
            logging.info(f"media check {resp.status} for {url[:90]}")
            return False, 0
    except Exception as e:
        logging.info(f"media check error for {url[:90]}: {e}")
        return False, 0


def cmaf_urls(vid: str, quality: int = CMAF_QUALITY) -> dict:
    base = f"https://v.redd.it/{vid}"
    return {
        "video_mp4": f"{base}/CMAF_{quality}.mp4",
        "video_m3u8": f"{base}/CMAF_{quality}.m3u8",
        "audio_mp4": f"{base}/CMAF_AUDIO_128.mp4",
        "audio_m3u8": f"{base}/CMAF_AUDIO_128.m3u8",
    }


async def resolve_video_url(session: aiohttp.ClientSession, vid: str,
                            fallback_url: str | None = None) -> str | None:
    """
    Audio video chain (NO silent fallback):
      1. fallback_url (from post JSON, if it serves an mp4)
      2. proxy.embedez.com  (CMAF mp4 + audio -> muxed mp4)
      3. vxreddit.com       (CMAF m3u8 pair -> muxed mp4, cached by them)
    Qualities tried: CMAF_QUALITY, then 1080 (not every video has 720p).
    -> None means the caller uses thumbnail + button.
    """
    if fallback_url and "v.redd.it" in fallback_url and fallback_url.lower().split("?")[0].endswith(".mp4"):
        ok, size = await media_url_ok(session, fallback_url, timeout=60, video=True)
        if ok:
            logging.info(f"video url OK via fallback_url ({size} bytes).")
            return fallback_url
    for quality in (CMAF_QUALITY, 1080):
        c = cmaf_urls(vid, quality)
        em = VIDEO_PROXY_EMBEDEZ.format(video_url=quote(c["video_mp4"], safe=""),
                                        audio_url=quote(c["audio_mp4"], safe=""))
        ok, size = await media_url_ok(session, em, timeout=120, video=True)
        if ok:
            logging.info(f"video url OK via embedez-proxy q{quality} ({size} bytes).")
            return em
        if quality == CMAF_QUALITY:
            vx = VIDEO_PROXY_VXREDDIT.format(video_url=quote(c["video_m3u8"], safe=""),
                                             audio_url=quote(c["audio_m3u8"], safe=""))
            ok, size = await media_url_ok(session, vx, timeout=120, video=True)
            if ok:
                logging.info(f"video url OK via vxreddit-proxy ({size} bytes).")
                return vx
    logging.info("video chain exhausted — using thumbnail + button (no silent video).")
    return None


def photo_urls_from_metadata(mm: dict) -> list[str]:
    """
    media_metadata (JSON) -> ordered signed photo URLs.
    Order = the order of `preview.images` (each entry's id keys into media_metadata).
    Prefers the full-res `p` variant, falls back to `s`, then `source`.
    URLs are used VERBATIM (the s= signature covers the query params).
    """
    if not mm:
        return []
    urls = []
    seen = set()
    for key, meta in mm.items():
        if not isinstance(meta, dict) or meta.get("is_video") or meta.get("is_gif"):
            continue
        url = None
        for variant in ("p", "s"):
            v = meta.get(variant)
            if isinstance(v, dict) and v.get("url"):
                url = v["url"]
                break
        if not url:
            src = meta.get("source")
            if isinstance(src, dict) and src.get("url"):
                url = src["url"]
        if url and url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def gif_url_from_metadata(mm: dict) -> str | None:
    for meta in (mm or {}).values():
        if isinstance(meta, dict) and meta.get("is_gif"):
            for variant in ("u", "s"):
                v = meta.get(variant)
                if isinstance(v, dict) and v.get("url"):
                    return v["url"]
    return None


def i_reddit_swap(url: str) -> str | None:
    """
    preview.redd.it/<file>.jpg|jpeg (signed) -> i.redd.it/<file>.jpg|jpeg
    (unsigned full-res; verified 2026-09-15 for jpg/jpeg, PNGs 404 there).
    Returns the candidate URL or None.
    """
    m = re.match(r"https?://preview\.redd\.it/([\w.-]+\.(?:jpe?g))\?", url or "", re.I)
    if not m:
        return None
    return f"https://i.redd.it/{m.group(1)}"


def extract_vreddit_id(text: str | None) -> str | None:
    m = VREDDIT_RE.search(text or "")
    return m.group(1) if m else None


def extract_redgifs_url(text: str | None) -> str | None:
    m = REDGIFS_RE.search(text or "")
    if not m:
        return None
    url = f"https://media.redgifs.com/{m.group(1)}.mp4"
    return url


async def resolve_youtube_media(session: aiohttp.ClientSession, vid: str, is_live: bool):
    """
    Returns (media_url_or_None, thumb_url). YOUTUBE_MEDIA_EMBED tries
    seaof.glass .mp4 (1 retry for cold start). Thumbs: maxres -> hqdefault.
    """
    media_url = None
    if YOUTUBE_MEDIA_EMBED and not is_live:
        mp4 = YOUTUBE_MP4_TEMPLATE.format(video_id=vid)
        for attempt in (1, 2):
            ok, size = await media_url_ok(session, mp4, timeout=90, video=True)
            if ok:
                media_url = mp4
                logging.info(f"YouTube mp4 OK via seaof.glass ({size} bytes).")
                break
            if attempt == 1:
                logging.info("YouTube mp4 check failed — retrying once (cold transcode?).")
                await asyncio.sleep(5)
    thumb = f"https://i.ytimg.com/vi/{vid}/maxresdefault.jpg"
    ok, _ = await media_url_ok(session, thumb, timeout=15)
    if not ok:
        thumb = f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
    return media_url, thumb


async def fetch_yt_oembed(session: aiohttp.ClientSession, yt_url: str) -> dict | None:
    try:
        async with session.get(
            "https://www.youtube.com/oembed",
            params={"url": yt_url, "format": "json"},
            headers=dict(BROWSER_HEADERS),
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            if resp.status == 200:
                return await resp.json()
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# ■ POST DATA ASSEMBLY
# ---------------------------------------------------------------------------
def entry_to_base_data(entry) -> dict:
    """What we can always get from the RSS entry (native-mode base)."""
    content_html = ""
    for c in entry.get("content") or []:
        if c.get("value"):
            content_html += c["value"]
    if not content_html and entry.get("summary"):
        content_html = entry["summary"]
    thumb = None
    for m in entry.get("media_thumbnail") or []:
        if isinstance(m, dict) and (m.get("url") or m.get("href")):
            thumb = m.get("url") or m.get("href")
            break
    author = str(getattr(entry, "author", "") or "")
    if author.startswith("/u/"):
        author = author[3:]
    return {
        "title": str(getattr(entry, "title", "") or "")[:400],
        "author": author or "unknown",
        "content_html": content_html,
        "thumb": thumb,
        "body": clean_rss_body(content_html),
        "vred_id": extract_vreddit_id(content_html),
        "redgifs_url": extract_redgifs_url(content_html),
        "youtube_url": extract_youtube_url(content_html),
    }


async def resolve_post_media(session: aiohttp.ClientSession, base: dict,
                             post_json: dict | None) -> dict:
    """
    Builds the final media list + meta for one post.
    media = [{"kind": "image"|"gif"|"video", "url": ...}, ...]
    """
    media: list[dict] = []
    stats = None
    crosspost = None
    body = base["body"]
    title = base["title"]
    author = base["author"]
    yt_url = base["youtube_url"]
    yt_live = False

    if post_json:
        # ---- FULL MODE ----
        title = str(post_json.get("title") or title)[:400]
        author = str(post_json.get("author") or author)
        if post_json.get("selftext"):
            body = strip_html(post_json["selftext"]) or body
        stats = {"comments": post_json.get("num_comments", 0),
                 "ups": post_json.get("ups", 0)}
        if post_json.get("crosspost_post_link"):
            crosspost = {"url": post_json["crosspost_post_link"],
                         "path": normalize_reddit_path(post_json["crosspost_post_link"])}
        # crosspost full-embed: fetch the ORIGINAL post (1 level only)
        if crosspost:
            orig_id = extract_post_id(crosspost["path"] or "")
            if orig_id:
                try:
                    # fetch_post_json already falls back internally
                    # (oauth -> feed token -> None)
                    orig = await fetch_post_json(session, orig_id, use_oauth=True)
                    if orig:
                        mm = orig.get("media_metadata") or {}
                        photos = photo_urls_from_metadata(mm)
                        g = gif_url_from_metadata(mm)
                        for u in photos[:MAX_GALLERIES * MEDIA_PER_GALLERY]:
                            media.append({"kind": "image", "url": u})
                        if g:
                            media.append({"kind": "gif", "url": g})
                        if orig.get("selftext"):
                            orig_body = strip_html(orig["selftext"])
                            if orig_body and len(orig_body) > len(body or ""):
                                body = orig_body
                        logging.info(f"crosspost: fetched original {orig_id} "
                                     f"({len(media)} media items).")
                except Exception as e:
                    logging.info(f"crosspost original fetch failed: {e}")
        # own media
        mm = post_json.get("media_metadata") or {}
        preview_images = (post_json.get("preview") or {}).get("images") or []
        # ordered by preview.images; fall back to metadata order if absent
        ordered_keys = [p.get("id") for p in preview_images if isinstance(p, dict) and p.get("id") in mm]
        video_poster = None  # first frame of a video post (used if the video tile is unavailable)
        if ordered_keys:
            for key in ordered_keys:
                meta = mm[key]
                if not isinstance(meta, dict):
                    continue
                if meta.get("is_gif") and not any(x["kind"] == "gif" for x in media):
                    g = (meta.get("u") or meta.get("s") or {}).get("url")
                    if g:
                        media.append({"kind": "gif", "url": g})
                        continue
                if meta.get("is_video"):
                    s = meta.get("s")
                    if video_poster is None and isinstance(s, dict) and s.get("url"):
                        video_poster = s["url"]
                    continue
                url = None
                for variant in ("p", "s"):
                    v = meta.get(variant)
                    if isinstance(v, dict) and v.get("url"):
                        url = v["url"]
                        break
                if url:
                    media.append({"kind": "image", "url": url})
        else:
            for u in photo_urls_from_metadata(mm):
                media.append({"kind": "image", "url": u})
            g = gif_url_from_metadata(mm)
            if g:
                media.append({"kind": "gif", "url": g})
            for meta in mm.values():
                if isinstance(meta, dict) and meta.get("is_video"):
                    s = meta.get("s")
                    if isinstance(s, dict) and s.get("url"):
                        video_poster = s["url"]
                        break
        # video
        vid = None
        fallback_url = None
        m = post_json.get("media")
        if isinstance(m, dict) and isinstance(m.get("reddit_video"), dict):
            rv = m["reddit_video"]
            fallback_url = rv.get("fallback_url")
            if fallback_url:
                vid = extract_vreddit_id(fallback_url)
        if not vid:
            vid = base["vred_id"] or extract_vreddit_id(str(post_json.get("url") or ""))
        if vid and not any(x["kind"] in ("video", "gif") for x in media):
            vurl = await resolve_video_url(session, vid, fallback_url)
            if vurl:
                media.append({"kind": "video", "url": vurl})
            elif video_poster and not media:
                # audio chain failed -> show the first frame (never a silent video)
                media.append({"kind": "image", "url": video_poster})
                logging.info("video unavailable -> using first-frame poster + button.")
        # youtube from the post's own url (link posts)
        if not yt_url:
            yt_url = extract_youtube_url(str(post_json.get("url") or ""))
    else:
        # ---- NATIVE MODE (RSS only) ----
        thumb = base["thumb"]
        if thumb:
            if ".gif" in thumb:
                media.append({"kind": "gif", "url": thumb})
            else:
                swap = i_reddit_swap(thumb)
                if swap:
                    ok, _ = await media_url_ok(session, swap, timeout=15)
                    if ok:
                        media.append({"kind": "image", "url": swap})
                        logging.info("photo via i.redd.it full-res swap.")
                    else:
                        media.append({"kind": "image", "url": thumb})
                else:
                    media.append({"kind": "image", "url": thumb})
        # video: v.redd.it id from the feed's [link] (skip GIF posts)
        if base["vred_id"] and not any(x["kind"] in ("video", "gif") for x in media):
            vurl = await resolve_video_url(session, base["vred_id"], None)
            if vurl:
                media.append({"kind": "video", "url": vurl})
        # redgifs link post
        if base["redgifs_url"] and not any(x["kind"] == "video" for x in media):
            ok, _ = await media_url_ok(session, base["redgifs_url"], timeout=30, video=True)
            if ok:
                media.append({"kind": "video", "url": base["redgifs_url"]})

    # youtube media tile (both modes)
    yt_vid, yt_live = extract_youtube_id(yt_url)
    yt_media_url = None
    if yt_vid:
        yt_media_url, yt_thumb = await resolve_youtube_media(session, yt_vid, yt_live)
        if yt_media_url and not any(x["kind"] == "video" for x in media):
            media.append({"kind": "video", "url": yt_media_url})
        elif yt_media_url is None:
            # keep the thumbnail visible even when the video tile is not used
            if not media:
                media.append({"kind": "image", "url": yt_thumb})

    media = media[:MAX_GALLERIES * MEDIA_PER_GALLERY]
    return {
        "title": title,
        "author": author,
        "body": body[:MAX_BODY_CHARS] + ("…" if len(body) > MAX_BODY_CHARS else ""),
        "media": media,
        "stats": stats,
        "crosspost": crosspost,
        "youtube_url": yt_url,
        "youtube_id": yt_vid,
        "youtube_live": yt_live,
        "full_mode": bool(post_json),
    }


# ---------------------------------------------------------------------------
# ■ CARD BUILDING (components v2)
# ---------------------------------------------------------------------------
def build_action_row(reddit_url: str, youtube_url: str | None) -> dict:
    buttons = [
        {"type": 2, "style": 5, "label": "Read Post", "url": reddit_url, "emoji": READ_POST_EMOJI},
    ]
    if youtube_url:
        buttons.append({"type": 2, "style": 5, "label": "YouTube", "url": youtube_url,
                        "emoji": YOUTUBE_EMOJI})
    for btn in STATIC_BUTTONS:
        b = {"type": 2, "style": 5, "label": btn["label"], "url": btn["url"]}
        if btn.get("emoji"):
            b["emoji"] = btn["emoji"]
        buttons.append(b)
    return {"type": 1, "components": buttons[:5]}


def build_v3_payload(subreddit: str, data: dict, reddit_url: str, posted_ts: int) -> dict:
    """
    <=10 media items -> single container (V2 look):
        header / body / divider / gallery / stats / divider / buttons
    11-20 media items -> two containers:
        container 1: header / body / divider / gallery(10)
        container 2: divider / gallery(rest) / stats / divider / buttons
    (Discord: 10 items per gallery, 10 components per container, 40 total.)
    """
    header = f"### [{data['title']}]({reddit_url})\n*by {data['author']} in r/{subreddit}*"
    if data["crosspost"]:
        header += f"\n*🔁 Crosspost of {data['crosspost']['url']}*"

    media = data["media"]
    stats = data["stats"]
    ts_suffix = f"   •   🕐 <t:{posted_ts}:f>"
    if stats:
        stats_line = f"-# 💬 {stats['comments']} 👍 {stats['ups']}{ts_suffix}"
    else:
        stats_line = f"-# 🕐 <t:{posted_ts}:f>"

    row = build_action_row(reddit_url, data["youtube_url"])

    def gallery(items: list) -> dict:
        return {"type": 12, "items": [{"media": {"url": m["url"]}} for m in items]}

    if len(media) > MEDIA_PER_GALLERY:
        first, second = media[:MEDIA_PER_GALLERY], media[MEDIA_PER_GALLERY:]
        container1 = {"type": 17, "accent_color": 16729344, "components": [
            {"type": 10, "content": header},
        ]}
        if data["body"]:
            container1["components"].append({"type": 10, "content": data["body"]})
        container1["components"].append({"type": 14, "divider": True, "spacing": 1})
        container1["components"].append(gallery(first))
        container2 = {"type": 17, "accent_color": 16729344, "components": [
            {"type": 14, "divider": True, "spacing": 1},
            gallery(second),
            {"type": 10, "content": stats_line},
            {"type": 14, "divider": True, "spacing": 1},
            row,
        ]}
        return {"flags": IS_COMPONENTS_V2,
                "components": [container1, container2]}

    inner = [{"type": 10, "content": header}]
    if data["body"]:
        inner.append({"type": 10, "content": data["body"]})
    if media:
        inner.append({"type": 14, "divider": True, "spacing": 1})
        inner.append(gallery(media))
    inner.append({"type": 10, "content": stats_line})
    inner.append({"type": 14, "divider": True, "spacing": 1})
    inner.append(row)
    return {"flags": IS_COMPONENTS_V2,
            "components": [{"type": 17, "accent_color": 16729344, "components": inner}]}


# ---------------------------------------------------------------------------
# ■ MAIN
# ---------------------------------------------------------------------------
async def main():
    if not SUBREDDITS:
        logging.error("No subreddits configured in SUBREDDITS environment variable.")
        return
    if not REDDIT_FEED_TOKEN:
        logging.warning("REDDIT_FEED_TOKEN not set — running anonymously. The combined feed "
                        "(1 request/run) usually fits the ~1 req/min limit, but add your feed "
                        "token (old.reddit.com -> Preferences -> Feeds) as REDDIT_FEED_TOKEN "
                        "to be bulletproof. (V3 also tries it on .json for FULL MODE.)")
    if not (REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET):
        logging.info("No Reddit OAuth app secrets — FULL MODE may still work via the feed "
                     "token on .json (tested once per run); otherwise cards use native RSS data.")

    posted = load_posted()
    is_first_run = len(posted) == 0
    now = time.time()

    use_oauth = bool(REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET)

    async with aiohttp.ClientSession() as session:
        # ---- PRIMARY: one combined request for all subreddits -------------
        combined = await fetch_combined_feed(session)
        new_posts = []  # (subreddit, path, unique_key, published_ts, entry)

        def collect(entries, known_subreddit: str | None):
            for entry in entries:
                raw_link = str(getattr(entry, "link", ""))
                path = normalize_reddit_path(raw_link)
                if not path:
                    continue
                sub = known_subreddit or _subreddit_by_name(extract_subreddit(path))
                if not sub:
                    continue
                post_id = extract_post_id(path)
                if not post_id:
                    continue
                unique_key = f"{sub}_{post_id}"
                if unique_key in posted:
                    continue
                published_parsed = entry.get("published_parsed")
                updated_parsed = entry.get("updated_parsed")
                published_ts = time.mktime(published_parsed) if published_parsed else now
                updated_ts = time.mktime(updated_parsed) if updated_parsed else published_ts
                activity_ts = max(published_ts, updated_ts)
                if not is_first_run and (now - activity_ts > MAX_AGE_SECONDS):
                    continue
                new_posts.append((sub, path, unique_key, published_ts, activity_ts, entry))

        if combined and combined.entries:
            entries = [combined.entries[0]] if is_first_run else combined.entries
            collect(entries, None)
        else:
            logging.info("Combined feed unavailable — falling back to per-subreddit feeds...")

            async def _staggered_fetch(sub: str, index: int):
                await asyncio.sleep(index * FEED_FETCH_STAGGER)
                return await fetch_working_reddit_feed(session, sub)

            tasks = [_staggered_fetch(sub, i) for i, sub in enumerate(SUBREDDITS)]
            feeds = await asyncio.gather(*tasks)
            for subreddit, feed in zip(SUBREDDITS, feeds):
                if not feed or not feed.entries:
                    continue
                entries = [feed.entries[0]] if is_first_run else feed.entries
                collect(entries, subreddit)

        total_found = len(new_posts)
        if total_found == 0:
            logging.info("No new Reddit posts to post.")
            save_posted(posted)
            return

        logging.info(f"Found {total_found} new Reddit posts. Building V3 cards...")

        # newest first per sub for stable ordering
        new_posts.sort(key=lambda p: p[3])

        for subreddit, path, unique_key, published_ts, activity_ts, entry in new_posts:
            webhook_url = get_webhook_for_subreddit(subreddit)
            if not webhook_url:
                logging.error(f"No webhook configured for r/{subreddit}. Skipping {unique_key}.")
                continue

            reddit_url = f"https://www.reddit.com{path}"
            base = entry_to_base_data(entry)

            post_json = await fetch_post_json(session, extract_post_id(path) or "",
                                              use_oauth=use_oauth)

            try:
                data = await resolve_post_media(session, base, post_json)
                posted_ts = int(max(published_ts, activity_ts))
                payload = build_v3_payload(subreddit, data, reddit_url, posted_ts)
                target_url = f"{webhook_url}?with_components=true"
                async with session.post(target_url, json=payload,
                                        timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status in (200, 204):
                        posted.add(unique_key)
                        kinds = ",".join(sorted({m["kind"] for m in data["media"]})) or "text"
                        mode = "full" if data["full_mode"] else "native"
                        logging.info(f"Reddit V3 Posted: {unique_key} (media={kinds} | {mode} | "
                                     f"{len(data['media'])} item(s))")
                        await asyncio.sleep(1.5)
                    else:
                        body = await resp.text()
                        logging.error(f"Discord error {resp.status} for {unique_key}: {body}")
            except Exception as e:
                logging.error(f"Failed building/posting {unique_key}: {e}")

    save_posted(posted)
    logging.info("Reddit V3 Monitor execution finished.")


if __name__ == "__main__":
    asyncio.run(main())
