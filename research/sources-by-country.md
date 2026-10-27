# Sources by country (data window: last 3 months, 2026-07-27 → 2026-10-27)

Registry: `radar/config.py` (`SOURCES`, one adapter each; `GNEWS_EDITIONS` for the country editions).
Shown events per country after the 2026-10-27 run (1,000 events, 40 countries + 30 Unknown).

| Country | Sources | Events |
|---|---|---|
| United States | SEC 8-K 2.05, WARN (CA, MD, PA, CO, WA; TX empty this window), Google News US, HN, Reddit | 334 |
| South Korea, Japan, China, Taiwan, Hong Kong | Google News ko / ja / zh-Hans / zh-Hant editions; Japan also TDnet | 69 / 35 / 24 / 8 / 10 |
| Germany, Austria, Switzerland | Google News de editions | 53 / 3 / 30 |
| France, Belgium, Netherlands | Google News fr, nl editions | 34 / 24 / 22 |
| Italy, Spain | Google News it, es | 45 / 41 |
| Brazil, Argentina, Mexico, Chile, Colombia | Google News pt-BR, es-419 | 44 / 36 / 7 / 19 / 4 |
| United Kingdom, Ireland, Canada, Australia, NZ-less Anglosphere | Google News en editions; Australia also ASX (0 hits this window) | 25 / – / 11 / 11 |
| India | Google News en-IN + hi, NSE announcements | 4 |
| Indonesia, Thailand, Vietnam, Philippines, Malaysia, Singapore | Google News id, th, vi, en editions | 16 / – / 2 / – / – / 2 |
| Nordics (SE, NO, DK, FI via spillover) | Google News sv, no, da | 13 / 4 / – / 8 |
| Poland, Turkey, Russia | Google News pl, tr, ru | 4 / 6 / 6 |
| Gulf, Egypt, Israel, South Africa, Nigeria, Bangladesh | Google News ar, he/en, en, bn | Israel 2, others 0 |

Notes
- Countries outside the editions (Greece, Czechia, Romania, Hungary, Portugal, Ukraine, Luxembourg) still appear when a story names them.
- GDELT DOC API is disabled (429 rate limits); GDELT bulk files are on the roadmap.
- Unknown country (30): mostly US regional employers named only in local news; a default-to-US rule for US-only sources is a next step.
