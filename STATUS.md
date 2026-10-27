# layoff-radar: STATUS
What: public, shareable layoff tracker built on mined data only. Multi-source scrape, then a consensus headcount per event, with every number sourced. The brand is a single config value (`LR_BRAND`, placeholder "layoff-radar").
State (2026-10-27): V2 built locally. The front page is a live stage: globe/map with event dots, a counter ticking at the 30-day pace, a deadpan line and a "right now" feed. Share kit: company statement cards, "this week in layoffs" card, 1080×1920 stories. "% of staff" is sourced or ≈ from a curated employee table.
Data: 7.9k items from Google News, EDGAR 8-K 2.05, CA+MD WARN, HN and Reddit became ~630 shown events (Official / Corroborated / Reported only).
Accuracy: entity resolution merges products, units and CEOs into the employer; rumours fold into confirmed events; rumour, hypothetical and past-total numbers are never counted.
Deploy: `.github/workflows/refresh.yml` (hourly, Actions cache for data/, wrangler to Cloudflare Pages). Prepared, not pushed. See README for the one-time setup.
Run: `python3 -m radar all`, then `python3 -m radar serve 8000`.
Known gaps: rule-based parsing, Google News redirect links, WARN covers CA+MD only, multi-round programs (Oracle, VW) shown as ranges.
Next: user picks a name and domain, creates the GitHub repo and Cloudflare Pages project, and adds secrets. See ROADMAP.md for the phases.
