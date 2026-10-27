# Research notes (2026-10-27)

## Competitors and their gaps
| Tracker | What it is | Gap we exploit |
|---|---|---|
| layoffs.fyi | Hand-curated tech layoffs since 2020, Airtable embed, single headline count | Tech only; one number per row with no range or confidence; embedded Airtable looks dated; no per-company share cards; no worker reports |
| TrueUp layoffs | Tech layoffs list that funnels into a job board | Tech only, list UI, little sourcing transparency, no consensus |
| WARNTracker | US WARN Act notices as a raw table | Official but US-only, notice-level (not event-level), no news context, hard to share |
| Challenger, Gray & Christmas | Monthly US job-cut report (PDF/press release) | Aggregate only (no company pages), monthly lag, US only |
| News roundups (Fast Company, Yahoo, TechCrunch "tracker" posts) | Long running articles | Not structured, no charts, no filters |

**Positioning:** "every number links to its sources" + confidence score + range, all industries and countries, worker reports as a validated signal, and share cards built for X/LinkedIn.

## What makes datafa.st-style pages feel premium and shareable
- One huge, confident number above the fold, with a short plain-English label and a timestamp ("updated 2h ago").
- Restrained palette: neutral off-white or near-black surface, one accent color carrying the data. No gradients, no emoji, no stock illustrations.
- A real UI typeface (Geist/Inter class), tight letter-spacing on big numerals, generous whitespace, hairline borders, small caps-style labels.
- Charts that are calm: thin marks, recessive grid, hover tooltips, no chart-junk.
- Every unit is linkable and has its own OG image so a share renders as a card with the number in it (this is the virality engine).
- Fast static pages; nothing spins.

## Free, keyless sources (probed live)
| Source | Access | Result | Tier |
|---|---|---|---|
| Google News RSS `news.google.com/rss/search?q=...` (supports `when:30d`, `after:`/`before:`) | no key | 200, 100 items/query, publisher name included; links are Google redirect URLs | major/other news by publisher |
| SEC EDGAR full-text search `efts.sec.gov/LATEST/search-index?q="Item 2.05"&forms=8-K` | no key, needs a descriptive User-Agent | 200, JSON with items (2.05 = exit/disposal costs), SIC codes, HQ location; filing docs fetchable for headcount/% | official |
| California EDD WARN `warn_report1.xlsx` | no key | current FY (07/01/26 to 10/21/26), ~390 notices, includes industry. Older `warn_report.xlsx` is stale (2023-24) | official |
| Maryland DOL WARN `labor.maryland.gov/employment/warn.shtml` | no key | HTML table with NAICS, current to 10/23/26 | official |
| HN Algolia `hn.algolia.com/api/v1/search_by_date` | no key | 200 | aggregator/social |
| Reddit `r/layoffs/new/.rss` | no key | RSS 200 (JSON API 403 without OAuth) | social |
| Washington ESD WARN | JS/Tableau-driven, no table in HTML | skipped |
| Texas TWC WARN xlsx | 403 to scripts | skipped |
| New York DOL WARN | legacy page only | skipped for V1 |
| Bing News RSS | works, but terms forbid reuse beyond Bing display | skipped |
| X / LinkedIn | paid API (X) / no public API and ToS bans scraping (LinkedIn) | skipped; worker self-reports cover the "social" signal |

## Consensus model (V1)
- Source quality weights: official filing/WARN 1.0, major outlet 0.7, other news 0.45, HN 0.25, Reddit 0.15.
- Confidence = 1 - prod(1 - w) over *independent* sources (one per publisher), scaled 0-100.
- Headcount = weighted median of credible numeric claims; WARN sum acts as an official floor; range = min..max of claims.
- Visibility gate (V1): only official records, or events with >= 2 independent publishers, are shown. Single-source stories are suppressed.
- Re-reporting control: a company's later coverage that repeats a figure (+-10%) or revises it on the same scale (0.5x-2.5x) within 365 days folds into the earlier event; past-total/multi-year numbers ("over the past year", "by 2030", "in 12 months") are not counted.

## Corrections later (not in V1)
Self-reports are dropped: laid-off people won't log in, and their company accounts are often already deactivated. A future correction loop should stay consensus-based instead of trusting individuals:
- Anyone can flag an event ("wrong number", "duplicate", "not a layoff") with a link. A flag is just another *claim* with low weight. It changes nothing on its own.
- A correction applies when the cited link is itself a qualifying source (filing, WARN notice, major outlet) and the pipeline re-parses it the same way. That keeps the "every number links to its sources" rule.
- Duplicate/merge flags feed an alias table (`ref.ALIASES`) reviewed by a maintainer; the same goes for company-name fixes.
- Every applied correction is shown in the event's source list with a date, so changes stay auditable.
