# ---------------------------------------------------------------------------
# ■ Reddit RSS Feed Monitor — V3 (Components V2 rich card — NATIVE media, NO EmbedEZ)
# ---------------------------------------------------------------------------
# Same monitoring as V1/V2 (combined feed, feed token, 429 retries, mod-queue
# safe 48h window, per-channel webhooks, dedup cache, auto-commit), but the
# card media comes from REDDIT'S OWN URLs — no EmbedEZ API, no mirror links,
# no credits. Round 12 (2026-09-15).
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
#     • photo(s): EVERY redd.it image in the RSS content, in post order,
#       best rendition each: i.redd.it "swap" (full-res, unsigned — verified
#       206 for jpg/jpeg; slug-prefixed preview names reduced to the bare
#       file id; PNGs 404 there → largest signed preview URL as-is)
#     • GIF: i.redd.it .gif (unsigned) / signed preview .gif as-is
#     • video (video posts show the video ONLY, never a dup thumb):
#           1. v.redd.it/<id>/DASH_<q>.mp4 (720→1080→480→360) — self-
#              contained mp4 WITH audio, straight from Reddit, open, no sig
#              (round 12 — replaces the old proxy-first chain)
#           2. proxy.embedez.com/render/video.mp4?videoUrl=…&audioUrl=…
#              (CMAF video + CMAF audio -> muxed mp4; keyless, verified
#              h264 720p + AAC out)
#           3. vxreddit.com/redditvideo.mp4?video_url=…&audio_url=…
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
# ■ ROUND 12 FIXES (2026-09-15, from the live test-channel review):
#   1. Multi-photo posts now show ALL photos: single-image posts get every
#      redd.it image from the RSS content in post order; multi-image GALLERY
#      posts (whose RSS content carries no image links — verified in the
#      2026-09-15 workflow log) get a best-effort REDLIB post-page harvest
#      (same instances as the feed fallback, probed in parallel, ~10s worst
#      case; on failure the single-thumbnail card is kept). FULL MODE had
#      all already.
#   2. Photos use the BEST rendition: i.redd.it full-res swap (jpg/jpeg) or
#      the largest signed preview URL — never the 140px feed thumbnail.
#   3. Stray redd.it image URLs no longer linger in the body text.
#   4. Video posts show the VIDEO ONLY — no duplicate first-frame thumbnail;
#      external-preview.redd.it thumbs (YouTube/external media screenshots)
#      are dropped whenever the post resolves a video.
#   5. Native reddit video chain now prefers v.redd.it DASH_<q>.mp4 — a
#      SELF-CONTAINED mp4 (h264 + AAC, with audio) straight from Reddit, no
#      proxy, no signature, no expiry — before the embedez/vxreddit CMAF
#      muxing proxies. (The signed packaged-media.redd.it DASH master links
#      expire within hours — the e=… query param — so they are NOT used.)
#   6. YouTube: default is now thumbnail + the animated starwardspark3
#      button (deterministic, no third-party transcoder in the hot path).
#      Set YOUTUBE_MEDIA_EMBED=1 to also try seaof.glass playback.
#   7. OP comment: FULL MODE fetches the stickied/top OP comment and shows
#      it in the card ("💬 OP comment:", capped 500 chars + full-comment
#      link). REDDIT_OP_COMMENT=0 disables.
#   8. Discohook: after each successful post a keyless share-link preview of
#      the exact card is created (discohook.app public API, /api/v1/share)
#      and the URL is logged to the workflow run. The share data contains
#      ONLY the public card payload — NO targets, so the webhook URL never
#      leaves the repo. DISCOHOOK_PREVIEW=0 disables.
#   9. Test tools: TEST_POST_ID=<sub>/<post_id> rebuilds one specific post;
#      DRY_RUN=1 builds + logs payloads without touching Discord or the
#      cache (use both from workflow_dispatch to verify before promoting).
#   10. (round 12c) TEST POST works in NATIVE MODE too: when the post JSON
#       is unavailable, the base is built from the post's RSS feed entry
#       (100-entry window) or, failing that, a redlib post page scrape.
#   11. (round 12e) TEST POST gains a 2nd native source: the post's OWN RSS
#       feed (/comments/<id>/.rss) — works for ANY post age, not just the
#       combined feed's 100-entry window. Native photo path now logs how
#       many media URLs the RSS content carries (gallery diagnostics).
#   12. (round 13) PROXY MEDIA: native-mode card media now comes FIRST from
#       the public proxy services — redditez.com (EmbedEZ) -> vxreddit.com
#       -> embeddit.deltandy.me, in that priority order (see testing
#       area/reddit_proxy.py). Each service's own URLs are used verbatim in
#       the components-v2 card: full-res photos, EVERY gallery photo (up to
#       20 = 2 containers), videos WITH audio, GIFs, plus stats. A per-run
#       warm-up probes all three with one known post and writes
#       proxy_health.json (auto-committed); services proven dead are
#       skipped for the run. When a redditez page shows "Failed to Get Post
#       | EmbedEZ" its backend (the part that fetches the post from Reddit
#       for us) is down or unavailable at that moment — a service-side
#       failure, detected per post — and the post falls through to the next
#       service.
#       If every proxy fails for a post, the round-12 native RSS path is
#       used unchanged. PROXY_MEDIA=0 disables the proxy path.
#   13. (round 13) YouTube posts also send a SECOND, plain message
#       containing ONLY the YouTube link (Discord's official preview) after
#       the card lands — waits for the first post (YOUTUBE_LINK_MESSAGE=0
#       disables; the card's own thumb + button stay).
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

