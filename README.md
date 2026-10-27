# layoff-radar

A public layoff tracker built on mined data only. The front page is a live stage (globe/map, ticking counter, "right now" feed) made to be screenshotted and shared. It pulls SEC filings, WARN notices and news, merges reports into events, and assigns each event a consensus headcount and a confidence score. Every number links to its sources. The site is fully static.

## Run

```sh
python3 -m radar all            # fetch -> process -> build (about 5 min on first run; HTTP is cached in data/cache)
python3 -m radar fetch [gnews edgar warn_ca warn_md hn reddit]   # pull sources (all if none given)
python3 -m radar process        # headlines -> claims -> events (consensus + confidence)
python3 -m radar build          # dist/: HTML pages, data.json, share-card PNGs
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
| `LR_BRAND` | Product name shown everywhere (default `layoff-radar`, a placeholder). |
| `LR_BACKFILL` | `1` re-scan the whole year of news, `0` recent only, `auto` (default): first run and 03:00 UTC daily. |

## Layout

- `radar/sources.py`: fetchers for Google News RSS, SEC EDGAR 8-K Item 2.05, CA and MD WARN, HN Algolia and Reddit RSS
- `radar/extract.py`: rule-based headline parser (company, headcount, %, retro/speculative flags)
- `radar/consensus.py`: clustering, re-report folding, weighted-median headcount, confidence, visibility gate
- `radar/build.py`, `radar/og.py`: static site, 1200×630 share cards and 1080×1920 stories
- `radar/places.py`: curated HQ cities and employee totals (for "% of staff"), Nominatim geocoding with a DB cache
- `radar/config.py`: brand name and site URL
- `site/static/globe.js`: front-page globe/map (d3-geo on canvas, vendored), live counter and feed
- `site/static/`: CSS, JS, fonts. `research/notes.md`: competitor and source research
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
