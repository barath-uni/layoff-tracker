# Layoff Tracker: 5-day X pack

Day 1 is **Thu 29 Oct 2026**. You post from your personal account, as the founder. Link: https://layoff-tracker.pages.dev

**Numbers** come from the data.json snapshot of 2026-10-29 01:54 UTC (`data/numbers.json`). They count Official and Corroborated events only, with plans and the bad rows taken out (listed at the end). Window: 29 Jul to 28 Oct 2026 ("last 3 months"). The site updates every hour, so on the morning of each post run this and re-check the figures in that day's post:

```sh
cd ~/codespace/layoff-radar && curl -s https://layoff-tracker.pages.dev/data.json -o marketing/data/data-$(date +%F).json \
  && python3 marketing/src/derive.py marketing/data/data-$(date +%F).json && python3 marketing/src/cards.py && python3 marketing/src/profile.py
```

**Clock note.** The Netherlands went back to winter time on 25 Oct. The US doesn't until 1 Nov. So Amsterdam is 5 hours ahead of New York on Thu to Sat, and 6 hours ahead from Sun. The times below already allow for that.

**Rules for every post:** no link in the main post (X shows posts with links to fewer people). The link goes in your own first reply, posted within 60 seconds. Pin the day-1 post. Stay in your own voice: "I built this". Never joke about the people who lost their jobs.

---

## Day 1: Thu 29 Oct, "watch this" (launch)

- **Time:** 14:30 Amsterdam (CET) = 09:30 New York (EDT). *New York is at their desks with coffee and Europe is back from lunch, so you get both audiences.*
- **Asset:** `video/globe-1920x1080.mp4` (use `video/globe-1080x1920.mp4` if the wide one looks soft on your phone)

**Main post** (252 chars)
```text
Watch 3 months of layoffs land on one globe.

112,159 people. 481 companies. 28 countries. Each dot is a verified layoff, sized by headcount.

I built this because headlines kept saying "massive" and never gave a number. Now it counts them, every hour.
```

**First reply (link)**
```text
Free, no signup: https://layoff-tracker.pages.dev

Every number links to the filing, WARN notice or news report behind it. Only official or multi-source events count. Rumours don't.
```

**Optional second reply** (asset `images/d-countries-1600x900.png`)
```text
The part that surprised me: more than half of the people are outside the US. 51.3%. UK, Germany, Italy, the Netherlands next.
```

**Prepared replies**
- *"Source?"*
  ```text
  Click any dot. Each event lists its sources: SEC 8-K filings, US state WARN notices, Japan's TDnet, India's NSE, plus news in 30 languages. This count uses only official filings or stories with 2+ independent sources.
  ```
- *"This is fearmongering"*
  ```text
  It's the opposite of a headline. No adjectives, just counted people with receipts. The median verified layoff is 108 people. If a number is wrong, show me and I'll fix it.
  ```
- *"Add my company"*
  ```text
  If it's public (a filing, a WARN notice or a news report) it gets picked up within the hour. Send me the link and I'll check why it's missing. Anonymous tips can't go in: every dot needs a source.
  ```

---

## Day 2: Fri 30 Oct, stat bomb

- **Time:** 14:00 Amsterdam (CET) = 09:00 New York (EDT). *Friday reach drops after US lunch, so post at the start of their working day.*
- **Asset:** `images/a-30day-1600x900.png`

**Main post** (225 chars)
```text
35,275 people laid off in the last 30 days.

That's 49 an hour.

189 verified layoffs. Not rumours: each one is a filing, a WARN notice or 2+ independent reports.

Biggest: American Express 3,500. NAB 2,500. Royal Mail 2,500.
```

**First reply (link)**
```text
Live count, updated hourly: https://layoff-tracker.pages.dev

Click any company and you get the sources behind its number.
```

**Prepared replies**
- *"Source?"*
  ```text
  AmEx 3,500: WSJ, CNBC, Livemint. NAB 2,500: Reuters, The Guardian. Royal Mail 2,500: The Sun, Interfax and others. Every event's sources are one click away on the site.
  ```
- *"This is fearmongering"*
  ```text
  49 an hour is the 30-day total divided by 720 hours. That's all. The site doesn't call anything a "bloodbath". It counts, and shows where each number came from.
  ```
- *"Add my company"*
  ```text
  Drop the link (filing, WARN notice or article). If it's a real announced cut with a number, it goes on the globe. If the number is missing, it still shows up as "undisclosed".
  ```

---

## Day 3: Sat 31 Oct, question

- **Time:** 15:00 Amsterdam (CET) = 10:00 New York (EDT). *On weekends Americans scroll later, so 10am is the slot. Quiz posts get replies all day.*
- **Asset:** `images/c-companies-1080x1350.png` (the tall card takes up more of the feed)

