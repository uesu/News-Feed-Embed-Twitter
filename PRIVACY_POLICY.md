# Privacy Policy

**Effective date:** September 11, 2026
**Applies to:** the *News Feed Embed* / *Citlali News* X (Twitter) + Reddit → Discord monitor
("the Service"), an open-source, self-hosted automation tool.

---

## 1. Overview

The Service is a set of Python scripts that run on **your own GitHub repository** (GitHub Actions)
and post new public X/Twitter and Reddit items into **your own Discord channels** via Discord
webhooks. There is no hosted bot account, no gateway connection, no dashboard, and no central server
operated by the author.

**Short version: the Service collects, stores, and transmits no personal data.**

---

## 2. Data the Service Processes

| Data | Where it lives | Why | Shared with anyone? |
|---|---|---|---|
| Post/tweet IDs (e.g. `TYPEII_EN_2098063866303504597`) | `posted_tweets.json` / `posted_reddit.json` **inside your own repository**, committed by `github-actions[bot]` | Deduplication only — prevents posting the same item twice | No |
| Webhook URLs & API keys | GitHub **encrypted repository secrets** in *your* repository | Authentication to Discord / EmbedEZ | No (GitHub stores them; they are never logged or transmitted elsewhere) |
| Public post content (titles, text, media URLs, stats) | Processed **in memory** during a run, discarded immediately after | Rendering the Discord message | Only sent to the Discord webhook(s) *you* configured |

No analytics, no tracking, no cookies, no databases, no telemetry, no advertising.

---

## 3. Data the Service Does NOT Collect

* Discord user information (usernames, IDs, messages of server members) — the Service cannot read
  any of it; webhooks are **one-way, post-only**.
* X/Twitter or Reddit account credentials — only **public** posts are fetched via public RSS/API
  endpoints; no login is used or stored.
* IP addresses or device information of anyone.
* Any payment information.

---

## 4. Third-Party Services

When the Service runs, it makes outbound requests to the following third parties. Their own privacy
policies apply to whatever they can technically observe (typically just the requesting IP and the
public URL being looked up):

| Service | Purpose | Their policy |
|---|---|---|
| **GitHub Actions** | Hosts and runs the scripts | https://docs.github.com/en/site-policy/privacy-policies |
| **Discord (webhooks)** | Delivers the generated messages | https://discord.com/privacy |
| **Nitter mirrors / Redlib** | Public RSS feeds for X/Twitter and Reddit | per-instance |
| **FxTwitter / FxEmbed API** | Tweet metadata, media, translation | https://fxtwitter.com |
| **video.twimg.com / x.com (X CDN & post pages)** | HTTP HEAD probes of public video file sizes (X V2/V3 "smart video" check) and OpenGraph image lookups on public post pages — only meta tags are read, no content is downloaded | https://x.com |
| **gif.fxtwitter.com** | One HEAD probe per X GIF to check the animated WebP rendition exists before using it | https://fxtwitter.com |
| **fastgif-production.up.railway.app** | Only when the above probe fails: one HEAD probe per X GIF to check the converted animated GIF exists; if it answers, Discord fetches that converted GIF when rendering the post. Independent third-party service, unaffiliated with this project or FxTwitter | https://railway.app |
| **EmbedEZ API** (Reddit V2 only) | Reddit post metadata, media | https://embedez.com |
| **reddit.com** | Public subreddit RSS | https://www.reddit.com/policies/privacy-policy |
| **cron-job.org** (optional) | External schedule trigger | https://cron-job.org/en/privacy/ |

The Service never sends these third parties anything about your Discord server's members or content —
only the identifiers of the **public** posts being rendered.

---

## 5. Data Retention

* Post-ID caches live in your repository until you delete them (they self-trim to the latest 500
  entries).
* Workflow run logs are retained by GitHub according to your repository's log-retention settings.
* Nothing is retained anywhere else, because nothing else exists.

---

## 6. Your Responsibilities & Rights

Because you operate your own instance, **you** are the data controller for it. You may inspect,
modify, or delete every byte it holds (the two JSON cache files) at any time. Server members who
want messages removed can ask you (or any admin with *Manage Messages*) to delete them from Discord.

---

## 7. Children's Privacy

The Service is not directed at children under 13 and collects no personal data from anyone of any
age.

---

## 8. Changes to this Policy

Changes are committed to this repository's `PRIVACY_POLICY.md` with an updated effective date.
Material changes will also be announced in the project's Discord server.

---

## 9. Contact

* GitHub: open an issue on this repository
* Discord: https://discord.gg/HyrVP9wRXu
* Support/dev: https://ko-fi.com/jieunlatte
