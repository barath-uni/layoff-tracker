# Layoff Tracker

A public layoff tracker built on mined data only. The front page is a single-screen app (no page scroll): a dot-matrix globe with company-logo pins, a ticking counter, a live feed and a "Replay", made to be screenshotted, screen-recorded and shared. It pulls SEC filings, US WARN notices, Japan's TDnet and India's NSE disclosures, and news from Google News country editions in local languages, merges reports into events, and assigns each event a consensus headcount and a confidence score. Every number links to its sources. The site is fully static.

## Run

```sh
python3 -m radar all            # fetch -> process -> build (about 5 min on first run; HTTP is cached in data/cache)
python3 -m radar fetch [gnews gnews_intl edgar warn_ca warn_md warn_tx warn_pa warn_co warn_wa tdnet nse asx hn reddit]
                                # pull sources (all if none given), one at a time, streamed into the DB in batches
python3 -m radar process        # headlines -> claims -> events (consensus + confidence)
python3 -m radar build          # dist/: HTML pages, data.json, share-card PNGs
python3 -m radar report         # quality report: duplicates, unknown country, headcount > company, junk names
python3 -m radar serve 8000     # local preview at http://127.0.0.1:8000 (Ctrl+C to stop)
```

Requirements: Python 3.11+ and Pillow (for share cards). Everything else is stdlib.

## Config (env vars)

| Var | Purpose |
|---|---|
| `SITE_URL` | Absolute base URL used in share links and OG tags (default `http://localhost:8000`). Set it before `build` for deploys. |
| `LR_CONTACT` | Contact email in the SEC User-Agent (SEC asks for one). |
| `LR_LLM_CMD` | Optional extractor command (JSON in on stdin, JSON out). Off by default; see `radar/llm.py`. |
| `LR_TODAY` | Pin "today" (YYYY-MM-DD) for reproducible builds. |
| `LR_BRAND` | Product name shown everywhere, share cards included (default `Layoff Tracker`). |
| `LR_BACKFILL` | `1` re-scan the whole window of news, `0` recent only, `auto` (default): first run of each source and 03:00 UTC daily. |
| `LR_SINCE` | Start of the fetch and reporting window (default: today minus 92 days, i.e. the last 3 months). |

## Layout

- `radar/sources.py`: fetchers for Google News RSS (English), SEC EDGAR 8-K Item 2.05, CA and MD WARN, HN Algolia and Reddit RSS
- `radar/sources_intl.py`: Google News country editions with local-language keywords, Japan TDnet, India NSE, ASX (GDELT DOC adapter kept but disabled)
- `radar/warn_more.py`: WARN notices for Texas (data.texas.gov), Pennsylvania, Colorado and Washington
- `radar/extract.py`: rule-based English headline parser (company, headcount, %, retro/speculative flags, announced multi-year plans)
- `radar/intl.py`: the same rules for 29 other languages (local layoff words, job nouns, number formats, rumour wording, CJK patterns)
- `radar/consensus.py`: clustering, re-report folding, weighted-median headcount, confidence, visibility gate
- `radar/build.py`, `radar/og.py`: static site, 1200×630 share cards and 1080×1920 stories
- `radar/places.py`: curated HQ cities and employee totals (for "% of staff"), Nominatim geocoding with a DB cache
- `radar/config.py`: brand name, site URL, the source registry (`SOURCES`) and the Google News editions (`GNEWS_EDITIONS`, ~40 economies)
- `site/static/globe.js` + `home.css`: the home app. Dot-matrix globe (canvas 2D, d3-geo vendored) with favicon logo pins, pulse rings and label chips; inertia drag, wheel/pinch zoom; live counter; live feed (bottom sheet on phones); pin card; "Replay" scrubber (the year in 20 s; `/?replay` autoplays for screen recordings)
- `site/static/gate.js`: "Dive deeper" drawer (sheet on phones): designed rows, first rows clear, the rest blurred behind an email-only unlock (soft gate, unlocks client-side)
- `radar/logos.py`: curated company domains (favicon pins; monogram fallback) and country ISO codes (flags)
- `/insights/`: the charts, breakdowns and filterable event list that used to sit under the home stage
- `functions/api/[[route]].js`: Cloudflare Pages Function for `/api/signup`, `/api/event` and `/api/stats` (D1 or KV)
- `site/static/`: CSS, JS, fonts. `research/notes.md`: competitor and source research; `research/sources-by-country.md`: coverage per country; `research/scale.md`: run costs and the full-coverage extrapolation
- `data/` (gitignored): SQLite DB and HTTP cache. `dist/` (gitignored): build output

