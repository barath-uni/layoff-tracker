# Layoff Tracker: launch marketing pack

Everything here is local. Nothing has been posted or published. The numbers come from the data.json snapshot of 2026-10-29 01:54 UTC. Only Official and Corroborated events are counted (plans excluded), with the bad rows removed (see `data/numbers.json` → `excluded`). Totals: **112,159 people · 523 events · 481 companies · 28 countries (29 Jul – 28 Oct 2026); 35,275 in the last 30 days.**

## Text
- `x-5-day-pack.md`: 5 X posts (Thu 29 Oct – Mon 2 Nov), each with its time, asset, link reply and 3 prepared replies.
- `playbook.md`: daily routine, where to reply on X, Reddit rules, Show HN, LinkedIn, the @LayoffTracker handle, what to do when a post takes off, KPIs, and a short research section.

## Images (`images/`)
- `a-30day-1600x900.png` / `a-30day-1080x1350.png`: 35,275 people in 30 days, 49 an hour, as a dot matrix (1 dot = 100 people; AmEx in red).
- `b-industries-1600x900.png` / `b-industries-1080x1350.png`: "Not a tech story anymore". Tech is 9.6% of the people laid off, and finance cut more.
- `c-companies-1600x900.png` / `c-companies-1080x1350.png`: top 10 companies by people laid off. Barclays is #1 with 5,000.
- `d-countries-1600x900.png` / `d-countries-1080x1350.png`: 51% of the people are outside the US, with the top 10 countries.
- `e-massive-1600x900.png` / `e-massive-1080x1350.png`: "Headlines say 'massive'" next to the real headcounts. The median layoff is 108 people.
- `f-30day-story-1080x1920.png`: a 9:16 story version of (a).

## Video (`video/`)
- `globe-1080x1920.mp4`: 18 s, H.264 yuv420p, 6.1 MB. A dot-matrix globe where layoffs pop in by date, with a counter, a date ticker, company flashes, the hook card and an end card.
- `globe-1920x1080.mp4`: the same in 16:9, 5.9 MB. Use this one on X, LinkedIn and Reddit.

## X profile (`profile/`)
- `header-1500x500.png`: the @LayoffTracker banner. The text is right of centre, clear of the avatar and crop zones.
- `avatar-400.png` / `avatar-1024.png`: a dot globe with one red pulse. It holds up when cropped to a circle and at 48px.

## Source and data (`src/`, `data/`)
- `data/data-2026-10-29.json`: the data.json snapshot every number comes from.
- `data/numbers.json`: every derived number, the excluded rows with reasons, and the kept events.
- `src/derive.py`: snapshot → `numbers.json` (filters, exclusions, totals, top lists).
- `src/cards.py`: `numbers.json` → the 11 PNG cards.
- `src/profile.py`: the header and avatars.
- `src/video.py`: `python3 src/video.py v|h` renders the video by piping frames to ffmpeg (no frames go to disk; it stops if less than 1.5 GB of RAM is free). The ffmpeg binary is borrowed from shorts-factory's venv; set `FFMPEG=` to override.

To refresh, run the command at the top of `x-5-day-pack.md`. Known nits: the 16:9 hook text sits centred on the frame rather than on the globe, and there's a faint dotted ring near the south pole of the globe.
