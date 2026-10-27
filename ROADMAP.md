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

## Deliberately out (for now)
| Item | Why not yet |
|---|---|
| Self-reports ("I was laid off") | Can't be verified (accounts deactivated), people won't log in |
| Consensus corrections | Needs moderation; design sketched in research/notes.md |
| X / LinkedIn ingestion | Paid API / ToS forbids scraping |
| More WARN states (NY, WA, TX, NJ, IL…) | Each needs its own scraper; some block bots |
| LLM extraction | Hook exists (`LR_LLM_CMD`), off to keep runs free and deterministic |
| Alerts, newsletter, public API | After the audience exists |
| Map zoom and city clustering | Fine at today's density |

## Plan
1. **Launch (now):** pick the name and domain, connect Cloudflare Pages, turn on the hourly workflow, seed the first posts with the weekly card.
2. **Coverage (weeks 1–2):** NY, WA, TX, NJ, IL WARN; resolve Google News redirect links to publisher URLs; more curated HQ and workforce rows.
3. **Accuracy (weeks 2–4):** optional LLM pass for headlines the rules miss, a maintainer review queue for merges and aliases, a public changelog of corrections.
4. **Distribution (month 2):** auto-post the weekly card, embeddable counter widget, per-industry and per-country landing pages.
5. **Community (month 3+):** consensus-based corrections (flags as low-weight claims, applied only with a qualifying source), alerts by company or industry, a public API.
