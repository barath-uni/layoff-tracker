# Layoff Tracker: launch playbook

The product in one line: **a free, live globe of every verified layoff worldwide, updated hourly, with the source behind every number.** https://layoff-tracker.pages.dev

What sets it apart: layoffs.fyi and TrueUp cover tech only, and WARN trackers cover the US only. This one covers every industry in 28 countries, reads news in 30 languages, counts only official or multi-source events, and refreshes every hour. Lead with that in every channel.

The numbers below come from `data/numbers.json` (snapshot of 2026-10-29). Refresh them with the command at the top of `x-5-day-pack.md`.

---

## 1. Daily 30-minute routine

| Min | Do |
|---|---|
| 0–5 | Run the refresh command (data, numbers, cards). Open `data/numbers.json` → `totals` and check that today's post still matches. If a big company cut jobs overnight, its card is already in `dist/og/company/<slug>.png`. |
| 5–8 | Post the day's X post at its slot. Post the link reply within 60 s. Pin it on day 1. |
| 8–23 | **Reply under 6–8 bigger posts** (section 2). By hand, one by one. This step brings most of the reach for a small account. |
| 23–27 | Answer every reply on your own post from the last 24 h. Use the prepared replies, but adjust each one. Thank anyone who sends a correction, publicly. |
| 27–30 | Log the KPIs (section 9) in one line in `marketing/kpi-log.md`: date, impressions, link clicks, followers, site visits, corrections. |

Once a week (15 min): one Reddit or LinkedIn post from section 3 or 5. Never more than one subreddit a day.

---

## 2. Where to reply on X, and how

**Look for, in this order:**
1. **Breaking layoff news in the first hour.** Search `layoffs`, `job cuts`, `WARN notice`, `"to cut" jobs` with the Latest filter. Business reporters at Reuters, Bloomberg, WSJ, FT and CNBC, plus regional desks (Germany, the Netherlands, Australia, India). Be early: the first useful reply gets the most views.
2. **Labour-market economists and macro accounts** posting jobs reports, JOLTS or claims charts. Reply with the cross-industry angle (Finance 15,312 vs Tech 10,778).
3. **Career, recruiting and HR accounts** asking "who's hiring / who's cutting". Reply with the company's number and that it's sourced.
4. **Tech-layoff discourse** ("AI is killing tech jobs"). Reply with the contrarian data point: tech is 9.6% of the verified total.
5. **European business accounts.** Most US trackers miss Europe entirely. 51.3% of the people are outside the US.

**Reply style:**
- Lead with **one specific number**, then **one line of context**. No link (X shows link replies to fewer people), unless someone asks.
- Attach the company card (`dist/og/company/<slug>.png`) or a marketing card when it fits. Replies with images stand out.
- Example: *"Confirmed: 2,500 at NAB, via Reuters and The Guardian. That's the 2nd-biggest cut in the last 30 days that I've tracked, after AmEx at 3,500."*
- Never say "check out my site". Never reply to posts about one person losing their job, and never quote-dunk anyone. Max ~10 replies a day, so you don't look like a bot.
- If someone asks for the source or the link, that's the moment to share it.

---

## 3. Reddit

General rules: post from an account with some history, disclose "I built this" in the post or first comment, answer every comment for 2 hours, and post one subreddit per day. **Re-read each sidebar on the day.** Rules change, and the notes below are summaries.