def _env_flag(name: str, default: str) -> bool:
    """Env bool: anything in 0/false/no/off/"" is False, everything else True."""
    return os.getenv(name, default).strip().lower() not in ("0", "false", "no", "off", "")


# YouTube: default = thumbnail + animated starwardspark3 button (deterministic,
# no third-party transcoder in the hot path). Set YOUTUBE_MEDIA_EMBED=1 to ALSO
# try to play the video via seaof.glass (quartz) — range-checked with 1 retry,
# degrades to thumbnail + button automatically.
YOUTUBE_MEDIA_EMBED = _env_flag("YOUTUBE_MEDIA_EMBED", "0")
YOUTUBE_MP4_TEMPLATE = "https://seaof.glass/yt/{video_id}.mp4"

# FULL MODE only: include the OP's (stickied first, else first top-level)
# comment in the card.
INCLUDE_OP_COMMENT = _env_flag("REDDIT_OP_COMMENT", "1")
OP_COMMENT_MAX_CHARS = 500

# Test tools (round 12):
#   TEST_POST_ID=<sub>/<post_id>  -> process exactly that post (bypasses feed)
#   DRY_RUN=1                     -> build + log payloads, never touch Discord/cache
TEST_POST_ID = os.getenv("TEST_POST_ID", "").strip()
DRY_RUN = os.getenv("DRY_RUN", "0").strip().lower() in ("1", "true", "yes", "on")

# Discohook share-link preview (public API, no key — see the function).
DISCOHOOK_PREVIEW = _env_flag("DISCOHOOK_PREVIEW", "1")
DISCOHOOK_SHARE_ENDPOINT = "https://discohook.app/api/v1/share"
DISCOHOOK_SHARE_TTL = 7 * 24 * 3600  # 7 days (API max: 28)
DISCOHOOK_USER_AGENT = "python:uesu.news-feed-embed:v3 (discohook share preview)"

# ---------------------------------------------------------------------------
# ■ PROXY MEDIA SERVICES (round 13) — see testing area/reddit_proxy.py
# ---------------------------------------------------------------------------
# Native-mode card media now comes from the public proxy services FIRST:
# redditez.com (EmbedEZ) -> vxreddit.com -> embeddit.deltandy.me, in that
# priority order. The winning service's own URLs are used verbatim in the
# card (full-res photos, every gallery photo, videos WITH audio, GIFs).
PROXY_MEDIA = _env_flag("PROXY_MEDIA", "1")        # '0' disables the proxy path entirely
YOUTUBE_LINK_MESSAGE = _env_flag("YOUTUBE_LINK_MESSAGE", "1")
# '0' stops the SECOND plain YouTube-link message (the card's own YouTube
# thumb + button are unaffected).

try:
    import reddit_proxy
except Exception as _proxy_import_error:
    # A missing/corrupt module must never break the run — the native RSS
    # media path (round 12) still works on its own.
    reddit_proxy = None
    logging.warning(f"reddit_proxy module unavailable — native media only: {_proxy_import_error}")

_proxy_health = None   # per-run warm-up result (set in main(), read in resolve_post_media)

# Native reddit video ladder: v.redd.it DASH_<q>.mp4 files are self-contained
# mp4s (h264 + AAC). 404s answer instantly, so the ladder is cheap.
DASH_QUALITIES = (720, 1080, 480, 360)