**Main post** (238 chars)
```text
Guess first, then look at the image.

Which company laid off the most people in the last 3 months?

Hint: not Meta, not Amazon, not Google. Not even tech.

I track every verified layoff on a live globe. The top 10 was not what I expected.
```

**First reply (link + answer)**
```text
Answer: Barclays. 5,000 jobs, and the bank pointed to AI. Then Uber, AmEx, a Washington farm, Evonik, Heineken.

Full list, live: https://layoff-tracker.pages.dev
```

**Prepared replies**
- *"Source?"*
  ```text
  Barclays 5,000: BBC, Bloomberg, Fast Company. Gebbers Farms 3,445: a Washington State WARN notice. Every row in the image has its sources on the site.
  ```
- *"This is fearmongering"*
  ```text
  It's a quiz with a sourced answer. Most of these cuts got one day of headlines and were gone. The point of a tracker is that they don't vanish.
  ```
- *"Add my company"*
  ```text
  Send the link. Public reports get pulled in hourly from news, SEC filings and WARN notices. If yours was missed, I want to know why.
  ```

---

## Day 4: Sun 1 Nov, story

- **Time:** 16:00 Amsterdam (CET) = 10:00 New York (EST, first day of US winter time). *Sunday is for slow reading, so a story post fits. Leave 6 hours between the cities from today.*
- **Asset:** `images/e-massive-1600x900.png`

**Main post** (278 chars)
```text
I built a layoff tracker after a week of headlines.

"Massive layoffs." "Massiver Stellenabbau." "Despidos masivos."

So I started counting. The median verified layoff in the last 3 months: 108 people.

Some are huge. Most are a team, a plant, a store. Every one is real people.
```

**First reply (link)**
```text
It became this: every verified layoff on a live globe, updated hourly, every number sourced. https://layoff-tracker.pages.dev
```

**Prepared replies**
- *"Source?"*
  ```text
  The median comes from 380 verified layoffs with a disclosed headcount, 29 Jul to 28 Oct. The headlines in the image are real: The Guardian on NAB, Heute on BMW, IGN on Ninja Theory. All linked on the site.
  ```
- *"This is fearmongering"*
  ```text
  This post is literally saying the headlines overhype it. 108 is the honest middle. The total is still 112,159 people in 3 months, and both numbers are true.
  ```
- *"Add my company"*
  ```text
  Small ones count too. A 20-person WARN notice is on the globe next to the 5,000-person bank. Send the link.
  ```

---

## Day 5: Mon 2 Nov, contrarian

- **Time:** 15:00 Amsterdam (CET) = 09:00 New York (EST). *On Monday morning in the US, people are catching up on news and arguing, which is the best time for a hot take.*
- **Asset:** `images/b-industries-1600x900.png`

**Main post** (241 chars)
```text
Layoffs are not a tech story anymore.

Last 3 months, verified:
Finance: 15,312 people
Tech: 10,778

Tech is under 10% of everyone laid off. Banks, farms, chemicals, steel, retail: that's where it is now.

The timeline just hasn't caught up.
```

**First reply (link)**
```text
Filter the globe by industry yourself: https://layoff-tracker.pages.dev

Every number is sourced. Tell me what I'm missing.
```

**Prepared replies**
- *"Source?"*
  ```text
  Finance: Barclays 5,000, AmEx 3,500, Visa 2,600, NAB 2,500. Tech: Uber 3,300, then eBay, ServiceNow, Amazon at about 1,000 each. Industry tags are on every company page.
  ```
- *"This is fearmongering"*
  ```text
  If anything it's the reverse of the usual "AI is eating tech jobs" panic. The numbers say it's spread across everything, which is a different and more useful story.
  ```
- *"Add my company"*
  ```text
  Which industry? If you post the source here, I'll make sure it lands with the right tag.
  ```

---

## Rows removed before counting (applies to every number above)

UPS 48,000 · Rockstar "GTA 6" (6) · Soriana 4,000 (denied) · AstraZeneca 2,000 (the staff count) · Jaguar Land Rover duplicates (none left) · **audit finds:** "Meta 60,000" (actually Microsoft's voluntary-retirement offer) and "Microsoft 60" (the same story), "Porsche 50,000" (the VW group plan), "Porsche 9,000" (the company denied it), "Blizzard 1,900" (a job-protection deal), "İngiliz 1,200" (a duplicate of GSK), "Meta 2,000" (laid off by a contractor). The full list with reasons is in `data/numbers.json` → `excluded`. These rows are still live on the site, so fix them there before day 1 if you can.