| Subreddit | Fit | Self-promo rules (summary) | What to post |
|---|---|---|---|
| **r/dataisbeautiful** | Best | Title must start with **[OC]**. The visual must be your own, posted natively as an image or video, not a link to a site. OP must post a comment within about an hour **citing the data source and the tool used**, or the post is removed. No clickbait titles. | Upload the 16:9 video natively. Title: `[OC] Every verified layoff of the last 3 months on one globe (112,159 people, 28 countries)`. Comment: "Source: SEC 8-K, US WARN notices, TDnet, NSE, multilingual news, deduplicated; only official or 2+ source events. Tool: Python (Pillow, numpy) + ffmpeg. Live version: link." |
| **r/datasets** | Good | Datasets and requests only. Free, open data is welcome, but no paywalled or "sign up" links. | Text post: "Hourly-updated JSON of verified layoffs worldwide (company, headcount, low/high, country, industry, sources)", linking `/data.json`. State the licence and terms first, and settle one if there isn't any. |
| **r/layoffs** | Good, carefully | Support and discussion sub. Promotion is usually removed unless mods agree. Be gentle. | **Message the mods first**: offer it as a free resource for the wiki or sidebar. If they say yes, post a text post with a calm tone and no hype numbers. |
| **r/cscareerquestions** | Weak | Strict: no self-promotion, no products, no surveys. Personal links get removed and can get you banned. | **Don't post.** Comment only when a thread asks "is the market getting worse / is it only tech?", give the number, and link only if asked. |
| **r/europe** | Medium | News and discussion. Personal sites and spam get removed. Data posts with sources and a clear European angle do better than links. | Native image: `images/d-countries-1600x900.png`, with a title like `Verified layoffs, last 3 months: UK, Germany, Italy and the Netherlands lead Europe`. Put the source and method in the first comment. Weekday, 10:00–12:00 CET. |

---

## 4. Show HN

- **When:** Tue 3 Nov or Wed 4 Nov, **15:00 Amsterdam = 09:00 New York (EST)**. A weekday US morning gives it a full day on /show. Not on the same day as a big X push, so you can stay in the comments for 3 hours.
- **Title** (factual, no superlatives, 76 chars):
  `Show HN: Layoff Tracker – a live globe of verified layoffs from 30 languages`
- **URL:** https://layoff-tracker.pages.dev
- **First comment:**

> Hi HN, I built this. Layoff news is scattered: SEC 8-Ks, US state WARN notices, Japan's TDnet, India's NSE disclosures, and local-language news that English trackers never see. Existing trackers are tech-only or US-only.
>
> How it works: Python, mostly stdlib. Fetchers pull those sources plus Google News country editions. A rule-based parser pulls out company, headcount and % from headlines in 30 languages (local layoff verbs, number formats, rumour wording, CJK patterns). Reports are clustered into events, and each event gets a consensus headcount (low/high) and a confidence label: Official (a filing or notice), Corroborated (2+ independent sources), or Reported. The site is fully static and rebuilt hourly. Every number links to its sources.
>
> Last 3 months, counting only Official and Corroborated: 112,159 people, 523 events, 481 companies, 28 countries. The median layoff is 108 people. Tech is under 10% of the total.
>
> What's hard, honestly: rule-based extraction misattributes. A Korean headline about Microsoft's voluntary-retirement offer got pinned on Meta, and a "GTA 6" headline became a 6-person layoff. I review the big ones by hand. I'd love feedback on the dedup and confidence logic, and on sources I'm missing (EU countries have no WARN equivalent).
>
> The data is at /data.json.

- **During:** answer every comment, admit errors fast, never ask for upvotes (HN penalises that). If it stalls in the first 30 minutes, don't repost the same day. The mods allow a repost after a few days if it got no attention.

---

## 5. LinkedIn

Post Tue–Thu, 08:30 Amsterdam (catches Europe at their desks). Attach `images/a-30day-1080x1350.png` (tall images take up more of the feed). The link goes in the first comment.

**Post:**

> I built a live tracker of every verified layoff in the world.
>
> In the last 30 days: 35,275 people. That's 49 an hour.
>
> What surprised me after 3 months of data:
> → Layoffs aren't a tech story anymore. Finance laid off more people than tech (15,312 vs 10,778).
> → More than half the people affected are outside the US.
> → The median layoff is 108 people. Not "massive". A team, a plant, a store.
>
> Every number links to its source: a filing, a government WARN notice, or at least two independent news reports. It reads news in 30 languages and updates every hour.
>
> It's free. If you work in HR, recruiting or outplacement, or you're job hunting, I hope it's useful. And if you see something wrong, tell me.
>
> Link in the first comment.

**First comment:**

> https://layoff-tracker.pages.dev: free, no signup, updated hourly. Click any dot or company for its sources.

---

## 6. The brand handle: @LayoffTracker

