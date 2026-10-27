# layoff-radar: STATUS
What: public, shareable layoff tracker built on mined data only. Multi-source scrape, then a consensus headcount per event, with every number sourced. Self-reports are dropped. Corrections are deferred (see research/notes.md).
Scope: all industries (tech-heavy), global. Name "layoff-radar" is a placeholder.
State (2026-10-27): V1 works locally. 7.9k items from Google News, EDGAR 8-K 2.05, CA+MD WARN, HN and Reddit became 637 shown events at 565 companies (403 Official, 163 Corroborated, 71 Reported). YTD total 365,012; last 30 days 31,625.
Run: `python3 -m radar all`, then `python3 -m radar serve 8000` (see README).
Accuracy rules: shown only if official or >= 2 independent publishers; re-reports fold into one event; past-total and multi-year numbers are ignored; >50k needs 3+ publishers incl. a major outlet.
Known gaps: rule-based parsing (LLM hook off), Google News links are redirect URLs, WARN covers only CA+MD, country is often HQ or Unknown, some multi-round programs (Oracle, VW) are fuzzy (shown as ranges).
Next: user picks a name and domain (SITE_URL); schedule daily `radar all`; add more WARN states (NY, WA, TX via other routes); optional LLM extraction pass; deploy dist/ to Cloudflare Pages.
