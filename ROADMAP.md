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

## Deliberately out (for now)
| Item | Why not yet |
|---|---|
| Self-reports ("I was laid off") | Can't be verified (accounts deactivated), people won't log in |
| Consensus corrections | Needs moderation; design sketched in research/notes.md |
| X / LinkedIn ingestion | Paid API / ToS forbids scraping |
| More WARN states (NY, WA, TX, NJ, IL…) | Each needs its own scraper; some block bots |
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