## Deploy (hourly, prepared but not active)

`.github/workflows/refresh.yml` runs `python -m radar all` every hour and deploys `dist/` to Cloudflare Pages with wrangler.
`data/` (SQLite DB and HTTP cache, about 30 MB) is kept between runs in the GitHub Actions cache.

One-time setup:
1. Push this repo to GitHub.
2. In Cloudflare, create a Pages project with direct upload (no Git integration needed) and an API token with *Cloudflare Pages: Edit*.
3. In the GitHub repo settings, add:
   - secrets `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID` and `LR_CONTACT` (your email, for the SEC User-Agent)
   - variables `CF_PAGES_PROJECT` (the project name), `SITE_URL` (e.g. `https://yourdomain.com`) and, optionally, `LR_BRAND`
4. Run the workflow once by hand (Actions → refresh → Run workflow) to seed the DB. After that it runs hourly.

The first run on an empty cache re-scans the whole year of news and geocodes places (OpenStreetMap Nominatim, 1 request/s). Expect 10–15 minutes. Later runs take a couple of minutes.

## Sign-up gate (a demand test, not a paywall)

Flow: click a pin or a feed row → card (company, people, % of staff, date, confidence, sources) → **Dive deeper** → drawer with the first 3–4 rows clear and the rest blurred, plus an "Early warning" tab (WARN notices filed but not yet effective) → email-only form → the full table unlocks in that browser (`localStorage`). The data itself stays public in `/data.json`; this only measures demand.

Endpoints (same routes locally and on Cloudflare):

| Route | What it does |
|---|---|
| `POST /api/signup` `{email, website, src}` | Stores the email once. `website` is a hidden honeypot (filled = fake success, nothing stored). 5 tries per IP per 10 min. |
| `POST /api/event` `{t}` | Counts `panel`, `gate_view` or `signup_open` per day (120 per IP per 10 min). |
| `GET /api/stats?key=…` | `{signups, totals, by_day}`. Needs `STATS_KEY` on Cloudflare; open locally. |

Locally, `python3 -m radar serve` handles these routes itself and writes `data/signups.jsonl` and `data/counts.json` (both gitignored). Check demand with `curl http://127.0.0.1:8000/api/stats`.

On Cloudflare, `functions/` deploys together with `dist/` (the workflow runs `wrangler pages deploy dist` from the repo root, which picks up `functions/`). One-time setup in the Cloudflare dashboard:
1. **Storage (pick one).** D1 (recommended): *Storage & Databases → D1 → Create*, e.g. `layoff-signups`. Or KV: *Workers KV → Create namespace*.
2. **Bind it to the Pages project:** *Workers & Pages → (project) → Settings → Bindings → Add*: a D1 database with variable name **`DB`**, or a KV namespace with variable name **`SIGNUPS`**. If both are bound, D1 is used. Tables create themselves on the first request.
3. **Variables** (*Settings → Variables and Secrets*, as secrets): **`STATS_KEY`** (any long random string; needed to read `/api/stats`) and, optionally, **`HASH_SALT`** (salts the hashed IPs used for rate limiting; raw IPs are never stored).
4. Redeploy (run the workflow once) so the bindings apply. Then: `curl "https://yourdomain.com/api/stats?key=$STATS_KEY"`.
   Export emails: `npx wrangler d1 execute layoff-signups --remote --command "SELECT email, created_at, src FROM signups"`.

Without a binding, `/api/signup` answers 503 and the form shows the error, so set storage up before launch.