# Feed-token .json attempt: anonymous .json is ~1 req/min from datacenters, so
# this is the polite sleep before each attempt (lower it ONLY if your token
# reliably works on .json).
FEEDTOKEN_JSON_STAGGER = int(os.getenv("FEEDTOKEN_JSON_STAGGER", "65"))

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
    r"""https?://(?:www\.)?(?:youtube\.com/(?:watch\?[^"'<>)\]\s]*v=|shorts/|live/)[^"'<>)\]\s]*"""
    r"""|youtu\.be/[^"'<>)\]\s]+)""",
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
    # Drop lines that are ONLY a redd.it media URL (the RSS content inlines
    # the post's images as links; they belong in the media gallery, not text)
    # or ONLY a leftover [link]/[comments] nav label (RSS / redlib footers).
    lines = [ln for ln in lines if not (ln.startswith("http") and "redd.it/" in ln)]
    lines = [ln for ln in lines if ln.lower() not in ("link", "comments", "[link]", "[comments]")]
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
    # limit=25: we need the TOP-LEVEL comments (data[1]) for the OP comment.
    url = f"https://oauth.reddit.com/comments/{post_id}.json?limit=25&raw_json=1"
    headers = {"User-Agent": REDDIT_API_USER_AGENT}
    token = await get_oauth_token(session) if use_oauth else None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    elif not _feedtoken_json_failed and REDDIT_FEED_TOKEN:
        # Workaround attempt: the personal feed token on a .json endpoint.
        # Anonymous .json is 403 from datacenters; the token MIGHT lift it.
        url = (f"https://www.reddit.com/comments/{post_id}.json"
               f"?limit=25&raw_json=1&feed={REDDIT_FEED_TOKEN}")
        headers = dict(BROWSER_HEADERS)
        await asyncio.sleep(FEEDTOKEN_JSON_STAGGER)  # anonymous tier ~1 req/min
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
        try:
            post["_top_comments"] = [
                c for c in (data[1].get("data", {}).get("children") or [])
                if isinstance(c, dict) and c.get("data", {}).get("body")
            ]
        except Exception:
            post["_top_comments"] = []
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
    # Native ladder FIRST: v.redd.it DASH_<q>.mp4 = self-contained mp4
    # (h264 + AAC, WITH audio) straight from Reddit — no proxy, no sig, no
    # expiry. (The signed packaged-media.redd.it masters expire in hours.)
    for quality in DASH_QUALITIES:
        dash = f"https://v.redd.it/{vid}/DASH_{quality}.mp4"
        ok, size = await media_url_ok(session, dash, timeout=30, video=True)
        if ok:
            logging.info(f"video url OK via native v.redd.it DASH_{quality} ({size} bytes).")
            return dash
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
    Slug-prefixed preview names (<postslug>-v0-<id>.jpg) are reduced to the
    bare <id>.jpg first — i.redd.it only serves the bare file id.
    Returns the candidate URL or None.
    """
    m = re.match(r"https?://preview\.redd\.it/([\w.-]+\.(?:jpe?g))\?", url or "", re.I)
    if not m:
        return None
    return f"https://i.redd.it/{_reddit_media_key(m.group(1))}"


def extract_vreddit_id(text: str | None) -> str | None:
    m = VREDDIT_RE.search(text or "")
    return m.group(1) if m else None


def extract_redgifs_url(text: str | None) -> str | None:
    m = REDGIFS_RE.search(text or "")
    if not m:
        return None
    url = f"https://media.redgifs.com/{m.group(1)}.mp4"
    return url


def _is_external_preview(url: str | None) -> bool:
    """external-preview.redd.it = screenshots of EXTERNAL media (mostly
    YouTube embeds). They are video byproducts, not post photos."""
    return bool(url) and "external-preview.redd.it" in url


# ---------------------------------------------------------------------------
# ■ NATIVE MODE MEDIA EXTRACTION (round 12)
# ---------------------------------------------------------------------------
REDDIT_MEDIA_URL_RE = re.compile(
    r"""https?://(?:i\.redd\.it|preview\.redd\.it|external-preview\.redd\.it)"""
    r"""/[\w.-]+\.(?:jpe?g|png|gif|webp)(?:\?[^"'<>\s]*)?""",
    re.I,
)


def _reddit_media_key(url: str) -> str:
    """Group key so all renditions of ONE photo collapse to a single item:
    preview.redd.it/<slug>-v0-<id>.png  and  i.redd.it/<id>.png  -> <id>.png
    """
    base = url.split("?", 1)[0].rsplit("/", 1)[-1].lower()
    return re.sub(r"^.+-v\d+-", "", base)


def extract_native_media(content_html: str | None) -> list[dict]:
    """
    ALL redd.it media from the RSS content HTML, in post order, one item per
    photo with its BEST rendition: i.redd.it (unsigned, full-res) > the
    signed preview URL with the largest ?width=. external-preview.redd.it
    thumbs are kept here and dropped by the caller when a video resolves.
    """
    if not content_html:
        return []
    best: dict[str, tuple[int, int, str, str]] = {}
    for order, m in enumerate(REDDIT_MEDIA_URL_RE.finditer(content_html)):
        url = m.group(0).rstrip(".,;")
        host = url.split("/")[2].lower()
        key = _reddit_media_key(url)
        ext = key.rsplit(".", 1)[-1]
        kind = "gif" if ext == "gif" else "image"
        score = 0
        if host == "i.redd.it" and "?" not in url:
            score += 100000  # unsigned full-res wins
        wm = re.search(r"[?&]width=(\d+)", url)
        if wm:
            score += int(wm.group(1))
        prev = best.get(key)
        if prev is None or score > prev[0]:
            best[key] = (score, order, kind, url)
    items = sorted(best.values(), key=lambda t: t[1])
    out = []
    for _, _, kind, u in items:
        if kind == "image":
            # Signed preview jpg/jpeg -> unsigned full-res i.redd.it
            # (verified 2026-09-15; PNGs are never swapped — i.redd.it 404s).
            swapped = i_reddit_swap(u)
            if swapped:
                u = swapped
        out.append({"kind": kind, "url": u})
    return out


# ---------------------------------------------------------------------------
# ■ OP COMMENT (FULL MODE, round 12)
# ---------------------------------------------------------------------------
def extract_op_comment(post_json: dict) -> dict | None:
    """
    Finds the OP's top-level comment (stickied first, else the first
    top-level comment by the post author). Returns
    {"text", "permalink", "stickied"} or None.
    """
    top = post_json.get("_top_comments") or []
    author = post_json.get("author")
    if not top or not author:
        return None

    def _finish(d: dict) -> dict | None:
        body = strip_html(d.get("body"))
        if not body:
            return None
        permalink = (f"https://www.reddit.com{post_json.get('permalink', '').rstrip('/')}"
                     f"/comment/{d.get('id', '')}/")
        return {"text": body, "permalink": permalink, "stickied": bool(d.get("stickied"))}

    fallback = None
    for c in top:
        d = c.get("data") if isinstance(c, dict) else None
        if not d or d.get("author") != author or not (d.get("body") or "").strip():
            continue
        if d.get("stickied"):
            return _finish(d)
        if fallback is None:
            fallback = d
    return _finish(fallback) if fallback else None


def op_comment_text(op: dict) -> str:
    """Single-line card text: label + capped comment + full-comment link."""
    t = op["text"].strip()
    if len(t) > OP_COMMENT_MAX_CHARS:
        cut = t[:OP_COMMENT_MAX_CHARS]
        cut = cut.rsplit(" ", 1)[0].rstrip(",;:—-") + "…"
    else:
        cut = t
    label = "💬 OP comment" + (" (stickied)" if op.get("stickied") else "")
    return f"**{label}:** {cut} — [full comment]({op['permalink']})"


