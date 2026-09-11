# News Feed Embed — X (Twitter) + Reddit RSS → Discord Monitor (Multi-Webhook Edition)

A lightweight, **100% serverless** bot that monitors public **X (Twitter)** accounts and **subreddits**
via RSS mirrors, then posts new items to **different Discord channels** (one webhook per account/subreddit)
with rich media embeds, clickable link-style buttons, and automatic **English translation** for
non-English tweets.

No bot token. No gateway. No server. Just **GitHub Actions + Discord Webhooks**.

---

## 🌟 Credits & Acknowledgments

This project stands on the shoulders of these amazing open-source projects and free services —
please support them:

| Project / Service | What it's used for | Links |
|---|---|---|
| **News-Flash-Bot** by [@cold-logic5](https://github.com/cold-logic5) | The original repository this project is based on (RSS → Discord webhook architecture) | [GitHub repo](https://github.com/cold-logic5/News-Flash-Bot) · [Author](https://github.com/cold-logic5) |
| **Nitter** by [@zedeus](https://github.com/zedeus) | Free & open-source, privacy-focused X/Twitter front-end providing the RSS feeds | [GitHub](https://github.com/zedeus/nitter) · [nitter.net](https://nitter.net/) · [nitter.perennialte.ch](https://nitter.perennialte.ch/) · [xcancel.com](https://xcancel.com/) · 💖 [Donate via Liberapay](https://liberapay.com/zedeus) |
| **FxTwitter / FxEmbed** by [@isovel](https://github.com/isovel) | Rich X/Twitter embeds (auto-unfurl) + the free API used for media, stats, translation, GIF re-rendering and the video proxy | [fxtwitter.com](https://fxtwitter.com) · [api.fxtwitter.com](https://api.fxtwitter.com) · [GitHub](https://github.com/isovel) · 💖 [Sponsor isovel](https://github.com/sponsors/isovel) |
| **EmbedEZ** | Rich Reddit embeds (redditez.com mirror) + the provider API used by Reddit V2 | [embedez.com](https://embedez.com/) · [redditez.com](https://www.redditez.com) · [API docs](https://embedez.com/docs) |
| **Embeddit** by [@DeltAndy123](https://github.com/DeltAndy123) | Alternative Reddit embed mirror (credited — its button was removed in the 2026-09-11 trim) | [GitHub](https://github.com/DeltAndy123/Embeddit) · [embeddit.deltandy.me](https://embeddit.deltandy.me) |
| **vxReddit** by [@dylanpdx](https://github.com/dylanpdx) | Alternative Reddit embed mirror (credited — its button was removed in the 2026-09-11 trim) | [GitHub](https://github.com/dylanpdx/vxReddit) · [vxreddit.com](https://vxreddit.com) |
| **Redlib** | Reddit front-end mirror used as an RSS fallback source | [redlib.perennialte.ch](https://redlib.perennialte.ch) |
| **cron-job.org** | Free external scheduler that triggers the workflows reliably every 10 minutes | [cron-job.org](https://cron-job.org) |
| **GitHub Actions** | Runs everything on a schedule, for free | — |
| **Discord Webhooks** | Delivers messages to channels statelessly | — |

Huge respect and gratitude to [@cold-logic5](https://github.com/cold-logic5) for the original
architecture, to the Nitter project — if you can, [support zedeus on Liberapay](https://liberapay.com/zedeus) —
and to [@isovel](https://github.com/isovel), creator of FxTwitter/FxEmbed — donations welcome at
[github.com/sponsors/isovel](https://github.com/sponsors/isovel).

---

## ✨ Features

- 🐦 **X/Twitter monitor** with **three interchangeable render engines**:
  - **V1** — classic text + fxtwitter auto-embed, buttons below.
  - **V2** — Discord *Components V2* card (container, gallery, stats), buttons **outside** the card.
  - **V3** — same rich card, but buttons **nested inside** the container.
- 🌐 **Automatic English translation** — non-English tweets show a *"Translated from X"* block with the
  original text preserved, via FxTwitter's `/en` translation endpoint (works on V1/V2/V3).
- 🎯 **Multi-webhook routing** — each tracked X account posts to its own Discord channel
  (`WEBHOOK_<ACCOUNT>` secrets), with an optional catch-all fallback webhook.
- 📰 **Reddit monitor** with two engines:
  - **V1** — free, no API key: posts the `redditez.com` link and lets Discord auto-embed it.
    If the thread links to YouTube, the bare YouTube URL is appended on its own line too, so a
    **playable YouTube player** appears next to the reddit embed.
  - **V2** — rich *Components V2* card built from the **EmbedEZ API** (title, media gallery, stats,
    🕐 Discord timestamp).
- 🔘 **Link-style buttons** with emoji support (Unicode **or** custom server emoji IDs). Reddit
  buttons: **Read Post → the original `reddit.com` thread**, **▶️ YouTube** (only when a link is
  detected), **Citlali News**, **Support**.
- 🔗 **Clickable hashtags & mentions (X V2/V3)** — `#tag` → `x.com/hashtag/tag` and `@user` →
  `x.com/user` as masked links, exactly like fxtwitter auto-embeds.
- 🎬 **Smart video handling (X V2/V3)** — Discord's media gallery can't play large video files, so
  every video's **real file size is probed** (HTTP HEAD) before posting. Oversized videos are
  swapped for the biggest **smaller mp4 variant** from FxTwitter's `formats[]` that still fits
  (stays playable!), with a thumbnail + "Watch on X" link as last resort. Resolution is irrelevant —
  it's all about file size (see the live test table below).
- 🕐 **Exact timestamps (V2/V3, X & Reddit)** — every card's stats line ends with a Discord-native
  `<t:…:f>` timestamp; hover/tap for the post's exact date & time.
- 🛡 **Mod-queue safe (Reddit)** — a 48-hour freshness window keyed on the RSS *updated* stamp means
  posts approved from a subreddit's moderator queue hours (or a day) later still get posted —
  they're never left out.
- 📊 **Stats line** — replies/retweets/likes/views (X) or comments/shares/likes/views (Reddit V2).
- 🕙 **Reliable 10-minute automation** via an external cron trigger (GitHub's built-in `schedule` is
  kept only as a backup — it's documented as best-effort and can lag or be skipped).
- 💾 **Self-maintaining memory** — posted IDs are cached in JSON files committed back to the repo by
  `github-actions[bot]`, so nothing is ever posted twice.

---

## 🗂 Repository Contents

```
├── .github/
│   └── workflows/
│       ├── rss_monitor.yml      # X/Twitter monitor (choose V1/V2/V3 inside)
│       └── reddit_monitor.yml   # Reddit monitor (choose V1/V2 inside)
├── main.py                      # X/Twitter — V1 (classic content + fxtwitter embed)
├── main_v2.py                   # X/Twitter — V2 (Components V2, buttons OUTSIDE)
├── main_v3.py                   # X/Twitter — V3 (Components V2, buttons INSIDE)
├── reddit_main.py               # Reddit — V1 (free, redditez auto-embed)
├── reddit_main_v2.py            # Reddit — V2 (Components V2 via EmbedEZ API)
├── posted_tweets.json           # X cache (auto-committed) — start with: []
├── posted_reddit.json           # Reddit cache (auto-committed) — start with: []
├── PRIVACY_POLICY.md            # privacy policy (the bot collects no personal data)
├── TERMS_OF_SERVICE.md          # terms of service / acceptable use
├── requirements.txt             # feedparser, aiohttp, python-dotenv
├── .env.example                 # local testing template
└── .gitignore                   # (keep the posted_*.json force-add exception in workflow)
```

---

# 🐦 X (Twitter) Monitor

## Choosing a version (V1 vs V2 vs V3)

All three do the same job with the same multi-webhook routing and translation — they only differ in
**how the Discord message looks**:

| | `main.py` (V1) | `main_v2.py` (V2) | `main_v3.py` (V3) |
|---|---|---|---|
| Message style | Plain text + fxtwitter link → Discord **auto-unfurls** the embed | Fully custom **Components V2** bordered card (type 17 container + text + media gallery + stats) | Same custom card as V2 |
| Buttons | Action row below the embed | Action row **outside/below** the container | Action row **nested inside** the container |
| Data source | RSS + FxTwitter API (light, lang check only) | RSS + FxTwitter API (full tweet JSON) | RSS + FxTwitter API (full tweet JSON) |
| Custom accent color | n/a | ✅ (per-tweet `color`) | ✅ (per-tweet `color`) |
| Switch to it | `run: python main.py` | `run: python main_v2.py` | `run: python main_v3.py` |

**To switch versions:** open `.github/workflows/rss_monitor.yml` and change the run line:

```yaml
run: python main.py        # V1
# run: python main_v2.py   # V2
# run: python main_v3.py   # V3
```

Commit — done. All three were verified working end-to-end (feeds, translation, per-channel routing,
buttons, and cache commits).

## 🆕 X V2/V3 card behaviors (2026-09-11 update)

* **Clickable hashtags & mentions** — `#tag` → `[#tag](https://x.com/hashtag/tag)`, `@user` →
  `[@user](https://x.com/user)`; bare http(s) links are auto-linked by Discord as before.
  Regex lookbehinds protect URLs like `example.com/path#anchor` and emails like `a@b.com` from being
  linkified by accident.
* **Smart video handling (revised after live testing).** Your tests proved the breakage is about
  **file size, not resolution**:

  | Video | Real size (probed) | Components V2 gallery |
  |---|---|---|
  | 3840×2160 · 24 min | 905 MB | ❌ "image failed to load" |
  | 1920×1080 · 56 min | 578 MB | ⚠️ loads, won't play |
  | 2560×1440 · 5:12 | 405 MB | ❌ "image failed to load" |
  | 2560×1440 · 1:28 | 120 MB | ✅ plays |
  | 3440×1440 · 0:24 | 22 MB | ✅ plays |
  | 2340×1080 · 4:29 | 191 MB | ✅ plays |

  So the scripts now **probe every video's real file size** with an HTTP HEAD request
  (`Content-Length`, with a Range-GET backup) and apply these rules — nothing is forced when the
  size can't be determined:
  * **≤ 256 MB** (`VIDEO_SIZE_LIMIT`, tunable) → video goes in the gallery as-is (confirmed safe zone:
    191 MB works, 405 MB fails).
  * **Over the limit** → the script tries FxTwitter's `formats[]` list (smaller mp4 renditions,
    highest quality first) and probes each; the first that fits is embedded instead, with a
    `🔽 Original video is ~X MB — showing a smaller version (~Y MB)… ▶️ Watch full quality on X`
    note. Example live result: the 905 MB 4K Wuthering video → 1280×720 variant (~135 MB) that
    **plays in Discord**.
  * **Over the limit + no fitting variant** → the video's **thumbnail** appears in the gallery plus
    a `⚠️ Video is ~X MB — ▶️ Watch it on X` note (covers the 56-minute Genshin case).
  * **Size undetectable** → the video is left untouched (never forced) **unless** it's clearly
    risky (> 5 minutes *and* ≥ 1080p — matches every verified failure), in which case it's
    thumbnailed with a watch link. A 2K clip of 1:28 stays in the gallery.
* **Discord timestamp** — the stats line ends with `🕐 <t:epoch:f>` (taken from FxTwitter's
  `created_timestamp`, falling back to `created_at`, then the RSS publish date).
* **Null-safe accent color** — FxTwitter sometimes returns `"color": null`; the card now falls back
  to Twitter blue instead of crashing.

## 🆕 X V2/V3 card behaviors — round 4 (2026-09-11)

Fixes and formats added after real feed runs:

* **Discord `400 {"components": ["0"]}` errors — FIXED.** Root cause: tweets with an **empty body**
  (a repost of a media-only quote post; an X Article) produced a zero-length text component, which
  Discord rejects. Text is now chunked (≤ 1900 chars per component, up to 4 components) and empty
  components are never emitted — so **very long tweets also render now** instead of failing.
* **Quoted posts are rendered.** Tweets quoting another post show:
  `>>> [Quote](url) from **Name** (@user)` + the quoted text + the quoted tweet's own media gallery
  (videos in quotes get the same size/GIF/portrait treatment).
* **X Articles & link cards get their image.** When a tweet has no media, the script fetches the
  tweet's own `x.com` page and reads its OpenGraph image — for X Articles that's the **article
  banner**, for link posts (e.g. `hoyo.link`) it's the **card image**. Fallback: the first external
  link's `og:image` (works for hoyoverse/kurogames pages). Profile pictures are never used, and the
  extra fetch is skipped for normal tweets.
* **GIF support.** X "GIFs" are internally tiny looping mp4s (`tweet_video/*.mp4`). When detected,
  the script swaps in FxTwitter's animated **WebP** rendition
  (`gif.fxtwitter.com/tweet_video/*.webp`), which renders/plays as an image in Discord. That CDN is
  **intermittently down** (Cloudflare 530/1033 — a maintainer-side issue, confirmed live); when it
  doesn't answer, the mp4 is kept, which still plays as a video. Never forced — it self-heals once
  the CDN recovers.
* **Portrait videos that "load but won't play" — FIXED.** Vertical videos (`h > w`, e.g. the 58s
  Jingran showcase) are re-pointed through FxTwitter's embed proxy
  (`api.fxtwitter.com/2/go?url=…`) — the exact URL V1/fxtwitter embeds use, which plays them.
  Landscape videos keep the direct link (already works).
* **`/status/:id` API path.** The screen-name API path (`/<user>/status/:id`) returns **404** for
  reposts of other authors, X Articles, and some newer tweets (verified live); the plain-ID path
  resolves everything. Read Post links now use the **true author** from the payload, so reposts link
  to the original post correctly. Same for the `/en` translation fetch.
* **"↩️ Replying to @user"** small line appears on replies (links to the parent post when known).
* **New animated button emoji** on X *and* Reddit (per your spec): Read Post
  `<a:starwardhmm:1472388018689282261>`, Citlali News `<a:starward11:1439878792653832253>`, Support
  `<a:starwardfans:1509026327548657914>`.
* **Interactive campaign tweets** (multi-photo, e.g. the "mysterious manuscript" Wuthering post) —
  all 4 photos render in the gallery; verified against the live API.

## 🌐 How translation works (all versions)

1. The script fetches the tweet from the FxTwitter API and reads its `lang` field.
2. If it's not English, it re-fetches `https://api.fxtwitter.com/<account>/status/<id>/en`, which
   returns FxTwitter's translated text.
3. The message shows **🌐 Translated from {Language}** then the translation, then an
   **Original text** block with the untranslated tweet. The *Read Post* button points to the `/en`
   fxtwitter page too.
4. If FxTwitter can't translate a specific post, the script gracefully posts the original text instead.
5. `LANGUAGE_NAMES` at the top of each file maps ISO codes (ja, ko, zh, fr, …) to readable names —
   extend it if you track accounts in other languages.

## 🎯 Multi-webhook routing

Every account in `ACCOUNTS` is routed to its own webhook secret:

| Setting | Example |
|---|---|
| `ACCOUNTS` secret | `TYPEII_EN,PomPom_HonkaiSR,Wuthering_Waves,HonkaiNA` |
| Per-account secret name | `WEBHOOK_` + account name **UPPERCASED**, non-alphanumerics → `_` |
| `TYPEII_EN` → | `WEBHOOK_TYPEII_EN` (e.g. `#zzz-news`) |
| `PomPom_HonkaiSR` → | `WEBHOOK_POMPOM_HONKAISR` (e.g. `#hsr-news`) |
| `Wuthering_Waves` → | `WEBHOOK_WUTHERING_WAVES` (e.g. `#wuwa-news`) |
| `HonkaiNA` → | `WEBHOOK_HONKAINA` |
| fallback (optional) | `DISCORD_WEBHOOK_URL` — used for any account without its own secret |

### The workflow (`.github/workflows/rss_monitor.yml`)

```yaml
name: RSS Feed Monitor

on:
  schedule:
    - cron: '*/10 * * * *'   # backup only — GitHub cron is best-effort
  workflow_dispatch:          # allows manual + external-cron triggering

permissions:
  contents: write

jobs:
  check-rss:
    runs-on: ubuntu-latest
    steps:
      - name: Check out repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run RSS Feed Monitor
        env:
          ACCOUNTS: ${{ secrets.ACCOUNTS }}
          DISCORD_WEBHOOK_URL: ${{ secrets.DISCORD_WEBHOOK_URL }}
          WEBHOOK_TYPEII_EN: ${{ secrets.WEBHOOK_TYPEII_EN }}
          WEBHOOK_POMPOM_HONKAISR: ${{ secrets.WEBHOOK_POMPOM_HONKAISR }}
          WEBHOOK_WUTHERING_WAVES: ${{ secrets.WEBHOOK_WUTHERING_WAVES }}
          WEBHOOK_HONKAINA: ${{ secrets.WEBHOOK_HONKAINA }}
        run: python main_v3.py   # ← switch to main.py / main_v2.py here

      - name: Commit and push updated posted_tweets.json cache
        run: |
          git config --local user.email "github-actions[bot]@users.noreply.github.com"
          git config --local user.name "github-actions[bot]"
          git add -f posted_tweets.json
          git diff --quiet && git diff --staged --quiet || (git commit -m "auto: update posted_tweets.json cache" && git push)
```

> Every webhook secret you add must get a matching `WEBHOOK_...` line in the `env:` block —
> that's the one manual step when adding a new account.

## 🔘 Customizing the buttons (all files)

Near the top of each script:

```python
READ_POST_LABEL = "Read Post"
READ_POST_EMOJI = {"name": "📖"}        # Unicode emoji — or None
STATIC_BUTTONS = [
    {"label": "Citlali News", "url": "https://discord.gg/HyrVP9wRXu", "emoji": {"name": "✨"}},
    {"label": "Support",     "url": "https://ko-fi.com/jieunlatte",   "emoji": {"name": "☕"}},
]
```

* Max **5 buttons per row** (Discord limit).
* **Custom server emoji:** type `\:emojiname:` in Discord to get its ID, then use:
  `"emoji": {"id": "123456789012345678", "name": "emojiname", "animated": False}`
  (`animated: True` for GIF emoji). Full custom *pictures* on buttons are not possible — Discord only
  supports label + one emoji.

---

# 📰 Reddit Monitor

Monitors subreddits through RSS (sorted by *new*) and posts each new thread to that subreddit's own
Discord channel.

## V1 vs V2

| | `reddit_main.py` (V1) | `reddit_main_v2.py` (V2) |
|---|---|---|
| Cost | **Free — no API key at all** | Requires an **EmbedEZ API key** (paid credits — see concerns below) |
| Look | Plain message + `redditez.com` link → Discord auto-embeds it (same idea as fxtwitter), plus a bare YouTube link with its own playable embed when detected | Rich **Components V2** card (title, author, media gallery, 💬/🔁/❤️/👁️ stats + 🕐 timestamp, buttons inside) |
| Buttons | Read Post → **original reddit.com thread** · ▶️ YouTube (conditional) · Citlali News · Support | Same set, nested inside the card |
| Switch to it | `run: python reddit_main.py` | `run: python reddit_main_v2.py` |

### Secrets

| Secret | Value |
|---|---|
| `SUBREDDITS` | Comma-separated subreddit names, e.g. `Zenlesszonezeroleaks_` |
| `WEBHOOK_REDDIT_ZENLESSZONEZEROLEAKS_` | Webhook for that sub's channel (rule: `WEBHOOK_REDDIT_` + UPPERCASE name, non-alphanumerics → `_`) |
| `EMBEDEZ_API_KEY` | **V2 only** — from your embedez.com dashboard |
| `DISCORD_WEBHOOK_URL` *(optional)* | Catch-all fallback |

### The workflow (`.github/workflows/reddit_monitor.yml`)

```yaml
name: Reddit Feed Monitor

on:
  schedule:
    - cron: '*/10 * * * *'
  workflow_dispatch:

permissions:
  contents: write

jobs:
  check-reddit:
    runs-on: ubuntu-latest
    steps:
      - name: Check out repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run Reddit Feed Monitor
        env:
          SUBREDDITS: ${{ secrets.SUBREDDITS }}
          DISCORD_WEBHOOK_URL: ${{ secrets.DISCORD_WEBHOOK_URL }}
          EMBEDEZ_API_KEY: ${{ secrets.EMBEDEZ_API_KEY }}
          WEBHOOK_REDDIT_ZENLESSZONEZEROLEAKS_: ${{ secrets.WEBHOOK_REDDIT_ZENLESSZONEZEROLEAKS_ }}
        run: python reddit_main.py   # ← switch to reddit_main_v2.py for the rich card

      - name: Commit and push updated posted_reddit.json cache
        run: |
          git config --local user.email "github-actions[bot]@users.noreply.github.com"
          git config --local user.name "github-actions[bot]"
          git add -f posted_reddit.json
          git diff --quiet && git diff --staged --quiet || (git commit -m "auto: update posted_reddit.json cache" && git push)
```

Create `posted_reddit.json` with `[]` as its initial content (first run posts only the newest thread,
by design).

## 🆕 Reddit behaviors (2026-09-11 update)

* **Buttons were trimmed.** The Embeddit and vxReddit mirror buttons are **gone** (see concerns §6),
  and *Read Post* now points to the **original `https://www.reddit.com/...` permalink** — not the
  redditez mirror. Mirrors stay credited at the top of this README.
* **YouTube posts get a playable embed (V1).** If the thread body links to YouTube (`watch?`,
  `shorts/` or `youtu.be`), the bare YouTube URL is appended on its own line after the redditez
  link — verified to auto-embed a working YouTube player alongside the reddit embed. A conditional
  **▶️ YouTube button** is also added. On V2 the URL appears as a clickable line plus the same
  button (Components V2 messages cannot auto-unfurl links — Discord limitation).
* **Pending-approval / mod-queue posts are never left out.** Subreddits with a moderator queue only
  publish posts to the `new` RSS listing **when approved** — sometimes hours or a day later. Two
  safeguards cover this: the freshness window was widened from 3h to **48h** (`MAX_AGE_SECONDS`), and
  the age check uses the RSS *updated* timestamp whenever it's newer than *published* (an approval
  bumps `updated`). A thread approved "tomorrow" still arrives. If your subs regularly take longer
  than 48h to approve, raise `MAX_AGE_SECONDS` near the top of the script.
* **Reddit V2 fixes** — all EmbedEZ text fields are now HTML-sanitized (their authorized
  `content.title` itself contains raw `<a>`/`<br>` tags, which previously rendered literally), and
  the stats line ends with a 🕐 `<t:…:f>` timestamp (from EmbedEZ `postedDate`, falling back to the
  RSS date).

## ⚠️ Reddit V2 (Components V2) — concerns you should know

The V2 script was rebuilt against the **currently documented** EmbedEZ API, but please read these
points before relying on it:

1. **The API key is not fully free.** The embedez dashboard shows a *credits* balance (fresh accounts
   start around 100 credits; more requires payment, and payments "may take up to 5 minutes to
   process"). **Every new post costs 2 API calls** (one `search` + one `preview`). If you don't want
   to spend credits, just use **Reddit V1** — it needs no key at all.
2. **Documented two-step flow.** V2 uses only the endpoints in the current OpenAPI docs:
   `GET /api/v1/providers/search?url=…` → returns a `key`, then
   `GET /api/v1/providers/preview?search_key=…` with header `Authorization: Bearer <ez_key>`.
   The older unofficial `/providers/combined?q=` endpoint from early docs is **no longer documented**
   and is not used.
3. **Graceful no-key fallback.** Without a valid key, the preview endpoint still returns *public* data
   (author, title, one thumbnail). V2 detects that and posts a **limited card** with a small
   `ℹ️ Limited preview` note instead of skipping the post.
4. **Defensive field parsing.** Media URLs are read from `media[].url` **or** the legacy
   `media[].source.url` shape; HTML in preview titles is stripped automatically. Even so —
5. **EmbedEZ warns the API may break.** Their docs explicitly say *"large changes will be made to the
   API in the future, and these might break the current API."* If posts suddenly fail, read the Actions
   log — it prints the exact API response — and check their release notes/docs for field renames.
6. **The Embeddit / vxReddit buttons were removed (2026-09-11).** A true
   "click to switch embed mirror" rotation is impossible via webhooks — interactive buttons need a
   24/7 bot process answering Discord interactions, incompatible with this stateless design — and the
   always-visible duplicate mirror buttons added clutter without value. The mirrors remain fully
   credited at the top of this README.
7. **HTML is stripped from every text field.** With a valid API key, EmbedEZ's `content.title` itself
   contains HTML (`Posted in <a …>r/sub</a><br>…`) — earlier builds rendered those tags literally in
   the Discord card. All title/description/text fields (authorized *and* public-preview) are
   sanitized now.
8. **Components V2 can't auto-unfurl a bare YouTube link** inside a card (the auto-embed player is a
   V1 behavior Discord only applies to regular message content). V2 therefore shows the YouTube URL
   as a clickable line plus a ▶️ YouTube button; if you want the playable inline player, use
   **Reddit V1**.

## 🔧 Reddit V1 fix (2026-09-11) — why the first run failed

Your first V1 test logged `Could not fetch valid RSS feed for r/*** from any instance.` The cause was
verified live:

| Source (in code order) | Result |
|---|---|
| `redlib.perennialte.ch` | **HTTP 403** — Cloudflare "Just a moment…" challenge |
| `old.reddit.com` | HTTP 200 but an **HTML "Welcome to Reddit" interstitial**, zero RSS entries |
| `www.reddit.com` | ✅ **real Atom feed, 25 entries** — but it wasn't in the source list! |

`reddit_main.py` (and V2) now:
* try **`https://www.reddit.com/r/<sub>/new/.rss` first**, with `old.reddit.com` and redlib as fallbacks;
* **validate** the response actually contains `/comments/` permalinks before accepting it (old.reddit's
  HTML page is now properly rejected);
* **log exactly why each source was skipped**, so future breakage is diagnosable from the Actions log.

If `www.reddit.com` ever starts blocking GitHub's datacenter IPs for you, open the Actions log —
you'll see the per-source reasons — and just reorder/replace entries in `REDDIT_RSS_INSTANCES`.

---

# 🛠 Full Setup Guide

## Step 0 — Make the repo your own (**do NOT fork**)

Forked repos get Actions/schedules disabled and auto-disabled again after ~60 days of inactivity —
your bot would silently stop. Instead:

1. On the source repo: **Code → Download ZIP**, then unzip locally.
2. Create a **brand-new empty repository** on your GitHub account.
3. Click *"uploading an existing file"* and drag in **all** files — including the hidden `.github`
   folder (enable *show hidden files* in your file explorer first!).
4. Commit. Since it's a fresh, non-fork repo, workflow **read/write** permissions work out of the box
   (verify at *Settings → Actions → General → Workflow permissions → Read and write*).

## Step 1 — Create Discord webhooks (one per channel)

For each target channel: *Channel Settings → Integrations → Webhooks → New Webhook → Copy URL.*

## Step 2 — Add repository secrets

*Repo → Settings → Secrets and variables → Actions → New repository secret*, then add the ones you
need from the X and Reddit tables above (`ACCOUNTS`, `WEBHOOK_<ACCOUNT>` per account, `SUBREDDITS`,
`WEBHOOK_REDDIT_<SUB>` per subreddit, `EMBEDEZ_API_KEY` only if using Reddit V2, optional
`DISCORD_WEBHOOK_URL` fallback).

## Step 3 — Reset the caches for a fresh start

Edit `posted_tweets.json` and `posted_reddit.json` to contain just:

```json
[]
```

On the first run the bots post only the **single newest item** per account/subreddit (by design — no
channel flooding).

## Step 4 — Reliable 10-minute automation (external trigger)

GitHub's built-in `schedule:` can lag 15–60 min or skip runs under load, so we replicate the original
author's "Manually run by …" pattern with a free external cron:

1. **Create a PAT:** GitHub → *Settings → Developer settings → Personal access tokens (classic) →
   Generate new token* → check **`workflow`** (and `repo` if private) → copy it.
2. Sign up at [cron-job.org](https://cron-job.org) (free) and create a job **per workflow**:
   * **URL:**
     `https://api.github.com/repos/<YOU>/<REPO>/actions/workflows/rss_monitor.yml/dispatches`
     (and a second job for `reddit_monitor.yml`)
   * **Method:** `POST` · **Crontab:** `*/10 * * * *`
   * **Headers:**
     | Key | Value |
     |---|---|
     | `Authorization` | `token <YOUR_PAT>` |
     | `Accept` | `application/vnd.github+json` |
     | `Content-Type` | `application/json` |
     | `X-GitHub-Api-Version` | `2026-03-10` *(optional, future-proof)* |
   * **Body:** `{"ref":"main"}` (match your default branch name)
3. **Perform test run** → expect `204 No Content` (or `200 OK`), then check the Actions tab for a run
   labeled *Manually run by you*. `401` = bad token/scope; `404` = wrong repo/workflow/branch name.

Keep the in-file `schedule:` cron as a harmless backup — occasional extra *Scheduled* runs are fine.

## Step 5 — Test end-to-end

*Actions → select the workflow → Run workflow*, then check: the right Discord channels got the right
posts, buttons render, and the cache file shows a new `github-actions[bot]` commit.

## (Optional) Render Cron instead of GitHub Actions

Create a **Cron Job** on Render: build `pip install -r requirements.txt`, command
`python main.py` (or any other engine file), schedule `*/10 * * * *`, and add the same env vars there.

---

## 💻 Local Testing

```bash
pip install -r requirements.txt
cp .env.example .env   # then fill in your values
```

`.env` example:

```env
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
ACCOUNTS=TYPEII_EN,PomPom_HonkaiSR,Wuthering_Waves,HonkaiNA
WEBHOOK_TYPEII_EN=https://discord.com/api/webhooks/...
WEBHOOK_POMPOM_HONKAISR=https://discord.com/api/webhooks/...
WEBHOOK_WUTHERING_WAVES=https://discord.com/api/webhooks/...
WEBHOOK_HONKAINA=https://discord.com/api/webhooks/...
SUBREDDITS=Zenlesszonezeroleaks_
WEBHOOK_REDDIT_ZENLESSZONEZEROLEAKS_=https://discord.com/api/webhooks/...
EMBEDEZ_API_KEY=ez_...       # Reddit V2 only
```

Then run any engine: `python main.py` / `python main_v2.py` / `python main_v3.py` /
`python reddit_main.py` / `python reddit_main_v2.py`.

---

## 🚨 Troubleshooting

* **Buttons don't render.** Every webhook POST must use the query param `?with_components=true` —
  Discord *silently drops* components without it (already handled in all scripts; don't remove it).
  Rich-card versions also set the `IS_COMPONENTS_V2` flag (`1 << 15`).
* **`Could not fetch valid RSS feed for @…` / `r/…`** — public mirrors rotate/die. For X, swap
  `RSS_INSTANCES` with currently-live Nitter mirrors; for Reddit, see the *Reddit V1 fix* section and
  read the new per-source log lines.
* **`ValueError: invalid literal for int() with base 16: 'None'`** — old V3 bug when FxTwitter returns
  `"color": null`; fixed via the `accent_from_color()` helper with a safe Twitter-blue default.
* **`Deprecation` / `Node.js 20 is deprecated` warnings in Actions logs** — cosmetic, safe to ignore
  (runs are forced onto Node 24).
* **No run at 10-minute marks** — GitHub's native cron is best-effort; that's why the external
  cron-job.org trigger exists. Also note GitHub auto-disables `schedule:` after 60 days of repo
  inactivity — the cache auto-commits usually count as activity, and the external trigger is immune.
* **Reddit V2 posts "Limited preview" cards** — your `EMBEDEZ_API_KEY` is missing/invalid or out of
  credits; add a valid key (and watch the credit balance), or switch to free V1.
* **First run posts only one item per account** — intentional anti-flood behavior; normal backfill
  starts on subsequent runs.
* **A big video shows as a thumbnail / "smaller version" note (X V2/V3)** — intended behavior:
  the file exceeded the verified ~256 MB Discord gallery limit (e.g. 4K or very long videos). The
  card still plays a smaller rendition, or links out to X when even that is too big. Tune
  `VIDEO_SIZE_LIMIT` at the top of the script if Discord's behavior ever changes.
* **`Discord error 400 ... {"components": ["0"]}`** — old round-3 bug: a tweet with empty body (or
  over-length text) emitted an invalid empty text component. Fixed in round 4 — text is chunked and
  empty components are never sent. If it ever recurs, the Actions log prints the full Discord
  response next to the tweet ID.
* **A GIF shows as a video player instead of an animated image** — `gif.fxtwitter.com` (the WebP
  rendition) is intermittently down (530/1033). The script keeps the mp4 player automatically and
  logs `gif.fxtwitter.com unavailable ... keeping mp4 player`. It self-heals; nothing to do.
* **A portrait/vertical video loads but won't play** — fixed in round 4 by proxying vertical videos
  through `api.fxtwitter.com/2/go?url=…` (the same URL fxtwitter's own embeds use). If another odd
  video misbehaves, check whether the direct twimg link plays when pasted in Discord — if yes, open
  an issue with the tweet ID.
* **EmbedEZ suddenly errors after an update** — expected risk (their docs warn of breaking changes);
  the Actions log prints the raw API response to help adjust field names.

---

## 📄 Final notes

* All engines are independent — mix and match freely (e.g. X on V3, Reddit on V1).
* Legal docs are included: [Privacy Policy](PRIVACY_POLICY.md) · [Terms of Service](TERMS_OF_SERVICE.md)
  (summary: webhook-only and stateless — the bot collects **no** personal data).
* Be nice to the free services this project uses: don't shorten the polling interval below 10 minutes,
  cache stays committed so nothing is fetched/posted twice, and consider donating to Nitter's author.
* All trademarks belong to their respective owners; this project is an unofficial, non-affiliated
  automation tool for personal servers.

---

## 🗒 Changelog

* **2026-09-11 — round 4 (quotes, GIFs, articles, portrait fix):**
  * **Fixed both live `400 {"components": ["0"]}` failures** (empty-text quote post + X Article) —
    text chunking (×4 @ ≤1900) + never emitting empty components; very long tweets now render.
  * **Quoted-post rendering** (`>>> [Quote](url) from **Name** (@user)` + quoted text + quoted
    media, with full video handling on quote media too).
  * **X Article / link-card images** via OpenGraph fetch of the post's `x.com` page (article banner
    / `card_img`), falling back to the shared link's OG image (hoyo.link & co. verified working).
  * **GIF support**: `tweet_video` GIFs render as animated WebP via `gif.fxtwitter.com` when that
    CDN is up; graceful mp4 fallback when it 530s (maintainer-side).
  * **Portrait-video playback fix** via the `api.fxtwitter.com/2/go?url=…` proxy wrapper.
  * **Robust `/status/:id` API path** (the screen-name path 404s on reposts/articles/newer tweets);
    Read Post links use the true author; `/en` translation uses the same path.
  * **"↩️ Replying to"** line on replies; **animated custom emoji** on all buttons (X + Reddit).
* **2026-09-11 — round 3 (smart videos):** X V2/V3 video handling rebuilt after live Discord tests
  proved **file size** (not resolution) decides playability. Each video's real size is now probed by
  HTTP HEAD; oversized (> 256 MB) videos are swapped for a smaller playable FxTwitter `formats[]`
  rendition (905 MB 4K → 135 MB 720p that plays), or thumbnailed with a watch link when nothing
  fits. Unknown sizes are left untouched unless clearly risky (> 5 min **and** ≥ 1080p). Replaces
  the earlier pixel-count rule, which would have wrongly thumbnailed playable 2K clips.
* **2026-09-11 — round 2:**
  * **Reddit (V1 + V2):** Embeddit/vxReddit buttons removed; *Read Post* → original `reddit.com`
    permalink; YouTube link detection (bare playable link on V1, clickable line + ▶️ button on V2);
    **48-hour mod-queue-safe window** keyed on the RSS *updated* stamp so late-approved posts are
    never missed; V2 now strips HTML from **all** EmbedEZ text fields and adds a 🕐 `<t:…:f>`
    Discord timestamp to cards.
  * **X (V2 + V3):** clickable `#hashtags` / `@mentions` (masked x.com links); 🕐 Discord timestamp
    on the stats line; null-safe accent color (`accent_from_color`).
  * **Docs:** added `PRIVACY_POLICY.md` and `TERMS_OF_SERVICE.md`.
* **2026-09-11 — round 1:** Reddit V1 source-order fix (`www.reddit.com` first + feed validation +
  per-source logging); Reddit V2 rebuilt on the documented two-step EmbedEZ flow
  (`search` → `preview`) with graceful public-preview fallback.
* **Earlier:** X V1/V2/V3 engines, multi-webhook routing, `/en` auto-translation, external
  cron-job.org scheduling guide.
