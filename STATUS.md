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
Deploy: `.github/workflows/refresh.yml` prepared, not pushed.
Next: user checks the globe on iPhone, picks domain, sets up Cloudflare Pages + D1/KV (README). Then ROADMAP "Data: deferred".