# ---------------------------------------------------------------------------
# ■ REDLIB GALLERY ENRICHMENT (round 12, best-effort, NATIVE MODE)
# ---------------------------------------------------------------------------
# Reddit RSS does NOT expose gallery images for multi-image posts (they live
# in the post JSON's media_metadata, which is 403-walled from datacenters —
# verified in the 2026-09-15 workflow log: "post JSON HTTP 403 — native
# mode"). Single-image posts DO carry their image link in the RSS content.
# Redlib post pages render the full gallery, so as a fallback lottery (the
# SAME instances as the feed fallback) we fetch the post page and harvest
# every redd.it media URL in the post area. All instances are probed in
# parallel; first success wins; if none answer, the single-thumbnail card
# is kept (no error, no retry).

REDDIL_POST_TITLE_RE = re.compile(r"<h1[^>]*post_title[^>]*>", re.I)


def _redlib_post_area(page_html: str) -> str:
    """HTML slice of the POST AREA (post title -> first comment) so sidebar,
    related posts and comment thumbnails can't leak into the harvest.
    Prefers the post_content element when the theme has one; the cut at the
    first comment is made on the tag boundary (not mid-tag)."""
    m = REDDIL_POST_TITLE_RE.search(page_html)
    if m:
        rest = page_html[m.end():]
        close = rest.find("</h1>")
        page_html = rest[close + 5:] if close != -1 else rest
    start = re.search(r'<(?:div|section)\s+class="post_content', page_html, re.I)
    if start:
        page_html = page_html[start.start():]
    for marker in ('id="comment-', 'class="comment"', '<section class="comments"'):
        idx = page_html.lower().find(marker.lower())
        if idx != -1:
            lt = page_html.rfind("<", 0, idx)
            page_html = page_html[:lt if lt != -1 else idx]
            break
    return page_html


def extract_redlib_gallery(page_html: str | None) -> list[dict]:
    """
    Harvest redd.it media from a redlib post page (post area only), then
    apply the same dedupe/best-rendition rules as extract_native_media.
    """
    if not page_html:
        return []
    return extract_native_media(_redlib_post_area(page_html))


def base_from_redlib_page(page_html: str | None, path: str) -> dict | None:
    """
    Round 12c: native base for a TEST POST when the post JSON is unavailable
    AND the post is not in the current RSS feed — title/author/body/media
    links scraped from a redlib post page (post area only). Best-effort:
    returns None for bot-challenge pages or unparseable layouts.
    """
    if not page_html:
        return None
    area = _redlib_post_area(page_html)
    tm = re.search(r"<h1[^>]*post_title[^>]*>.*?<a[^>]*>([^<]+)</a>", page_html, re.S | re.I)
    title = html_lib.unescape(tm.group(1)).strip() if tm else ""
    if not title:
        return None
    author = "unknown"
    am = re.search(r'class="post_author[^"]*"[^>]*>\s*(?:<[^>]+>\s*)?u?/?\s*([A-Za-z0-9_]{2,20})',
                   page_html, re.I)
    if am:
        author = am.group(1)
    og = (re.search(r'property="og:image"\s+content="([^"]+)"', page_html, re.I) or
          re.search(r'content="([^"]+)"\s+property="og:image"', page_html, re.I))
    return {
        "title": title[:400],
        "author": author,
        "content_html": area,
        "thumb": og.group(1) if og else None,
        "body": clean_rss_body(area),
        "vred_id": extract_vreddit_id(area),
        "redgifs_url": extract_redgifs_url(area),
        "youtube_url": extract_youtube_url(area),
    }

async def _fetch_post_rss(session: aiohttp.ClientSession, path: str):
    """
    Round 12e: the post's OWN RSS feed (/r/<sub>/comments/<id>/.rss).
    Works for ANY post age — unlike the combined feed, which only carries
    the newest 100 entries across all subreddits. The post itself is an
    entry whose link is its permalink; comment entries are ignored by the
    caller's permalink match.
    """
    for instance in REDDIT_RSS_INSTANCES:
        url = f"{instance}{path}.rss"
        if REDDIT_FEED_TOKEN and "reddit.com" in instance:
            url += f"?feed={REDDIT_FEED_TOKEN}"
        feed = await _fetch_feed(session, url, f"post-rss {instance}")
        if feed:
            return feed
    return None
    
