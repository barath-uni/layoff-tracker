"""Static site generator: data/radar.db -> dist/ (HTML pages, data.json, share-card PNGs)."""
import functools
import html
import http.server
import json
import os
import re
import shutil
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from urllib.parse import quote

from . import og
from .db import connect
from .ref import TIER_LABEL
from .util import DIST, SITE, TODAY, YEAR_START, slugify

SITE_URL = os.environ.get("SITE_URL", "http://localhost:8000").rstrip("/")
NAME = "layoff-radar"
e = html.escape
LABEL_STEPS = {"Official": 4, "Corroborated": 3, "Reported": 2, "Unverified": 1}
TIER_RANK = {"official": 0, "major": 1, "news": 2, "aggregator": 3, "social": 4, "filing-nonworkforce": 5}


def fmt(n):
    return f"{n:,}" if n is not None else "–"


def compact(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".replace(".0M", "M")
    if n >= 10_000:
        return f"{round(n / 1000)}K"
    if n >= 1000:
        return f"{n / 1000:.1f}K".replace(".0K", "K")
    return str(n)


def nice_date(s):
    return date.fromisoformat(s).strftime("%b %-d, %Y")


def short_date(s):
    return date.fromisoformat(s).strftime("%b %-d")


# ------------------------------------------------------------------ data
def load():
    con = connect()
    evs = [dict(r) for r in con.execute(
        "SELECT * FROM events WHERE visible = 1 AND start >= ? ORDER BY start DESC, headcount DESC",
        (YEAR_START.isoformat(),))]
    src = defaultdict(list)
    for r in con.execute("""SELECT ec.event_id, c.headcount, c.pct, c.speculative, c.date, i.tier, i.source, i.publisher,
                            i.url, i.title, i.meta FROM event_claims ec JOIN claims c ON c.id = ec.claim_id
                            JOIN items i ON i.id = c.item_id"""):
        src[r["event_id"]].append(dict(r))
    for ev in evs:
        seen, rows = set(), []
        for s in sorted(src[ev["id"]], key=lambda s: (TIER_RANK.get(s["tier"], 9), s["date"])):
            k = (s["publisher"], re.sub(r"\W+", "", (s["title"] or "").lower())[:60], s["url"] if s["tier"] == "official" else "")
            if k in seen or s["tier"] == "filing-nonworkforce" and ev["has_official"] == 0:
                continue
            seen.add(k)
            if s["source"] == "hn":
                s["hn"] = json.loads(s["meta"] or "{}").get("hn")
            rows.append(s)
        ev["sources"] = rows
    run = con.execute("SELECT at FROM runs ORDER BY id DESC LIMIT 1").fetchone()
    updated = datetime.fromisoformat(run["at"]) if run else datetime.now(timezone.utc)
    return evs, updated


def week_index(d):
    start = YEAR_START - timedelta(days=YEAR_START.weekday())
    return (date.fromisoformat(d) - start).days // 7


def stats(evs):
    counted = [x for x in evs if x["headcount"]]
    d30 = (TODAY - timedelta(days=30)).isoformat()
    d60 = (TODAY - timedelta(days=60)).isoformat()
    s = {
        "ytd": sum(x["headcount"] for x in counted),
        "d30": sum(x["headcount"] for x in counted if x["start"] >= d30),
        "prev30": sum(x["headcount"] for x in counted if d60 <= x["start"] < d30),
        "events": len(evs),
        "events30": sum(1 for x in evs if x["start"] >= d30),
        "companies": len({x["slug"] for x in evs}),
        "official_share": round(100 * sum(x["headcount"] for x in counted if x["label"] in ("Official", "Corroborated"))
                                / max(1, sum(x["headcount"] for x in counted))),
        "undisclosed": sum(1 for x in evs if not x["headcount"]),
    }
    nweeks = week_index(TODAY.isoformat()) + 1
    weekly = [0] * nweeks
    week_top = [None] * nweeks
    for x in counted:
        w = week_index(x["start"])
        if 0 <= w < nweeks:
            weekly[w] += x["headcount"]
            if not week_top[w] or x["headcount"] > week_top[w][1]:
                week_top[w] = (x["company"], x["headcount"])
    s["weekly"], s["week_top"] = weekly, week_top
    comp = defaultdict(lambda: {"n": 0, "events": 0, "latest": "", "company": "", "industry": "", "country": ""})
    for x in evs:
        c = comp[x["slug"]]
        c["n"] += x["headcount"] or 0
        c["events"] += 1
        c["company"], c["industry"], c["country"] = x["company"], x["industry"], x["country"]
        c["latest"] = max(c["latest"], x["start"])
        c["slug"] = x["slug"]
    s["companies_list"] = sorted(comp.values(), key=lambda c: (-c["n"], c["company"]))
    return s


# ------------------------------------------------------------------ components
ICON = {
    "x": '<svg width="14" height="14" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M18.24 2.25h3.31l-7.23 8.26 8.5 11.24h-6.65l-5.21-6.82-5.97 6.82H1.68l7.73-8.84L1.25 2.25h6.83l4.71 6.23zm-1.16 17.52h1.83L7.08 4.13H5.12z"/></svg>',
    "in": '<svg width="14" height="14" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M20.45 20.45h-3.55v-5.57c0-1.33-.03-3.04-1.85-3.04-1.85 0-2.14 1.45-2.14 2.94v5.67H9.35V9h3.41v1.56h.05c.48-.9 1.64-1.85 3.37-1.85 3.6 0 4.27 2.37 4.27 5.46zM5.34 7.43a2.06 2.06 0 1 1 0-4.12 2.06 2.06 0 0 1 0 4.12zM7.12 20.45H3.56V9h3.56z"/></svg>',
    "link": '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M10 13a5 5 0 0 0 7.07 0l3-3a5 5 0 0 0-7.07-7.07l-1.5 1.5"/><path d="M14 11a5 5 0 0 0-7.07 0l-3 3a5 5 0 0 0 7.07 7.07l1.5-1.5"/></svg>',
    "img": '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M12 3v12m0 0-4-4m4 4 4-4M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/></svg>',
    "share": '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M4 12v7a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-7M16 6l-4-4-4 4M12 2v13"/></svg>',
    "theme": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 3a9 9 0 0 0 0 18z" fill="currentColor"/></svg>',
}
LOGO = ('<svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true"><path d="M3.5 15a9 9 0 0 1 17 0" fill="none" '
        'stroke="currentColor" stroke-width="2" stroke-linecap="round" opacity=".45"/><path d="M7.5 15a5 5 0 0 1 9 0" fill="none" '
        'stroke="currentColor" stroke-width="2" stroke-linecap="round" opacity=".7"/><circle cx="12" cy="15" r="2.4" fill="var(--accent)"/></svg>')
FAVICON = ("data:image/svg+xml," + quote('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><rect width="24" height="24" rx="6" '
           'fill="#0d0d0d"/><path d="M4.5 16a8 8 0 0 1 15 0" fill="none" stroke="#f0efec" stroke-width="2" stroke-linecap="round"/>'
           '<circle cx="12" cy="16" r="2.6" fill="#e66767"/></svg>'))


def share_buttons(url, text, card=None, label_x="Post on X"):
    xu = f"https://x.com/intent/post?text={quote(text)}&url={quote(url)}"
    li = f"https://www.linkedin.com/sharing/share-offsite/?url={quote(url)}"
    out = [f'<a class="btn primary" href="{e(xu)}" target="_blank" rel="noopener">{ICON["x"]}{label_x}</a>',
           f'<a class="btn" href="{e(li)}" target="_blank" rel="noopener">{ICON["in"]}LinkedIn</a>',
           f'<button class="btn" type="button" data-copy="{e(url)}">{ICON["link"]}Copy link</button>']
    if card:
        out.append(f'<a class="btn" href="{e(card)}" download>{ICON["img"]}Card</a>')
    return '<div class="share-row">' + "".join(out) + "</div>"


def conf_badge(ev):
    steps = LABEL_STEPS.get(ev["label"], 1)
    bars = "".join(f'<i class="{"on" if i < steps else ""}"></i>' for i in range(4))
    return (f'<span class="conf" title="Confidence {ev["confidence"]}/100 from {ev["n_publishers"]} independent '
            f'source{"s" if ev["n_publishers"] != 1 else ""}"><span class="meter">{bars}</span>{e(ev["label"])}</span>')


def headcount_html(ev, big=False):
    if ev["headcount"]:
        return f'{fmt(ev["headcount"])}'
    if ev["pct"]:
        return f'{ev["pct"]:g}%'
    return "Undisclosed"


def headcount_sub(ev):
    if ev["headcount"] and ev["low"] and ev["high"] and ev["low"] != ev["high"]:
        return f'sources say {fmt(ev["low"])}–{fmt(ev["high"])}'
    if ev["headcount"] and ev["pct"]:
        return f'{ev["pct"]:g}% of staff'
    if not ev["headcount"] and ev["pct"]:
        return "of staff, headcount not given"
    return "people" if ev["headcount"] else "no number yet"


def feed_row(ev):
    return (f'<a class="row" href="/company/{e(ev["slug"])}/">'
            f'<span class="when">{short_date(ev["start"])}</span>'
            f'<span><span class="co">{e(ev["company"])}</span><span class="hl">{e(ev["headline"])}</span>'
            f'<span class="meta">{conf_badge(ev)}<span>{e(ev["industry"])}</span><span>{e(ev["country"])}</span>'
            f'<span>{ev["n_publishers"]} source{"s" if ev["n_publishers"] != 1 else ""}</span></span></span>'
            f'<span class="num"><b>{headcount_html(ev)}</b><small>{e(headcount_sub(ev))}</small></span></a>')


def bars_html(rows, key, link=None, limit=10):
    if not rows:
        return '<p class="empty">No events match.</p>'
    vmax = max(r[1] for r in rows) or 1
    out = []
    for name, val, extra in rows[:limit]:
        w = max(0.6, 100 * val / vmax)
        inner = (f'<span class="name">{e(name)}</span><span class="track"><span class="fill" style="width:{w:.1f}%"></span></span>'
                 f'<span class="val">{fmt(val)}</span>')
        if link:
            out.append(f'<a class="bar-row" href="{e(link(extra))}" title="{e(name)}: {fmt(val)} people">{inner}</a>')
        else:
            out.append(f'<button class="bar-row" type="button" data-{key}="{e(name)}" title="Filter by {e(name)}">{inner}</button>')
    return "".join(out)


def weekly_chart(weekly, week_top):
    W, H, L, B, T = 1000, 240, 44, 26, 12
    n = len(weekly)
    vmax = max(weekly or [1]) or 1
    step = 10 ** max(0, len(str(int(vmax))) - 1)
    top = ((vmax // step) + 1) * step
    if top / 2 >= vmax:
        top = top / 2
    slot = (W - L) / n
    bw = min(24, max(4, slot * 0.62))
    ph = H - B - T
    parts = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="People laid off per week in {YEAR_START.year}">']
    for f in (0, 0.5, 1):
        y = T + ph * (1 - f)
        parts.append(f'<line class="{"baseline" if f == 0 else "gridline"}" x1="{L}" x2="{W}" y1="{y:.1f}" y2="{y:.1f}"/>')
        parts.append(f'<text class="tick" x="{L - 8}" y="{y + 4:.1f}" text-anchor="end">{compact(int(top * f))}</text>')
    wk0 = YEAR_START - timedelta(days=YEAR_START.weekday())
    last_month = None
    for i, v in enumerate(weekly):
        x = L + slot * i
        ws = wk0 + timedelta(days=7 * i)
        if ws.month != last_month and (ws.day <= 7 or i == 0):
            parts.append(f'<text class="tick" x="{x + slot / 2:.1f}" y="{H - 6}" text-anchor="middle">{ws.strftime("%b")}</text>')
            last_month = ws.month
        h = ph * v / top if v else 0
        bx = x + (slot - bw) / 2
        tip = {"w": f'Week of {ws.strftime("%b %-d")}', "v": v,
               "t": f'Largest: {week_top[i][0]} ({fmt(week_top[i][1])})' if week_top[i] else ""}
        parts.append(f'<rect class="hit" x="{x:.1f}" y="{T}" width="{slot:.1f}" height="{ph}" data-tip=\'{e(json.dumps(tip))}\' tabindex="0"/>')
        if h >= 1:
            r = min(4, bw / 2, h)
            y0, y1 = T + ph - h, T + ph
            parts.append(f'<path class="col{" dim" if i < n - 5 else ""}" d="M{bx:.1f},{y1:.1f} V{y0 + r:.1f} Q{bx:.1f},{y0:.1f} {bx + r:.1f},{y0:.1f} '
                         f'H{bx + bw - r:.1f} Q{bx + bw:.1f},{y0:.1f} {bx + bw:.1f},{y0 + r:.1f} V{y1:.1f} Z"/>')
    parts.append("</svg>")
    return '<div class="chart" data-chart>' + "".join(parts) + '<div class="tip" role="status"></div></div>'


# ------------------------------------------------------------------ pages
def page(path, title, desc, body, og_img="/og/home.png", page_class=""):
    url = SITE_URL + path
    img = SITE_URL + og_img
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{e(url)}">
<meta property="og:type" content="website"><meta property="og:site_name" content="{NAME}">
<meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{e(url)}"><meta property="og:image" content="{e(img)}">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{e(title)}">
<meta name="twitter:description" content="{e(desc)}"><meta name="twitter:image" content="{e(img)}">
<meta name="theme-color" content="#0d0d0d" media="(prefers-color-scheme: dark)">
<meta name="theme-color" content="#f9f9f7" media="(prefers-color-scheme: light)">
<link rel="icon" href="{FAVICON}">
<link rel="preload" href="/static/fonts/geist-600.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/static/style.css">
<script>try{{var t=localStorage.getItem("theme");if(t)document.documentElement.dataset.theme=t}}catch(_){{}}</script>
</head><body class="{page_class}">
<header class="wrap top">
  <a class="brand" href="/">{LOGO}<span>{NAME}</span></a>
  <nav class="nav"><a href="/companies/">Companies</a><a class="hide-sm" href="/methodology/">Methodology</a>
  <button class="icon-btn" type="button" data-theme-toggle aria-label="Toggle dark mode">{ICON["theme"]}</button></nav>
</header>
<main class="wrap">{body}</main>
<footer><div class="wrap"><span>{NAME} tracks layoffs from public filings, WARN notices and news. Every number links to its sources.</span>
<span><a href="/methodology/">Methodology</a> · <a href="/data.json">Data (JSON)</a></span></div></footer>
<div class="toast" role="status" aria-live="polite"></div>
<script src="/static/app.js" defer></script>
</body></html>"""


def home(evs, s, updated, industries, countries):
    url = SITE_URL + "/"
    delta = s["d30"] - s["prev30"]
    dtxt = (f'{"+" if delta >= 0 else "−"}{compact(abs(delta))} vs prior 30 days') if s["prev30"] else ""
    share_text = (f"{fmt(s['ytd'])} people laid off in {YEAR_START.year} so far, across {fmt(s['companies'])} companies. "
                  f"Every number links to its sources.")
    tiles = [
        ("Last 30 days", fmt(s["d30"]), dtxt or "people", "/stat/30d/"),
        ("Layoff events", fmt(s["events"]), f'{s["events30"]} in the last 30 days', "/stat/events/"),
        ("Companies", fmt(s["companies"]), "with at least one event", "/companies/"),
        ("Official or corroborated", f'{s["official_share"]}%', "of tracked headcount", "/methodology/"),
    ]
    tiles_html = "".join(
        f'<div class="tile"><div class="label">{e(lbl)}</div><div class="value">{v}</div><div class="sub">{e(sub)}</div>'
        f'<a class="icon-btn share" href="{href}" aria-label="Share {e(lbl)}">{ICON["share"]}</a></div>'
        for lbl, v, sub, href in tiles)
    top = [(c["company"], c["n"], c["slug"]) for c in s["companies_list"] if c["n"]][:10]
    feed = "".join(feed_row(x) for x in evs[:30])
    opts_i = "".join(f'<option>{e(n)}</option>' for n, _, _ in industries)
    opts_c = "".join(f'<option>{e(n)}</option>' for n, _, _ in countries)
    slim = [{"s": x["slug"], "c": x["company"], "d": x["start"], "n": x["headcount"], "lo": x["low"], "hi": x["high"],
             "p": x["pct"], "l": x["label"], "cf": x["confidence"], "i": x["industry"], "k": x["country"], "h": x["headline"],
             "np": x["n_publishers"]} for x in evs]
    body = f"""
<section class="hero">
  <div class="eyebrow"><span class="live" aria-hidden="true"></span>Tracked layoffs in {YEAR_START.year} · updated {updated.strftime("%b %-d, %H:%M")} UTC</div>
  <h1 class="big" data-count="{s['ytd']}">{fmt(s['ytd'])}</h1>
  <p class="lede">people laid off this year across <strong>{fmt(s['companies'])} companies</strong>, merged from SEC filings,
  WARN notices and {fmt(sum(x['n_publishers'] for x in evs))} news reports. Every number links to its sources.</p>
  <div class="hero-actions">{share_buttons(url, share_text, "/og/home.png")}</div>
  <div class="tiles">{tiles_html}</div>
</section>
<section class="section">
  <div class="card"><h3>People laid off per week</h3><p class="cap">By announcement date, {YEAR_START.year}. The last five weeks are highlighted.</p>
  {weekly_chart(s['weekly'], s['week_top'])}</div>
</section>
<section class="section">
  <div class="section-head"><h2>Biggest layoffs of {YEAR_START.year}</h2><p><a href="/companies/">All companies →</a></p></div>
  <div class="card"><div class="bars">{bars_html(top, "company", link=lambda slug: f"/company/{slug}/")}</div></div>
</section>
<section class="section" id="explore">
  <div class="section-head"><h2>Explore</h2><p data-fsum></p></div>
  <div class="filters" role="group" aria-label="Filters">
    <div class="seg" data-range><button type="button" data-r="30" aria-pressed="false">30 days</button><button type="button" data-r="90" aria-pressed="false">90 days</button><button type="button" data-r="ytd" aria-pressed="true">{YEAR_START.year}</button></div>
    <select class="select" data-f="i" aria-label="Industry"><option value="">All industries</option>{opts_i}</select>
    <select class="select" data-f="k" aria-label="Country"><option value="">All countries</option>{opts_c}</select>
    <input class="search" type="search" placeholder="Search companies" data-f="q" aria-label="Search companies">
  </div>
  <div class="grid2">
    <div class="card"><h3>By industry</h3><p class="cap">People laid off. Tap a bar to filter.</p><div class="bars" data-bars="i">{bars_html(industries, "i")}</div></div>
    <div class="card"><h3>By country</h3><p class="cap">Company headquarters unless sources say otherwise.</p><div class="bars" data-bars="k">{bars_html(countries, "k")}</div></div>
  </div>
  <div class="section-head" style="margin-top:28px"><h2>Latest events</h2><p>Newest first</p></div>
  <div class="feed" data-feed>{feed}<button class="more" type="button" data-more>Show more</button></div>
</section>
<script type="application/json" id="events">{json.dumps(slim, separators=(",", ":")).replace("</", "<\\/")}</script>"""
    title = f"{fmt(s['ytd'])} people laid off in {YEAR_START.year}: {NAME}"
    desc = f"Live tracker of {YEAR_START.year} layoffs across {s['companies']} companies. Consensus numbers from filings, WARN notices and news, each linked to its sources."
    return page("/", title, desc, body, "/og/home.png", "home")


def source_row(src):
    tier = "official" if src["tier"] == "official" else ""
    claim = fmt(src["headcount"]) if src["headcount"] else (f'{src["pct"]:g}%' if src["pct"] else "–")
    spec = " · speculative" if src["speculative"] else ""
    hn = f' · <a href="{e(src["hn"])}" target="_blank" rel="noopener">HN thread</a>' if src.get("hn") else ""
    return (f'<li><span><a class="t" href="{e(src["url"])}" target="_blank" rel="noopener nofollow">{e(src["title"])}</a>'
            f'<span class="p"><span class="tier {tier}">{e(TIER_LABEL.get(src["tier"], "Filing"))}</span>{e(src["publisher"])} · '
            f'{short_date(src["date"])}{spec}{hn}</span></span><span class="c">{claim}</span></li>')


def company_page(slug, cevs, s):
    c = cevs[0]
    total = sum(x["headcount"] or 0 for x in cevs)
    url = f"{SITE_URL}/company/{slug}/"
    best = max(cevs, key=lambda x: LABEL_STEPS.get(x["label"], 0))
    number = fmt(total) if total else (f'{cevs[0]["pct"]:g}%' if cevs[0]["pct"] else "Undisclosed")
    share_text = (f"{c['company']} has laid off {fmt(total)} people in {YEAR_START.year}, per {NAME}'s source consensus."
                  if total else f"{c['company']} layoffs in {YEAR_START.year}: every report and filing in one place.")
    timeline = []
    for ev in cevs:
        srcs = "".join(source_row(x) for x in ev["sources"][:40])
        more = f'<p class="cap" style="margin:10px 0 0">+{len(ev["sources"]) - 40} more sources</p>' if len(ev["sources"]) > 40 else ""
        span = short_date(ev["start"]) + (f' – {short_date(ev["end"])}' if ev["end"] != ev["start"] else "")
        timeline.append(f"""<div class="ev"><div class="card">
  <div class="ev-top"><span class="d">{span}</span>{conf_badge(ev)}</div>
  <div class="ev-top" style="margin-top:6px"><span class="n">{headcount_html(ev)}</span><span class="range">{e(headcount_sub(ev))}</span></div>
  <p class="hl" style="margin:6px 0 0;color:var(--ink-2)">{e(ev["headline"])}</p>
  <ul class="src">{srcs}</ul>{more}</div></div>""")
    body = f"""
<p class="crumbs"><a href="/">Home</a> / <a href="/companies/">Companies</a></p>
<section class="co-head">
  <h1>{e(c['company'])}</h1>
  <div class="facts"><span>{e(c['industry'])}</span><span>{e(c['country'])}</span><span>{len(cevs)} event{"s" if len(cevs) != 1 else ""} in {YEAR_START.year}</span>{conf_badge(best)}</div>
  <div class="co-total">
    <div><div class="k">Laid off in {YEAR_START.year}</div><div class="v">{number}</div></div>
    <div><div class="k">Latest</div><div class="v" style="font-size:clamp(24px,4vw,34px);padding-top:8px">{nice_date(cevs[0]['start'])}</div></div>
  </div>
  <div class="hero-actions">{share_buttons(url, share_text, f"/og/company/{slug}.png")}</div>
</section>
<section class="section"><div class="section-head"><h2>Timeline and sources</h2><p>Each event shows the consensus number and every source behind it.</p></div>
<div class="timeline">{"".join(timeline)}</div></section>"""
    title = f"{c['company']} layoffs {YEAR_START.year}: {number}" + (" people" if total else "")
    desc = f"{c['company']} layoffs in {YEAR_START.year}: {len(cevs)} event(s), consensus headcount, confidence and every source."
    return page(f"/company/{slug}/", title, desc, body, f"/og/company/{slug}.png")


def companies_page(s):
    rows = "".join(
        f'<tr data-name="{e(c["company"].lower())}"><td><a href="/company/{e(c["slug"])}/">{e(c["company"])}</a></td>'
        f'<td>{e(c["industry"])}</td><td>{e(c["country"])}</td><td class="r">{c["events"]}</td>'
        f'<td class="r">{fmt(c["n"]) if c["n"] else "–"}</td><td class="r">{short_date(c["latest"])}</td></tr>'
        for c in s["companies_list"])
    body = f"""<div class="prose"><h1>Companies</h1><p>{fmt(len(s['companies_list']))} companies with at least one tracked layoff in {YEAR_START.year}, ranked by people laid off.</p></div>
<div class="filters"><input class="search" type="search" placeholder="Search {len(s['companies_list'])} companies" data-table-search aria-label="Search companies"></div>
<div class="card scroll-x" style="padding:6px 10px"><table class="list" data-table><thead><tr><th>Company</th><th>Industry</th><th>Country</th>
<th class="r">Events</th><th class="r">People</th><th class="r">Latest</th></tr></thead><tbody>{rows}</tbody></table></div>"""
    return page("/companies/", f"All companies with layoffs in {YEAR_START.year}: {NAME}",
                f"{len(s['companies_list'])} companies with tracked layoffs in {YEAR_START.year}.", body)


def stat_page(key, eyebrow, number, sub, share_text, cta=("/", "See the full tracker")):
    url = f"{SITE_URL}/stat/{key}/"
    body = f"""<section class="hero" style="padding-top:64px">
<div class="eyebrow"><span class="live" aria-hidden="true"></span>{e(eyebrow)}</div>
<h1 class="big">{e(number)}</h1><p class="lede">{e(sub)}</p>
<div class="hero-actions">{share_buttons(url, share_text, f"/og/stat-{key}.png")}<a class="btn" href="{cta[0]}">{e(cta[1])} →</a></div>
<img class="og-preview" src="/og/stat-{key}.png" alt="Share card: {e(eyebrow)} {e(number)}" width="1200" height="630" loading="lazy">
</section>"""
    return page(f"/stat/{key}/", f"{eyebrow}: {number}", sub, body, f"/og/stat-{key}.png")


def methodology_page(s, counts):
    src_rows = "".join(f"<li><strong>{e(k)}</strong>: {fmt(v)} items</li>" for k, v in counts)
    body = f"""<div class="prose">
<h1>Methodology</h1>
<p>{NAME} counts layoffs from public records and reporting. It never estimates numbers that no source has stated.
Every figure on the site links to the sources it came from.</p>
<h2>Sources</h2><ul>{src_rows}</ul>
<p>Official sources are SEC 8-K filings under Item 2.05 (exit or disposal activities) and state WARN notices
(California EDD, Maryland DOL). News comes from Google News searches across several English editions, plus Hacker News and r/layoffs as weak signals.
X and LinkedIn are not used: their APIs are paid or prohibit this use.</p>
<h2>From reports to events</h2>
<p>Each headline is parsed for a company, a headcount or percentage, and a date. Lists, opinion pieces, buyout offers and
denials are discarded. Reports about the same company within two weeks of each other form one event. Later coverage that repeats
an earlier figure, or revises it on the same scale, is folded into the original event instead of being counted twice.
Numbers that describe several years, a past total or a long-term target ("by 2030", "over the past year") are not counted.</p>
<h2>Consensus number</h2>
<p>The event's number is the weighted median of the firm claims. Filings outrank news, and news outranks rumour. Figures far from the median
are ignored. When sources disagree, the page shows the range (for example, "sources say 4,000–15,000"). WARN notices are only a floor:
they cover one state, so they never lower a company-wide figure. Figures above 50,000 need at least three independent publishers, including a major outlet.</p>
<h2>Confidence</h2>
<p>Each source has a weight: official record 1.0, major outlet 0.7, other news 0.45, Hacker News 0.25, Reddit 0.15. Speculative wording
("reportedly", "plans", "may") cuts a source's weight by 40%. Confidence = 1 − ∏(1 − weight) over independent publishers.</p>
<ul><li><strong>Official</strong>: a WARN notice or an SEC filing that mentions the workforce.</li>
<li><strong>Corroborated</strong>: three or more independent publishers, or two including a major outlet.</li>
<li><strong>Reported</strong>: two independent publishers.</li></ul>
<p>Anything weaker is not shown. Single-source stories and social posts on their own never appear, and 8-K restructuring filings that don't mention people are left out.
In {YEAR_START.year}, {fmt(s['undisclosed'])} shown events have no stated headcount. They count as events but add nothing to the totals.</p>
<h2>Known limits</h2>
<ul><li>Totals are a floor: many layoffs are never reported, and WARN coverage is limited to two states for now.</li>
<li>Country is the company's headquarters unless a filing or the sources say where the cuts happen.</li>
<li>Headline parsing is rule-based. An optional LLM extractor can be plugged in (<code>LR_LLM_CMD</code>) but is off.</li></ul>
<p>Data: <a href="/data.json">data.json</a> holds every shown event with its sources.</p></div>"""
    return page("/methodology/", f"Methodology: {NAME}", "How layoff-radar turns filings, WARN notices and news into sourced consensus numbers.", body)


# ------------------------------------------------------------------ build
def build():
    evs, updated = load()
    s = stats(evs)
    if DIST.exists():
        shutil.rmtree(DIST)
    (DIST / "og" / "company").mkdir(parents=True)
    shutil.copytree(SITE / "static", DIST / "static")

    def agg(key):
        acc = defaultdict(int)
        for x in evs:
            if x["headcount"]:
                acc[x[key]] += x["headcount"]
        return sorted(((k, v, k) for k, v in acc.items()), key=lambda r: (r[0] == "Unknown", -r[1]))

    industries, countries = agg("industry"), agg("country")
    stamp = updated.strftime("%b %-d, %Y")

    def write(path, text):
        p = DIST / path.strip("/") / "index.html" if not path.endswith(".html") else DIST / path.strip("/")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    write("/", home(evs, s, updated, industries, countries))
    og.card(DIST / "og/home.png", f"People laid off in {YEAR_START.year}, tracked", fmt(s["ytd"]),
            f"across {fmt(s['companies'])} companies · {fmt(s['events'])} events", stamp, spark=s["weekly"])

    by_slug = defaultdict(list)
    for x in evs:
        by_slug[x["slug"]].append(x)
    for slug, cevs in by_slug.items():
        write(f"/company/{slug}/", company_page(slug, cevs, s))
        total = sum(x["headcount"] or 0 for x in cevs)
        num = fmt(total) if total else (f'{cevs[0]["pct"]:g}%' if cevs[0]["pct"] else "Undisclosed")
        og.card(DIST / f"og/company/{slug}.png", f"{cevs[0]['company']} layoffs in {YEAR_START.year}", num,
                f"{len(cevs)} event{'s' if len(cevs) != 1 else ''} · {cevs[0]['label'].lower()} · "
                f"{sum(x['n_publishers'] for x in cevs)} sources", stamp, quote=cevs[0]["headline"])
    write("/companies/", companies_page(s))

    stat_defs = [
        ("ytd", f"People laid off in {YEAR_START.year}", fmt(s["ytd"]), f"across {fmt(s['companies'])} companies, every number sourced",
         f"{fmt(s['ytd'])} people laid off in {YEAR_START.year} so far."),
        ("30d", "People laid off in the last 30 days", fmt(s["d30"]), f"in {s['events30']} layoff events since {short_date((TODAY - timedelta(days=30)).isoformat())}",
         f"{fmt(s['d30'])} people laid off in the last 30 days."),
        ("events", f"Layoff events in {YEAR_START.year}", fmt(s["events"]), f"at {fmt(s['companies'])} companies, each confirmed by a filing or several outlets",
         f"{fmt(s['events'])} layoff events in {YEAR_START.year} so far."),
    ]
    for name, v, _ in industries[:6]:
        n_co = len({x["slug"] for x in evs if x["industry"] == name})
        stat_defs.append((f"industry-{slugify(name)}", f"{name} layoffs in {YEAR_START.year}", fmt(v),
                          f"across {n_co} companies", f"{fmt(v)} people laid off in {name.lower()} in {YEAR_START.year}."))
    for key, eyebrow, number, sub, text in stat_defs:
        write(f"/stat/{key}/", stat_page(key, eyebrow, number, sub, text + f" Sourced tracker by {NAME}:"))
        og.card(DIST / f"og/stat-{key}.png", eyebrow, number, sub, stamp, spark=s["weekly"])

    con = connect()
    counts = [(k, v) for k, v in con.execute(
        "SELECT CASE source WHEN 'gnews' THEN 'News (Google News)' WHEN 'edgar' THEN 'SEC 8-K Item 2.05' "
        "WHEN 'warn_ca' THEN 'WARN: California' WHEN 'warn_md' THEN 'WARN: Maryland' WHEN 'hn' THEN 'Hacker News' "
        "ELSE 'Reddit r/layoffs' END, COUNT(*) FROM items GROUP BY source ORDER BY 2 DESC")]
    write("/methodology/", methodology_page(s, counts))
    write("/404.html", page("/404.html", f"Not found: {NAME}", "Page not found.",
                            '<div class="prose"><h1>Not found</h1><p>That page does not exist. <a href="/">Back to the tracker</a>.</p></div>'))
    data = {"updated": updated.isoformat(), "totals": {k: s[k] for k in ("ytd", "d30", "events", "companies")},
            "events": [{k: x[k] for k in ("slug", "company", "start", "end", "headcount", "low", "high", "pct", "confidence",
                                          "label", "industry", "country", "headline")}
                       | {"sources": [{"publisher": r["publisher"], "tier": r["tier"], "url": r["url"], "title": r["title"],
                                       "date": r["date"], "headcount": r["headcount"], "pct": r["pct"]} for r in x["sources"]]}
                       for x in evs]}
    (DIST / "data.json").write_text(json.dumps(data, separators=(",", ":")))
    print(f"built {len(by_slug)} company pages, {len(stat_defs)} stat pages; ytd={s['ytd']:,} d30={s['d30']:,} events={s['events']}")


class Handler(http.server.SimpleHTTPRequestHandler):
    def send_error(self, code, message=None, explain=None):
        if code == 404 and (DIST / "404.html").exists():
            body = (DIST / "404.html").read_bytes()
            self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().send_error(code, message, explain)


def serve(port=8000):
    """Local preview of the static build (any static host works the same way)."""
    h = functools.partial(Handler, directory=str(DIST))
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), h) as srv:
        print(f"serving {DIST} at http://127.0.0.1:{port}")
        srv.serve_forever()
