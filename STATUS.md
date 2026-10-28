# Layoff Tracker (repo: layoff-radar): STATUS
What: public layoff tracker on mined data only. Multi-source scrape, consensus headcount per event, every number sourced. Brand "Layoff Tracker" (`LR_BRAND`).
State (2026-10-27): ui-redesign merged (single-screen globe home, /insights, /companies, /company/<slug>/). Data scoped to the LAST 3 MONTHS (2026-07-27 → today, `util.SINCE`).
Data: 1,000 shown events, 40 countries (+30 Unknown), 321,400 people counted. Items in window: Google News EN 3.3k + 43 country editions 20.8k, EDGAR 67, WARN CA/MD/PA/CO/WA 436, HN 319, Reddit 114, NSE 8, TDnet 8.
Sources: `radar/config.py` SOURCES (one adapter each). GDELT DOC API disabled (429s). ASX and WARN TX returned 0 this window.
Announced multi-year plans (VW 50k, BMW 8k, Porsche…) are kind `plan`: shown with "announced plan · not counted", excluded from counter and totals.
Quality: `python3 -m radar report` (dupes 4, unknown country 30, headcount>company 1 = Qualcomm hoax, number dropped in build; junk names 43, mostly short legit names/WARN sites).
Run: `python3 -m radar all` (~15 min with warm cache, peak RSS <100 MB), then `python3 -m radar serve 8000`.
Verified: /, /insights/, /methodology/, /company/{volkswagen,barclays,ups}/ all 200 with brand and non-zero totals (curl only, no browser check).
Known gaps: rule-based parsing in 29 languages (cross-language dupes still possible), Google News redirect links, Unknown-country US regionals.
Deploy (2026-10-28): public repo github.com/barath-uni/layoff-tracker. `main` = source; `site` (DEFAULT branch) = tag `site-base` (workflow only) + one force-pushed build commit (dist + deploy/vercel/api + vercel.json). Hourly workflow on GH Actions (data/ in Actions cache, EDGAR daily via LR_DAILY=edgar) runs deploy/push-site.sh with GITHUB_TOKEN. After editing refresh.yml on main: `deploy/push-site.sh --new-base` locally. Commit emails rewritten to GitHub noreply (local backup tag backup/pre-public-rewrite, never push it).
First CI run 2026-10-28: success in 16 min (empty cache; fetch 15.5 min), 788 events. EDGAR 403 from CI (SEC wants a contact email in the UA): set repo secret LR_CONTACT. WARN TX and ASX 0 as before.
Sign-ups on Vercel: only logged to function logs; /api/stats = 501. TODO Upstash Redis.
Next: user imports the repo in Vercel (Other, no build) -> https://layoff-tracker.vercel.app (if the domain differs, set repo variable SITE_URL). Then ROADMAP "Data: deferred".