async def fetch_test_post_base(session: aiohttp.ClientSession, path: str,
                               label: str) -> dict | None:
    """
    Round 12c: NATIVE fallback for TEST POST mode (post JSON 403'd / no
    OAuth app). Source 1: the combined RSS feed (post must be inside the
    100-entry window — true for anything from the last day or two).
    Source 2: the redlib post page (same parallel lottery as the gallery
    enrichment). None when neither source has the post.
    """
    target_sub = extract_subreddit(path)
    target_pid = extract_post_id(path)
    feed = await fetch_combined_feed(session)
    if feed:
        # match on subreddit + post id (feed permalinks carry a slug suffix,
        # the test-post path does not)
        for entry in feed.entries:
            p = normalize_reddit_path(str(getattr(entry, "link", "")))
            if not p:
                continue
            if (extract_post_id(p) == target_pid
                    and (extract_subreddit(p) or "").lower() == (target_sub or "").lower()):
                logging.info(f"[{label}] test post found in the RSS feed — "
                             f"native base built from it.")
                return entry_to_base_data(entry)
    logging.info(f"[{label}] test post not in the combined feed window — "
                 f"trying its own RSS feed...")
    post_feed = await _fetch_post_rss(session, path)
    if post_feed:
        for entry in post_feed.entries:
            p = normalize_reddit_path(str(getattr(entry, "link", "")))
            if not p:
                continue
            if (extract_post_id(p) == target_pid
                    and (extract_subreddit(p) or "").lower() == (target_sub or "").lower()):
                logging.info(f"[{label}] test post found in its own RSS feed — "
                             f"native base built from it.")
                return entry_to_base_data(entry)
    logging.info(f"[{label}] not in its own RSS feed either — "
                 f"trying the redlib post page...")
    pages = await asyncio.gather(
        *[_fetch_redlib_post_page(session, inst, path) for inst in REDDIT_RSS_INSTANCES]
    )
    for instance, html in zip(REDDIT_RSS_INSTANCES, pages):
        base = base_from_redlib_page(html, path)
        if base:
            logging.info(f"[{label}] test post base via redlib ({instance}).")
            return base
    return None


async def _fetch_redlib_post_page(session: aiohttp.ClientSession, instance: str,
                                  path: str, timeout: int = 10) -> str | None:
    try:
        async with session.get(f"{instance}{path}", headers=BROWSER_HEADERS,
                               timeout=aiohttp.ClientTimeout(total=timeout),
                               allow_redirects=True) as resp:
            if resp.status == 200 and "html" in (resp.headers.get("Content-Type") or "").lower():
                return await resp.text()
    except Exception:
        pass
    return None


