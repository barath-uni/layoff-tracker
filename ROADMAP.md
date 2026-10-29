# Roadmap

## V1 (done)
- Sources: Google News RSS (YTD backfill, 6 English editions), SEC 8-K Item 2.05, California and Maryland WARN, HN, r/layoffs
- Rule-based extraction; clustering into events; weighted-median headcount with a range; confidence labels (Official / Corroborated / Reported)
- Accuracy gate: shown only if official or 2+ independent publishers; re-reports, past totals and multi-year targets are not counted
- Static site: company pages with every source, charts, filters, share cards, data.json

## V2 (this release)
- Live front page: globe/map of events (sized by people, bright = last 7 days, pulsing), click a dot for the details and sources
- Ticking counter (estimate at the 30-day pace, snaps to verified data hourly), deadpan headline line, "right now" feed
- Share kit: "Company just cut X% of its staff" cards, "This week in layoffs" card, 1080×1920 stories
- % of staff: sourced percentage, or ≈ from a curated employee table (FY + annual report); never invented
- Entity resolution: products, units and executives merge into the employer; rumours fold into the confirmed event
- Hourly GitHub Actions refresh and deploy to Cloudflare Pages (DB kept in the Actions cache)

## V3: free-to-locked demand test (this release)
- Map freedom: zoom (wheel, pinch, +/−) and pan on the flat map and the globe; dots stay legible, company labels appear at higher zoom
- Click a dot: a panel on the first screen (bottom sheet on phones) with people, % of staff, date, confidence and sources, plus "Dive deeper"
- Dive deeper: table preview by company, sector and country, first rows free, the rest blurred behind an email-only sign-up; an "Early warning" tab of WARN notices not yet effective (the paid-product teaser)
- Sign-up through a Cloudflare Pages Function (D1 or KV), honeypot and rate limit; own counts of panel opens, gate views and sign-ups, no third-party analytics

## V4: single-screen globe (branch ui-redesign)
- Home is one screen (100dvh, no page scroll); everything floats over the globe on glass panels; charts moved to /insights
- Custom globe: dot-matrix "night earth", company favicon pins with recency rings, WARN badge, pulse rings, label chips ("Meta −3,600 · 2d")
- Live counter + deadpan line, live feed (new items slide in), pin card, Dive-deeper drawer with designed rows and the blurred email unlock
- Replay of the year in ~20 s with a weekly-histogram scrubber; the camera follows the biggest layoffs; `/?replay` autoplays
- Brand: Layoff Tracker

## Globe extras (cut for launch, next)
- "People" particles drifting off fresh pins, scaled by log(headcount)
- Country glow from the last 30 days (and a trailing 30-day glow during Replay)
- City clustering with a count bubble when pins pile up; a denser dot lattice at high zoom
- A recording mode for Replay (hide panels, 9:16 framing, brand watermark) and a "download clip" export
- Self-hosted logo sprites at build time (no third-party favicon requests), more curated domains

## Data V5: last 3 months, ~40 economies (this release)
- Window: the last 3 months only (`util.SINCE`, default today − 92 days; `LR_SINCE` overrides). Older rows stay in the DB as cache but are not processed or shown.
- Sources in `config.SOURCES` (one adapter each): Google News (English) and 43 country editions with local-language keywords (`config.GNEWS_EDITIONS`), SEC 8-K 2.05, WARN (CA, MD, TX, PA, CO, WA), TDnet, NSE, ASX, HN, Reddit
- Announced multi-year plans (VW-style "50,000 by 2030") are kind `plan`: shown with their deadline, excluded from the counter and totals
- `python3 -m radar report`: duplicates, unknown country, headcount > company, junk names (fixes go into rules/aliases)

## Data: deferred
- **Country-by-country expansion:** per-country official sources (UK HR1 via FOI-only, Germany Massenentlassungsanzeigen are not public, France PSE/DREETS, Canada provincial notices, Australia/Korea/Japan exchange feeds beyond TDnet/ASX), more editions beyond the top ~40 economies, per-country keyword tuning
- **GDELT bulk files:** the GDELT DOC API rate-limits (429 / "Please limit requests"), so the adapter is disabled in `config.SOURCES`. Next: the 15-minute GKG/Events bulk CSVs from data.gdeltproject.org (no rate limit), filtered on layoff themes (`ECON_UNEMPLOYMENT`, `TAX_ECON_PRICE`…)
- **Older backfill:** before the 3-month window (`LR_SINCE=2026-01-01` works but needs a longer run and a "since" label check on every page)
- More WARN states (NY, NJ, IL…), Google News redirect resolution to publisher URLs

## Deliberately out (for now)
| Item | Why not yet |
|---|---|
| Self-reports ("I was laid off") | Can't be verified (accounts deactivated), people won't log in |
| Consensus corrections | Needs moderation; design sketched in research/notes.md |
| X / LinkedIn ingestion | Paid API / ToS forbids scraping |
| LLM extraction | Hook exists (`LR_LLM_CMD`), off to keep runs free and deterministic |
| Alerts, newsletter, public API | After the audience exists |
| City clustering | Zoom plus label collision handling covers today's density |
| Real paywall, accounts, alert e-mails | Only after the demand test shows sign-ups ÷ gate views is worth it |

## Plan
1. **Launch (now):** pick the name and domain, connect Cloudflare Pages, turn on the hourly workflow, seed the first posts with the weekly card.
2. **Coverage (weeks 1–2):** NY, WA, TX, NJ, IL WARN; resolve Google News redirect links to publisher URLs; more curated HQ and workforce rows.
3. **Accuracy (weeks 2–4):** optional LLM pass for headlines the rules miss, a maintainer review queue for merges and aliases, a public changelog of corrections.
4. **Distribution (month 2):** auto-post the weekly card, embeddable counter widget, per-industry and per-country landing pages.
5. **Community (month 3+):** consensus-based corrections (flags as low-weight claims, applied only with a qualifying source), alerts by company or industry, a public API.

- Rumoured label: show rumour-only events (e.g. Meta, Oct 2026) with a visible "Rumoured / unconfirmed" badge, no headcount, out of all totals. Today rumours already never set a number; the badge is not built yet.
