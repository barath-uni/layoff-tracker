# layoff-radar

A public layoff tracker built on mined data only. It pulls SEC filings, WARN notices and news, merges reports into events, and assigns each event a consensus headcount and a confidence score. Every number links to its sources. The site is fully static.

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

## Layout

- `radar/sources.py`: fetchers for Google News RSS, SEC EDGAR 8-K Item 2.05, CA and MD WARN, HN Algolia and Reddit RSS
- `radar/extract.py`: rule-based headline parser (company, headcount, %, retro/speculative flags)
- `radar/consensus.py`: clustering, re-report folding, weighted-median headcount, confidence, visibility gate
- `radar/build.py`, `radar/og.py`: static site and 1200×630 share cards
- `site/static/`: CSS, JS, fonts. `research/notes.md`: competitor and source research
- `data/` (gitignored): SQLite DB and HTTP cache. `dist/` (gitignored): build output

## Deploy

`dist/` is a plain static folder (Cloudflare Pages, Netlify, any bucket). Run `python3 -m radar all` on a schedule, for example a daily cron or CI job, with `SITE_URL` set.