async def enrich_gallery_redlib(session: aiohttp.ClientSession, path: str,
                                label: str) -> list[dict]:
    """
    Parallel best-effort redlib gallery harvest. Returns [] when no instance
    answers (caller keeps the single-thumbnail fallback).
    """
    pages = await asyncio.gather(
        *[_fetch_redlib_post_page(session, inst, path) for inst in REDDIT_RSS_INSTANCES]
    )
    for instance, html in zip(REDDIT_RSS_INSTANCES, pages):
        if not html:
            continue
        items = extract_redlib_gallery(html)
        if items:
            logging.info(f"[{label}] gallery via redlib ({instance}) — "
                         f"{len(items)} media item(s).")
            return items
    logging.info(f"[{label}] redlib gallery enrichment failed (all instances) — "
                 f"single thumbnail kept.")
    return []


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
    # maxresdefault 404s for videos without 4K; hqdefault always exists.
    thumb = None
    for name in ("maxresdefault", "hqdefault", "mqdefault"):
        cand = f"https://i.ytimg.com/vi/{vid}/{name}.jpg"
        ok, _ = await media_url_ok(session, cand, timeout=10)
        if ok:
            thumb = cand
            break
    if thumb is None:
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
                             post_json: dict | None,
                             path: str | None = None, label: str = "") -> dict:
    """
    Builds the final media list + meta for one post.
    media = [{"kind": "image"|"gif"|"video", "url": ...}, ...]
    Round-12/13 rules:
      • video posts -> the VIDEO tile ONLY (no first-frame / external thumb)
      • photo posts -> ALL photos, best rendition each (never the 140px thumb)
      • round 13 (native mode): the proxy services (redditez/vxreddit/
        embeddit) are tried FIRST — they provide every gallery photo and
        videos WITH audio; on any failure the round-12 RSS/redlib path runs
      • stats: post JSON (FULL MODE) or the proxy services (round 13 native)
      • external-preview.redd.it screenshots dropped whenever a video resolves
    """
    media: list[dict] = []
    stats = None
    crosspost = None
    op_comment = None
    body = base["body"]
    title = base["title"]
    author = base["author"]
    yt_url = base["youtube_url"]
    vid: str | None = None
    fallback_url: str | None = None
    video_poster: str | None = None

    if post_json:
        # ---- FULL MODE ----
        title = str(post_json.get("title") or title)[:400]
        author = str(post_json.get("author") or author)
        if post_json.get("selftext"):
            body = strip_html(post_json["selftext"]) or body
        stats = {"comments": post_json.get("num_comments", 0),
                 "ups": post_json.get("ups", 0)}
        if INCLUDE_OP_COMMENT:
            op_comment = extract_op_comment(post_json)
        # video id / youtube — resolved BEFORE the photo loop (round 12)
        m = post_json.get("media")
        if isinstance(m, dict) and isinstance(m.get("reddit_video"), dict):
            rv = m["reddit_video"]
            fallback_url = rv.get("fallback_url")
            if fallback_url:
                vid = extract_vreddit_id(fallback_url)
        if not vid:
            vid = base["vred_id"] or extract_vreddit_id(str(post_json.get("url") or ""))
        if not yt_url:
            yt_url = extract_youtube_url(str(post_json.get("selftext") or ""),
                                         str(post_json.get("url") or ""))
        yt_vid_early, _ = extract_youtube_id(yt_url)
        has_video = bool(vid or yt_vid_early or base.get("redgifs_url"))
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
                # external-preview screenshots belong to a video, not the gallery
                if url and not (has_video and _is_external_preview(url)):
                    media.append({"kind": "image", "url": url})
        else:
            for u in photo_urls_from_metadata(mm):
                if not (has_video and _is_external_preview(u)):
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
    else:
        # ---- NATIVE MODE (RSS only) ----
        vid = base["vred_id"]
        yt_vid_early, _ = extract_youtube_id(yt_url)
        has_video = bool(vid or yt_vid_early or base.get("redgifs_url"))

    # ---- round 13: PROXY media services (native mode only) ---------------
    # redditez.com -> vxreddit.com -> embeddit.deltandy.me, in that priority
    # order (see testing area/reddit_proxy.py). The winning service's own
    # URLs are used verbatim: full-res photos, EVERY gallery photo (20 ->
    # 2 containers), videos WITH audio, GIFs. The per-run warm-up
    # (proxy_health.json) skips services already proven dead this run.
    # Any failure here simply falls through to the round-12 native path.
    proxy_media_used = False
    if not post_json and PROXY_MEDIA and reddit_proxy is not None and path:
        proxy = await reddit_proxy.fetch_proxy_post(session, path,
                                                    label=label, health=_proxy_health)
        if proxy:
            proxy_media = []
            for m in proxy["media"]:
                if m["kind"] == "video":
                    # range-check the muxed mp4; if it died, drop the whole
                    # proxy result so the native DASH chain (with audio) runs
                    ok, size = await media_url_ok(session, m["url"], timeout=90, video=True)
                    if ok:
                        logging.info(f"[{label or 'proxy'}] proxy video OK via "
                                     f"{proxy['service']} ({size} bytes).")
                        proxy_media.append(m)
                    else:
                        logging.info(f"[{label or 'proxy'}] {proxy['service']} video URL "
                                     f"failed the range check — native video chain will run.")
                        proxy_media = None
                        break
                else:
                    proxy_media.append(m)
            if proxy_media:
                media = proxy_media
                stats = proxy.get("stats")
                if proxy.get("body"):
                    body = proxy["body"][:MAX_BODY_CHARS]
                proxy_media_used = True
                logging.info(f"[{label or 'proxy'}] card media via {proxy['service']} "
                             f"— {len(media)} item(s).")
            else:
                logging.info(f"[{label or 'proxy'}] no usable proxy media — "
                             f"falling back to the native RSS path.")

    # ---- VIDEO FIRST (round 12): the tile is the video, never a dup thumb
    video_url = None
    if (not proxy_media_used and vid
            and not any(x["kind"] in ("video", "gif") for x in media)):
        video_url = await resolve_video_url(session, vid, fallback_url)

    if video_url:
        media.append({"kind": "video", "url": video_url})
        # drop the video's own screenshot (external-preview) if one slipped in
        media = [x for x in media
                 if x["kind"] in ("video", "gif") or not _is_external_preview(x["url"])]
    else:
        if proxy_media_used and any(x["kind"] == "video" for x in media):
            # round 13: the proxy video tile only (no first-frame / poster dup)
            media = [x for x in media if x["kind"] in ("video", "gif")]
        elif not post_json:
            # ---- NATIVE MODE media (no reddit video resolved) ----
            if base.get("redgifs_url"):
                ok, _ = await media_url_ok(session, base["redgifs_url"], timeout=30, video=True)
                if ok:
                    media.append({"kind": "video", "url": base["redgifs_url"]})
            if not any(x["kind"] == "video" for x in media):
                # ALL photos from the RSS content, best rendition each
                native_items = extract_native_media(base.get("content_html"))
                logging.info(f"[{label or 'native'}] native media in RSS content: "
                             f"{len(native_items)} url(s).")
                for p in native_items:
                    if has_video and _is_external_preview(p["url"]):
                        continue  # it's the video's screenshot
                    if p["kind"] == "image":
                        swap = i_reddit_swap(p["url"])
                        if swap:
                            ok, _ = await media_url_ok(session, swap, timeout=15)
                            if ok:
                                p["url"] = swap
                                logging.info(f"photo via i.redd.it full-res swap ({swap}).")
                    media.append(p)
            if not media and path:
                # Multi-image GALLERY posts: the RSS content carries no image
                # links (single-image posts do) — best-effort redlib harvest
                # of the post page (parallel, ~10s worst case, no retry).
                media = await enrich_gallery_redlib(session, path, label or "gallery")
            if not media and base.get("thumb"):
                # legacy fallback: the feed's single thumbnail
                thumb = base["thumb"]
                if ".gif" in thumb:
                    media.append({"kind": "gif", "url": thumb})
                else:
                    swap = i_reddit_swap(thumb)
                    if swap:
                        ok, _ = await media_url_ok(session, swap, timeout=15)
                        if ok:
                            media.append({"kind": "image", "url": swap})
                        else:
                            media.append({"kind": "image", "url": thumb})
                    else:
                        media.append({"kind": "image", "url": thumb})
        elif video_poster and not media:
            # FULL MODE, video chain failed -> first frame (never a silent video)
            media.append({"kind": "image", "url": video_poster})
            logging.info("video unavailable -> using first-frame poster + button.")

    # youtube tile / thumbnail (both modes)
    yt_vid, yt_live = extract_youtube_id(yt_url)
    if yt_vid:
        yt_media_url, yt_thumb = await resolve_youtube_media(session, yt_vid, yt_live)
        if yt_media_url and not any(x["kind"] == "video" for x in media):
            media.append({"kind": "video", "url": yt_media_url})
        if not any(x["kind"] == "video" for x in media):
            # thumbnail + button (round-12 default): the YT thumb is the
            # canonical preview — replace external screenshots, add if absent
            media = [x for x in media if not _is_external_preview(x["url"])]
            if not any(x["kind"] == "image" for x in media):
                media.append({"kind": "image", "url": yt_thumb})

    media = media[:MAX_GALLERIES * MEDIA_PER_GALLERY]
    return {
        "title": title,
        "author": author,
        "body": body[:MAX_BODY_CHARS] + ("…" if len(body) > MAX_BODY_CHARS else ""),
        "media": media,
        "stats": stats,
        "crosspost": crosspost,
        "op_comment": op_comment,
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

    # Char budget: Discord caps TOTAL text at 4000 across all components.
    op_line = op_comment_text(data["op_comment"]) if data.get("op_comment") else ""
    body_budget = max(300, 3800 - len(header) - len(op_line) - len(stats_line))
    body_out = data["body"][:body_budget]
    if len(data["body"]) > body_budget:
        body_out = body_out.rsplit(" ", 1)[0].rstrip() + "…"

    def gallery(items: list) -> dict:
        return {"type": 12, "items": [{"media": {"url": m["url"]}} for m in items]}

    if len(media) > MEDIA_PER_GALLERY:
        first, second = media[:MEDIA_PER_GALLERY], media[MEDIA_PER_GALLERY:]
        container1 = {"type": 17, "accent_color": 16729344, "components": [
            {"type": 10, "content": header},
        ]}
        if body_out:
            container1["components"].append({"type": 10, "content": body_out})
        if op_line:
            container1["components"].append({"type": 10, "content": op_line})
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
    if body_out:
        inner.append({"type": 10, "content": body_out})
    if op_line:
        inner.append({"type": 10, "content": op_line})
    if media:
        inner.append({"type": 14, "divider": True, "spacing": 1})
        inner.append(gallery(media))
    inner.append({"type": 10, "content": stats_line})
    inner.append({"type": 14, "divider": True, "spacing": 1})
    inner.append(row)
    return {"flags": IS_COMPONENTS_V2,
            "components": [{"type": 17, "accent_color": 16729344, "components": inner}]}


# ---------------------------------------------------------------------------
# ■ DISCOHOOK SHARE-LINK PREVIEW (optional, keyless, round 12)
# ---------------------------------------------------------------------------
async def create_discohook_share(session: aiohttp.ClientSession, payload: dict,
                                 label: str) -> str | None:
    """
    Creates a public Discohook share link (discohook.app) that renders the
    EXACT card we just posted — handy for verifying in the browser before
    promoting. Keyless public API (POST /api/v1/share), best-effort: any
    failure only logs, posting is never blocked.

    PRIVACY: the share data contains ONLY the public card payload. NO
    `targets` are sent, so the webhook URL (and any token) never leaves this
    repo. Share IDs are reused after the TTL, so treat links as 7-day temp.
    """
    if not DISCOHOOK_PREVIEW:
        return None
    query_data = {"version": "d2", "messages": [{"data": payload}]}
    try:
        async with session.post(
            DISCOHOOK_SHARE_ENDPOINT,
            json={"data": query_data, "ttl": DISCOHOOK_SHARE_TTL},
            headers={"User-Agent": DISCOHOOK_USER_AGENT},
            timeout=aiohttp.ClientTimeout(total=20),
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                url = data.get("url")
                logging.info(f"Discohook preview for {label}: {url}")
                return url
            logging.warning(f"Discohook share HTTP {resp.status} for {label} — preview skipped.")
    except Exception as e:
        logging.warning(f"Discohook share error for {label} — preview skipped: {e}")
    return None


def test_post_entries(now: float) -> list:
    """
    TEST_POST_ID=<subreddit>/<post_id> -> one synthetic entry so a specific
    post can be rebuilt on demand (workflow_dispatch input `test_post`).
    Bypasses the feed and the dedup cache on purpose (re-testing is the
    point). Data source: post JSON when reachable (FULL MODE); otherwise
    the RSS feed entry / redlib post page (round 12c native fallback).
    """
    parts = TEST_POST_ID.split("/", 1)
    sub_name, pid = (parts + [""])[:2] if len(parts) < 2 else parts
    sub = _subreddit_by_name(sub_name) if sub_name else None
    if not sub or not pid:
        logging.error(f"TEST_POST_ID: '{TEST_POST_ID}' — use <subreddit>/<post_id>, "
                      f"e.g. AnantaLeaks/1wgvcz7 (subreddit must be in SUBREDDITS).")
        return []
    path = f"/r/{sub}/comments/{pid}/"
    return [(sub, path, f"{sub}_{pid}", now, now, None)]


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
        # ---- round 13: proxy warm-up (writes proxy_health.json) ----------
        global _proxy_health
        if PROXY_MEDIA and reddit_proxy is not None:
            _proxy_health = await reddit_proxy.proxy_warmup(session)
        else:
            logging.info("Proxy media off (PROXY_MEDIA=0 or module missing) — "
                         "native media only.")

        # ---- TEST POST mode (round 12): rebuild one specific post --------
        if TEST_POST_ID:
            logging.info(f"TEST POST mode: {TEST_POST_ID} (dry_run={DRY_RUN}) — "
                         f"feed + dedup cache bypassed on purpose.")
            new_posts = test_post_entries(now)
        else:
            # ---- PRIMARY: one combined request for all subreddits ---------
            combined = await fetch_combined_feed(session)
            new_posts = []  # (subreddit, path, unique_key, published_ts, activity_ts, entry)

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
            if entry is not None:
                base = entry_to_base_data(entry)
                post_json = await fetch_post_json(session, extract_post_id(path) or "",
                                                  use_oauth=use_oauth)
            else:
                # TEST POST mode: no RSS entry (feed bypassed on purpose).
                # Try the post JSON (FULL MODE); when JSON is unavailable
                # (native mode), build the base from the RSS feed entry or
                # the redlib post page (round 12c).
                post_json = await fetch_post_json(session, extract_post_id(path) or "",
                                                  use_oauth=use_oauth)
                if post_json:
                    st = str(post_json.get("selftext") or "")
                    base = {
                        "title": str(post_json.get("title") or "")[:400],
                        "author": str(post_json.get("author") or "unknown"),
                        "content_html": st,
                        "thumb": None,
                        "body": strip_html(st),
                        "vred_id": extract_vreddit_id(st) or extract_vreddit_id(str(post_json.get("url") or "")),
                        "redgifs_url": extract_redgifs_url(st),
                        "youtube_url": extract_youtube_url(st, str(post_json.get("url") or "")),
                    }
                else:
                    base = await fetch_test_post_base(session, path, TEST_POST_ID)
                    if not base and PROXY_MEDIA and reddit_proxy is not None:
                        # round 13: build a minimal base from a proxy service
                        # (title/author/body) so the test post still works
                        # when no RSS/redlib source has the post — media is
                        # then resolved from the same service in
                        # resolve_post_media.
                        proxy = await reddit_proxy.fetch_proxy_post(session, path,
                                                                    label=TEST_POST_ID,
                                                                    health=_proxy_health)
                        if proxy and proxy.get("title"):
                            base = {
                                "title": str(proxy["title"])[:400],
                                "author": proxy.get("author") or "unknown",
                                "content_html": proxy.get("body") or "",
                                "thumb": None,
                                "body": proxy.get("body") or "",
                                "vred_id": None,
                                "redgifs_url": None,
                                "youtube_url": extract_youtube_url(proxy.get("body") or ""),
                            }
                            logging.info(f"[{TEST_POST_ID}] test post base built from "
                                         f"proxy service {proxy['service']}.")
                    if not base:
                        logging.error(f"TEST POST {TEST_POST_ID}: post JSON unavailable "
                                      f"(native mode), and the post is neither in the "
                                      f"combined feed (100-entry window), its own RSS "
                                      f"feed, any redlib instance, nor any proxy "
                                      f"service (redditez/vxreddit/embeddit) — cannot "
                                      f"build the test post. Add REDDIT_CLIENT_ID/"
                                      f"SECRET secrets for reliable testing.")
                        continue

            try:
                data = await resolve_post_media(session, base, post_json,
                                                path=path, label=unique_key)
                posted_ts = int(max(published_ts, activity_ts))
                payload = build_v3_payload(subreddit, data, reddit_url, posted_ts)

                if DRY_RUN:
                    kinds = ",".join(sorted({m["kind"] for m in data["media"]})) or "text"
                    mode = "full" if data["full_mode"] else "native"
                    logging.info(f"DRY RUN (Discord NOT touched): {unique_key} "
                                 f"(media={kinds} | {mode} | {len(data['media'])} item(s))")
                    logging.info(f"DRY RUN payload for {unique_key}:\n"
                                 f"{json.dumps(payload, indent=2, ensure_ascii=False)}")
                    if data.get("youtube_url") and YOUTUBE_LINK_MESSAGE:
                        logging.info(f"DRY RUN 2nd message for {unique_key} "
                                     f"(YouTube link only): {data['youtube_url']}")
                    continue

                target_url = f"{webhook_url}?with_components=true"
                async with session.post(target_url, json=payload,
                                        timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status in (200, 204):
                        posted.add(unique_key)
                        kinds = ",".join(sorted({m["kind"] for m in data["media"]})) or "text"
                        mode = "full" if data["full_mode"] else "native"
                        logging.info(f"Reddit V3 Posted: {unique_key} (media={kinds} | {mode} | "
                                     f"{len(data['media'])} item(s))")
                        await create_discohook_share(session, payload, unique_key)
                        # round 13: YouTube posts get a SECOND, plain message
                        # containing ONLY the YouTube link (Discord shows the
                        # official preview for a bare link). It waits for the
                        # card above to land first; the card's own YouTube
                        # thumb + animated button stay as they are.
                        if data.get("youtube_url") and YOUTUBE_LINK_MESSAGE:
                            try:
                                async with session.post(
                                    webhook_url,
                                    json={"content": data["youtube_url"]},
                                    timeout=aiohttp.ClientTimeout(total=15),
                                ) as yt_resp:
                                    if yt_resp.status in (200, 204):
                                        logging.info(f"YouTube link message posted: "
                                                     f"{data['youtube_url']}")
                                    else:
                                        logging.error(f"YouTube link message "
                                                      f"HTTP {yt_resp.status}: "
                                                      f"{(await yt_resp.text())[:200]}")
                            except Exception as yt_e:
                                logging.error(f"YouTube link message failed: {yt_e}")
                            await asyncio.sleep(1.0)
                        await asyncio.sleep(1.5)
                    else:
                        body = await resp.text()
                        logging.error(f"Discord error {resp.status} for {unique_key}: {body}")
            except Exception as e:
                logging.error(f"Failed building/posting {unique_key}: {e}")

    if DRY_RUN:
        logging.info("DRY RUN finished: cache NOT saved, Discord NOT touched.")
    else:
        save_posted(posted)
        logging.info("Reddit V3 Monitor execution finished.")


if __name__ == "__main__":
    asyncio.run(main())