- **Register it this week** (free) before someone else does. If it's taken, use `@LayoffTrackerHQ` or `@layofftracker_live`. Same name on Bluesky, Threads and Instagram.
- Profile: banner `profile/header-1500x500.png`, avatar `profile/avatar-400.png`, bio *"Every verified layoff worldwide, on one live globe. Updated hourly. Sources on every number. Built by @you."*, and the link.
- Go to Settings → Your account → Account information → **Automation** and mark it as automated, managed by your personal handle. X requires this for bot-run accounts.
- **Later, auto-stats:** a once-a-day post (e.g. 14:00 CET) of the 24h and 30-day counts, plus the share card `dist/og/stat-30d.png`, posted with the X API (check the current free-tier write limit in the developer portal first; stay on the free tier). **Original posts only.** No automated replies, mentions, likes or follows.
- Until then, the personal founder account does all the talking. People follow people at launch.

---

## 7. When a post takes off

Signs: more than 10k impressions in the first hour, quote-reposts from big accounts, or replies coming faster than you can read them.

1. **Stay in the replies for 2 hours.** Reply fast with numbers. That's what keeps it spreading.
2. **Extend the thread:** add `d-countries`, then `b-industries`, then `c-companies` as replies. Each new card is a fresh reason to repost.
3. **Pin it** (replace the day-1 pin if this one is bigger). Don't edit the post.
4. **Check the site:** Cloudflare Pages is static, so it will hold. Watch for broken share previews.
5. **Fix any reported error within the hour and say so publicly** ("fixed, thanks @x"). That builds more trust than the post itself.
6. **Capture it:** reply to journalists and big accounts who quote it with a one-line offer ("happy to share the data or a country cut"). Save their handles to `marketing/press.md`.
7. **Convert:** one reply saying "@LayoffTracker posts the daily count", once the handle exists.
8. **Next day:** post a follow-up with a fresh number ("since yesterday's post, X more people…"), not a repeat.

---

## 8. Do-not list

No automated replies or DMs (against X and Reddit rules, and it gets the account limited). No buying followers or boosts. No "RIP" or jokes about laid-off people. Don't call it "real-time" (it's hourly). Don't post a number you can't trace to `data.json`.

---

## 9. KPIs

| Metric | Where | Week-1 target (small account) |
|---|---|---|
| Impressions per post | X analytics | 5k median; one post above 50k |
| Link clicks per post | X analytics, link reply | 1–2% of impressions |
| Unique site visitors | Cloudflare Web Analytics (free) | 5,000 for the week |
| Followers gained | X | +200 |
| Replies under others → profile visits | X analytics | 10 a day → 50 profile visits a day |
| Corrections received and fixed | your log | every one fixed within 24 h |
| Show HN | HN | front page (about 30 points in the first hour) |
| r/dataisbeautiful | Reddit | 1k upvotes |
| Return visitors (day 7) | Cloudflare | 15%+ |

A repeat visit is the real signal: an hourly-updating tracker should become a bookmark.

---

## 10. Lite research: what works for tracker and data-viz launches right now

Based on general knowledge up to mid-2026, not paid tools. Check the details on the day.

- **Lead with a surprising finding, not the product.** Data launches spread when the first line is a number people want to argue with ("tech is under 10%"). "I built X" works as the second sentence.
- **Upload media natively; link in the first reply.** X and LinkedIn both show posts with outbound links to fewer people. A short looping video or one bold image is the format that travels for data-viz.
- **Movement beats static.** Animated globes, counters going up and timelines "filling in" get shared and quote-reposted much more than charts.
- **Receipts on demand.** Trackers live or die on "source?". Having the source one click away, and fixing errors in public, turns sceptics into people who share it.
- **Newsjacking.** Big layoff announcements bring traffic spikes. Being the first reply with a clean, sourced card for that company is what grows trackers. The company cards already exist in `dist/og/company/`.
- **Show HN and r/dataisbeautiful** still reward an honest write-up of the method and its limits over hype.
- **Verification is not required.** Paid accounts get some ranking boost in replies, but small unverified accounts still go viral through quote-reposts and native video. Leave verification for later, once you know it pays off.
- **No automated replies.** X's automation rules ban automated replies and mentions to users who didn't ask for them, and Reddit bans bot posting. All replies are by hand. The brand handle only posts original, scheduled stats.
