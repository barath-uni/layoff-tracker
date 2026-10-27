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
from .places import HQ, WORKFORCE, geocode
from .ref import TIER_LABEL, US_STATE_CODES
from .util import DATA, DIST, SITE, TODAY, YEAR_START, slugify

from .config import BRAND as NAME, SITE_URL
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
    for ev in evs:
        # Announced multi-year plans ("35,000 jobs by 2030") are shown but never counted: the number moves to plan_n.
        ev["plan_n"] = ev["plan_pct"] = None
        if ev["kind"] == "plan":
            ev["plan_n"], ev["plan_pct"] = ev["headcount"], ev["pct"]
            ev["headcount"] = ev["low"] = ev["high"] = ev["pct"] = None
            ev["label"] = ev["label"] if ev["label"] != "Official" else "Official"
    for ev in evs:
        ev["lat"] = ev["lon"] = None
        for place in event_places(ev):
            hit = geocode(con, place)
            if hit:
                ev["lat"], ev["lon"] = hit
                ev["place"] = place
                break
        ev["pct_show"], ev["pct_note"] = staff_share(ev)
    run = con.execute("SELECT at FROM runs ORDER BY id DESC LIMIT 1").fetchone()
    updated = datetime.fromisoformat(run["at"]) if run else datetime.now(timezone.utc)
    return evs, updated


def _us(loc):
    """'Palo Alto, CA' -> ['Palo Alto, CA, USA', 'CA, USA']"""
    if not loc or "," not in loc:
        return []
    city, st = [x.strip() for x in loc.rsplit(",", 1)]
    if st not in US_STATE_CODES:
        return []
    return [f"{city}, {st}, USA", f"{st}, USA"]


def event_places(ev):
    """Most specific place first: WARN site, curated HQ, SEC filer address, then country."""
    out = []
    for s in ev["sources"]:
        if s["source"].startswith("warn"):
            out += _us(json.loads(s["meta"] or "{}").get("location"))
            break
    if ev["slug"] in HQ:
        out.append(HQ[ev["slug"]])
    for s in ev["sources"]:
        if s["source"] == "edgar":
            out += _us(json.loads(s["meta"] or "{}").get("location"))
            break
    if ev["country"] and ev["country"] not in ("Unknown",) and "multi" not in ev["country"]:
        out.append(ev["country"])
    return out


def staff_share(ev):
    """(display, note). Sourced percentage first; else computed from the curated workforce table."""
    wf = WORKFORCE.get(ev["slug"])
    if ev["pct"]:
        comp = 100 * ev["headcount"] / wf[0] if (wf and ev["headcount"]) else None
        if comp is None or comp / 3 <= ev["pct"] <= comp * 3:  # else the % describes a subset ("37% of corporate roles")
            return f'{ev["pct"]:g}%', "of staff, as reported"
    if ev["headcount"] and wf:
        p = 100 * ev["headcount"] / wf[0]
        shown = "<0.1%" if p < 0.1 else (f"≈{p:.1f}%" if p < 10 else f"≈{p:.0f}%")
        return shown, f"of ≈{wf[0]:,} staff ({wf[3] if len(wf) > 3 else 'annual report'}, FY{wf[1]})"
    return None, None


def wf_link(slug, ev):
    wf = WORKFORCE.get(slug)
    if not wf or len(wf) < 3 or "as reported" in (ev.get("pct_note") or ""):
        return ""
    return f' · <a href="{e(wf[2])}" target="_blank" rel="noopener nofollow">source</a>'


def early_warnings(evs):
    """WARN notices already filed whose layoff date is still ahead (the paid-product teaser)."""
    slug_of = {}
    for x in evs:
        for r in x["sources"]:
            if r["source"].startswith("warn"):
                slug_of[r["title"]] = x["slug"]
    out, seen = [], set()
    for r in connect().execute("""SELECT title, published, meta FROM items WHERE source LIKE 'warn%'
                                  AND json_extract(meta, '$.effective') > ? ORDER BY json_extract(meta, '$.effective')""",
                               (TODAY.isoformat(),)):
        m = json.loads(r["meta"] or "{}")
        k = (m.get("company"), m.get("effective"), m.get("location"))
        if k in seen:
            continue
        seen.add(k)
        out.append({"c": m.get("company"), "s": slug_of.get(r["title"]), "n": m.get("headcount"), "f": r["published"],
                    "e": m.get("effective"), "loc": m.get("location"), "i": m.get("industry"), "kd": m.get("kind")})
    return out


def week_index(d):
    start = YEAR_START - timedelta(days=YEAR_START.weekday())
    return (date.fromisoformat(d) - start).days // 7


def stats(evs):
    plans = [x for x in evs if x["kind"] == "plan"]
    evs = [x for x in evs if x["kind"] != "plan"]
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
    for x in plans:
        if x["slug"] not in comp:
            c = comp[x["slug"]]
            c.update(company=x["company"], industry=x["industry"], country=x["country"], latest=x["start"], slug=x["slug"])
    s["companies_list"] = sorted(comp.values(), key=lambda c: (-c["n"], c["company"]))
    s["plans"], s["plan_people"] = len(plans), sum(x["plan_n"] or 0 for x in plans)
    s["countries"] = len({x["country"] for x in evs if x["country"] and x["country"] != "Unknown"})
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


def plan_text(ev):
    when = f"by {ev['horizon']}" if ev.get("horizon") and ev["horizon"] != "multi-year" else "over several years"
    return f"announced plan, {when} · not counted"


def headcount_html(ev, big=False):
    if ev.get("plan_n"):
        return f'{fmt(ev["plan_n"])}'
    if ev.get("plan_pct"):
        return f'{ev["plan_pct"]:g}%'
    if ev["headcount"]:
        return f'{fmt(ev["headcount"])}'
    if ev["pct"]:
        return f'{ev["pct"]:g}%'
    return "Undisclosed"


def headcount_sub(ev):
    if ev["kind"] == "plan":
        return plan_text(ev)
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
def page(path, title, desc, body, og_img="/og/home.png", page_class="", wrap=True):
    url = SITE_URL + path
    img = SITE_URL + og_img
    extra_js = ("<script src=\"/static/vendor/d3-array.min.js\" defer></script><script src=\"/static/vendor/d3-geo.min.js\" defer></script>"
                "<script src=\"/static/vendor/topojson-client.min.js\" defer></script><script src=\"/static/globe.js\" defer></script><script src=\"/static/gate.js\" defer></script>"
                if page_class == "home" else "")
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
<div class="bar"><header class="wrap top">
  <a class="brand" href="/">{LOGO}<span>{NAME}</span></a>
  <nav class="nav"><a href="/companies/">Companies</a><a class="hide-sm" href="/methodology/">Methodology</a>
  <button class="icon-btn" type="button" data-theme-toggle aria-label="Toggle dark mode">{ICON["theme"]}</button></nav>
</header></div>
<main{' class="wrap"' if wrap else ''}>{body}</main>
<footer><div class="wrap"><span>{NAME} tracks layoffs from public filings, WARN notices and news. Every number links to its sources.</span>
<span><a href="/methodology/">Methodology</a> · <a href="/data.json">Data (JSON)</a></span></div></footer>
<div class="toast" role="status" aria-live="polite"></div>
{extra_js}<script src="/static/app.js" defer></script>
</body></html>"""


def ago(d_iso):
    days = (TODAY - date.fromisoformat(d_iso)).days
    return "today" if days <= 0 else "yesterday" if days == 1 else f"{days} days ago" if days < 14 else short_date(d_iso)


def rightnow_items(evs, n=4):
    out = []
    for x in [x for x in evs if x["headcount"] or x["pct_show"]][:n]:
        num = f'{fmt(x["headcount"])} jobs' if x["headcount"] else f'{x["pct_show"]} of staff'
        extra = f' · {x["pct_show"]} of staff' if x["headcount"] and x["pct_show"] else ""
        out.append(f'<li><a href="/company/{e(x["slug"])}/"><b>{e(x["company"])}</b><span>{num}{e(extra)}</span>'
                   f'<time datetime="{x["start"]}">{ago(x["start"])}</time></a></li>')
    return "".join(out)


def week_stats(evs):
    since = (TODAY - timedelta(days=7)).isoformat()
    wk = [x for x in evs if x["start"] >= since]
    people = sum(x["headcount"] or 0 for x in wk)
    by = defaultdict(int)
    for x in wk:
        by[x["company"]] += x["headcount"] or 0
    top = sorted(((k, v) for k, v in by.items() if v), key=lambda r: -r[1])
    return people, len({x["slug"] for x in wk}), top


def home(evs, s, updated, industries, countries):
    url = SITE_URL + "/"
    y = YEAR_START.year
    pace_h = s["d30"] / (30 * 24)
    every = round(3600 / pace_h) if pace_h else 0
    wk_people, wk_cos, wk_top = week_stats(evs)
    share_text = f"{fmt(s['ytd'])} people laid off in {y}. So far. Every number sourced:"
    delta = s["d30"] - s["prev30"]
    dtxt = (f'{"+" if delta >= 0 else "−"}{compact(abs(delta))} vs prior 30 days') if s["prev30"] else ""
    tiles = [
        ("Last 30 days", fmt(s["d30"]), dtxt or "people", "/stat/30d/"),
        ("This week", fmt(wk_people), f"people at {wk_cos} companies", "/stat/week/"),
        ("Layoff events", fmt(s["events"]), f'{s["events30"]} in the last 30 days', "/stat/events/"),
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
             "p": x["pct"], "ps": x["pct_show"], "pn": x["pct_note"], "l": x["label"], "cf": x["confidence"],
             "i": x["industry"], "k": x["country"], "h": x["headline"], "np": x["n_publishers"],
             "la": x["lat"], "lo2": x["lon"], "pl": x["plan_n"], "hz": x["horizon"],
             "src": [[r["publisher"], r["url"]] for r in x["sources"][:3]]} for x in evs]
    on_map = sum(1 for x in evs if x["lat"] is not None)
    iso = updated.isoformat()
    body = f"""
<section class="stage" data-stage>
  <div class="stage-in">
    <div class="stage-copy">
      <div class="eyebrow"><span class="live" aria-hidden="true"></span><span>Live</span><span aria-hidden="true">·</span><span data-ago data-updated="{iso}">updated {updated.strftime("%H:%M")} UTC</span></div>
      <h1 class="ticker"><span data-ticker data-base="{s['ytd']}" data-updated="{iso}" data-pace="{pace_h / 3600:.6f}">{fmt(s['ytd'])}</span></h1>
      <p class="kicker">people laid off in {y}. <span>So far.</span></p>
      <p class="deadpan" data-deadpan data-every="{every}" data-week="{wk_people}" data-cos="{wk_cos}">At this pace, someone loses their job every {every} seconds.</p>
      <div class="stage-share">{share_buttons(url, share_text, "/og/home.png")}<a class="btn ghost" href="/og/story-home.png" download>Story</a></div>
      <p class="fine">The counter is a live estimate at the last 30 days' pace (about {pace_h:.0f} people an hour). It resets to verified figures every hour. <a href="/methodology/">How we count</a></p>
    </div>
    <div class="globe-box" data-globe-box>
      <canvas data-globe role="img" aria-label="Map of {on_map} layoff events in {y}"></canvas>
      <div class="seg view" role="group" aria-label="Map view"><button type="button" data-view="globe" aria-pressed="true">Globe</button><button type="button" data-view="map" aria-pressed="false">Map</button></div>
      <div class="zoom" role="group" aria-label="Zoom"><button type="button" data-zoom="in" aria-label="Zoom in">+</button><button type="button" data-zoom="out" aria-label="Zoom out">−</button><button type="button" data-zoom="reset" aria-label="Reset view" hidden>⟲</button></div>
      <div class="legend"><span><i class="lg fresh"></i>last 7 days</span><span><i class="lg"></i>earlier in {y}</span><span>size = people</span></div>
      <div class="pin" data-pin hidden role="dialog" aria-label="Layoff details"></div>
    </div>
  </div>
  <div class="rightnow"><span class="rn-label"><span class="live" aria-hidden="true"></span>Right now</span><ol data-rightnow>{rightnow_items(evs)}</ol></div>
</section>
<div class="wrap">
<section class="section">
  <div class="tiles" style="margin-top:0">{tiles_html}</div>
</section>
<section class="section week-share">
  <div class="card week-card">
    <div><h3>This week in layoffs</h3><p class="cap">{fmt(wk_people)} people at {wk_cos} companies since {short_date((TODAY - timedelta(days=7)).isoformat())}. Ready to post.</p>
    {share_buttons(SITE_URL + "/stat/week/", f"This week in layoffs: {fmt(wk_people)} people at {wk_cos} companies.", "/og/stat-week.png")}
    <a class="btn ghost" href="/og/story-week.png" download style="margin-top:8px">Story (1080×1920)</a></div>
    <img src="/og/stat-week.png" alt="This week in layoffs share card" width="1200" height="630" loading="lazy">
  </div>
</section>
<section class="section">
  <div class="card"><h3>People laid off per week</h3><p class="cap">By announcement date, {y}. The last five weeks are highlighted.</p>
  {weekly_chart(s['weekly'], s['week_top'])}</div>
</section>
<section class="section">
  <div class="section-head"><h2>Biggest layoffs of {y}</h2><p><a href="/companies/">All companies →</a></p></div>
  <div class="card"><div class="bars">{bars_html(top, "company", link=lambda slug: f"/company/{slug}/")}</div></div>
</section>
<section class="section" id="explore">
  <div class="section-head"><h2>Explore</h2><p data-fsum></p></div>
  <div class="filters" role="group" aria-label="Filters">
    <div class="seg" data-range><button type="button" data-r="30" aria-pressed="false">30 days</button><button type="button" data-r="90" aria-pressed="false">90 days</button><button type="button" data-r="ytd" aria-pressed="true">{y}</button></div>
    <select class="select" id="f-industry" data-f="i" aria-label="Industry"><option value="">All industries</option>{opts_i}</select>
    <select class="select" id="f-country" data-f="k" aria-label="Country"><option value="">All countries</option>{opts_c}</select>
    <input class="search" id="f-search" type="search" placeholder="Search companies" data-f="q" aria-label="Search companies">
  </div>
  <div class="grid2">
    <div class="card"><h3>By industry</h3><p class="cap">People laid off. Tap a bar to filter.</p><div class="bars" data-bars="i">{bars_html(industries, "i")}</div></div>
    <div class="card"><h3>By country</h3><p class="cap">Company headquarters unless sources say otherwise.</p><div class="bars" data-bars="k">{bars_html(countries, "k")}</div></div>
  </div>
  <div class="section-head" style="margin-top:28px"><h2>Latest events</h2><p>Newest first</p></div>
  <div class="feed" data-feed>{feed}<button class="more" type="button" data-more>Show more</button></div>
</section>
</div>
<script type="application/json" id="events">{json.dumps(slim, separators=(",", ":")).replace("</", "<\\/")}</script>
<script type="application/json" id="warn">{json.dumps(early_warnings(evs), separators=(",", ":")).replace("</", "<\\/")}</script>
<div class="dive" data-dive hidden><div class="dive-in" role="dialog" aria-modal="true" aria-labelledby="dive-title" tabindex="-1"></div></div>"""
    title = f"{fmt(s['ytd'])} people laid off in {y}: {NAME}"
    desc = f"{fmt(s['ytd'])} people laid off in {y} so far, live. Every number links to its sources."
    return page("/", title, desc, body, "/og/home.png", "home", wrap=False)


def source_row(src):
    tier = "official" if src["tier"] == "official" else ""
    claim = fmt(src["headcount"]) if src["headcount"] else (f'{src["pct"]:g}%' if src["pct"] else "–")
    spec = " · speculative" if src["speculative"] else ""
    hn = f' · <a href="{e(src["hn"])}" target="_blank" rel="noopener">HN thread</a>' if src.get("hn") else ""
    return (f'<li><span><a class="t" href="{e(src["url"])}" target="_blank" rel="noopener nofollow">{e(src["title"])}</a>'
            f'<span class="p"><span class="tier {tier}">{e(TIER_LABEL.get(src["tier"], "Filing"))}</span>{e(src["publisher"])} · '
            f'{short_date(src["date"])}{spec}{hn}</span></span><span class="c">{claim}</span></li>')


def statement(cevs):
    """Deadpan, postable line for a company's latest event: (lead, big, tail)."""
    c, lev = cevs[0]["company"], cevs[0]
    if lev["kind"] == "plan" and len(cevs) > 1:
        lev = next((x for x in cevs if x["kind"] != "plan"), lev)
    if lev["kind"] == "plan":
        when = f"by {lev['horizon']}" if lev.get("horizon") and lev["horizon"] != "multi-year" else "over several years"
        big = fmt(lev["plan_n"]) if lev["plan_n"] else (f'{lev["plan_pct"]:g}%' if lev["plan_pct"] else "Undisclosed")
        return f"{c} plans to cut", big, f"jobs {when}. An announced plan, not yet counted."
    recent = (TODAY - date.fromisoformat(lev["start"])).days <= 14
    verb = "just cut" if recent else "cut"
    when = "" if recent else f" in {date.fromisoformat(lev['start']).strftime('%B')}"
    if lev["pct_show"] and lev["headcount"]:
        return f"{c} {verb}", lev["pct_show"], f"of its staff{when}. That is {fmt(lev['headcount'])} people."
    if lev["pct_show"]:
        return f"{c} {verb}", lev["pct_show"], f"of its staff{when}."
    if lev["headcount"]:
        return f"{c} {verb}", fmt(lev["headcount"]), f"job{'s' if lev['headcount'] != 1 else ''}{when}."
    return f"{c} is cutting jobs{when}.", "Undisclosed", "No number has been published yet."


def company_page(slug, cevs, s):
    c = cevs[0]
    total = sum(x["headcount"] or 0 for x in cevs if x["kind"] != "plan")
    url = f"{SITE_URL}/company/{slug}/"
    best = max(cevs, key=lambda x: LABEL_STEPS.get(x["label"], 0))
    number = fmt(total) if total else (f'{cevs[0]["pct"]:g}%' if cevs[0]["pct"] else "Undisclosed")
    lead, big, tail = statement(cevs)
    share_text = f"{lead} {big} {tail}".replace("Undisclosed No number has been published yet.", "").strip() + " Sources:"
    pct_block = (f'<div><div class="k">Share of staff (latest)</div><div class="v">{e(c["pct_show"])}</div>'
                 f'<div class="k" style="margin-top:2px">{e(c["pct_note"])}{wf_link(slug, c)}</div></div>') if c["pct_show"] else ""
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
    {pct_block}
    <div><div class="k">Latest</div><div class="v" style="font-size:clamp(24px,4vw,34px);padding-top:8px">{nice_date(cevs[0]['start'])}</div></div>
  </div>
  <div class="hero-actions">{share_buttons(url, share_text, f"/og/company/{slug}.png")}<a class="btn ghost" href="/og/story/{slug}.png" download>Story</a></div>
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


SOURCE_NAMES = {
    "gnews": "News: Google News, English (US edition, year-to-date)",
    "gnews_intl": "News: Google News, 55 country editions in 29 languages",
    "gdelt": "News: GDELT (machine-translated global news, last ~3 months)",
    "edgar": "SEC 8-K Item 2.05 filings", "warn_ca": "WARN: California", "warn_md": "WARN: Maryland",
    "warn_tx": "WARN: Texas", "warn_pa": "WARN: Pennsylvania", "warn_co": "WARN: Colorado", "warn_wa": "WARN: Washington",
    "tdnet": "Japan: TDnet timely disclosures", "nse": "India: NSE corporate announcements",
    "asx": "Australia: ASX announcements", "hn": "Hacker News", "reddit": "Reddit r/layoffs",
}


def methodology_page(s, counts):
    src_rows = "".join(f"<li><strong>{e(k)}</strong>: {fmt(v)} items</li>" for k, v in counts)
    body = f"""<div class="prose">
<h1>Methodology</h1>
<p>{NAME} counts layoffs from public records and reporting. It never estimates numbers that no source has stated.
Every figure on the site links to the sources it came from.</p>
<h2>Sources</h2><ul>{src_rows}</ul>
<p>Official sources are SEC 8-K filings under Item 2.05 (exit or disposal activities), state WARN notices
(California, Maryland, Texas, Pennsylvania, Colorado, Washington), Japan's TDnet disclosures and India's NSE announcements.
News comes from Google News in 55 country editions, searched with layoff wording in each local language
(Stellenabbau, licenciements, despidos, demissões, esuberi, ontslagen, 希望退職, 裁员, 구조조정, छंटनी, PHK and more), and from GDELT,
which indexes machine-translated news in about 65 languages. Hacker News and r/layoffs are weak signals.
X and LinkedIn are not used: their APIs are paid or prohibit this use.</p>
<h2>Languages</h2>
<p>Headlines in other languages are parsed with the same rules as English ones: a local layoff word, a company, and a number next to a
local job noun ("1.200 Stellen", "1 200 postes", "3 mil empleos", "2万人"). Rumour wording in each language marks a report as speculative.
Where an outlet is in one country and the headline names no country, the company is placed in the outlet's country.</p>
<p>In Japan, firms cut staff through voluntary-retirement programs (希望退職), because dismissals are tightly restricted. A program with a
stated target or a reported number of leavers counts as a layoff there. The size of the eligible pool ("open to 60,000 staff") never counts.</p>
<h2>Names and duplicates</h2>
<p>Products, studios, units and executives often appear in headlines instead of the employer ("Ghost of Yōtei developer Sucker Punch", "Microsoft's Xbox").
When most of a name's headlines also name a bigger, overlapping story right next to it, both are merged under the employer.</p>
<h2>From reports to events</h2>
<p>Each headline is parsed for a company, a headcount or percentage, and a date. Lists, opinion pieces, buyout offers and
denials are discarded. Reports about the same company within two weeks of each other form one event. Later coverage that repeats
an earlier figure, or revises it on the same scale, is folded into the original event instead of being counted twice.
Numbers that describe a past total ("over the past year") are not counted.</p>
<h2>Announced plans</h2>
<p>A multi-year target ("35,000 jobs by 2030", "over the next five years") is shown as an <strong>announced plan</strong> with its
deadline, but it is left out of the live counter and the yearly total ({fmt(s.get("plans", 0))} plans, {fmt(s.get("plan_people", 0))} jobs in {YEAR_START.year}).
We do not spread a plan over its years: companies rarely say how fast it will happen, and much of it is often done through attrition.
When a round of the plan happens and is reported (a WARN notice, a plant closure, "cuts 1,000 jobs this week"), that round is counted.</p>
<h2>Consensus number</h2>
<p>The event's number is the weighted median of the firm claims. Filings outrank news, and news outranks rumour. Figures far from the median
are ignored. When sources disagree, the page shows the range (for example, "sources say 4,000–15,000"). WARN notices are only a floor:
they cover one state, so they never lower a company-wide figure. Figures above 50,000 need at least three independent publishers, including a major outlet.
Rumoured or hypothetical figures never set the number; once a layoff is confirmed, earlier rumour coverage joins that event.</p>
<h2>Share of staff</h2>
<p>When sources state a percentage, we show it. Otherwise, for large companies, we divide the headcount by the employee total from the
company's latest annual report (10-K, 20-F or the company's own annual report, linked in the table source) and mark it with ≈.
Where the employee total is unknown, we show the count only.</p>
<h2>The live counter</h2>
<p>Between hourly data updates, the counter on the front page climbs at the average pace of the last 30 days. It is an estimate, labelled as one,
and resets to the verified total on every update.</p>
<h2>Confidence</h2>
<p>Each source has a weight: official record 1.0, major outlet 0.7, other news 0.45, Hacker News 0.25, Reddit 0.15. Speculative wording
("reportedly", "may", "could", "sources say") cuts a source's weight by 40%. Confidence = 1 − ∏(1 − weight) over independent publishers.</p>
<ul><li><strong>Official</strong>: a WARN notice or an SEC filing that mentions the workforce.</li>
<li><strong>Corroborated</strong>: three or more independent publishers, or two including a major outlet.</li>
<li><strong>Reported</strong>: two independent publishers.</li></ul>
<p>Anything weaker is not shown. Single-source stories and social posts on their own never appear, and 8-K restructuring filings that don't mention people are left out.
In {YEAR_START.year}, {fmt(s['undisclosed'])} shown events have no stated headcount. They count as events but add nothing to the totals.</p>
<h2>Known limits</h2>
<ul><li>Totals are a floor: many layoffs are never reported, and WARN coverage is limited to six US states for now.</li>
<li>Country is the company's headquarters unless a filing or the sources say where the cuts happen.</li>
<li>Headline parsing is rule-based. An optional LLM extractor can be plugged in (<code>LR_LLM_CMD</code>) but is off.</li></ul>
<p>Data: <a href="/data.json">data.json</a> holds every shown event with its sources. Map places: <a href="https://www.geonames.org/">GeoNames</a> (CC BY 4.0) and OpenStreetMap Nominatim; land outlines: Natural Earth via world-atlas.</p></div>"""
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
    (DIST / "og" / "story").mkdir(parents=True)
    og.card(DIST / "og/home.png", f"People laid off in {YEAR_START.year}, tracked", fmt(s["ytd"]),
            f"across {fmt(s['companies'])} companies · {fmt(s['events'])} events", stamp, spark=s["weekly"])
    og.statement(DIST / "og/story-home.png", f"People laid off in {YEAR_START.year}", fmt(s["ytd"]),
                 f"So far. {fmt(s['companies'])} companies.", f"Updated {stamp}", stamp, story=True, spark=s["weekly"])
    wk_people, wk_cos, wk_top = week_stats(evs)
    rows = [(n, fmt(v)) for n, v in wk_top]
    wk_range = f"{short_date((TODAY - timedelta(days=7)).isoformat())} – {nice_date(TODAY.isoformat())}"
    og.statement(DIST / "og/stat-week.png", "This week in layoffs", fmt(wk_people), f"people. {wk_cos} companies.",
                 wk_range, stamp, rows=rows)
    og.statement(DIST / "og/story-week.png", "This week in layoffs", fmt(wk_people), f"people. {wk_cos} companies.",
                 wk_range, stamp, story=True, rows=rows)

    by_slug = defaultdict(list)
    for x in evs:
        by_slug[x["slug"]].append(x)
    top_slugs = {c["slug"] for c in s["companies_list"][:60]}
    d30 = (TODAY - timedelta(days=30)).isoformat()
    for slug, cevs in by_slug.items():
        write(f"/company/{slug}/", company_page(slug, cevs, s))
        lead, big, tail = statement(cevs)
        meta = (f"{nice_date(cevs[0]['start'])} · {cevs[0]['label']} · {cevs[0]['n_publishers']} "
                f"source{'s' if cevs[0]['n_publishers'] != 1 else ''}")
        og.statement(DIST / f"og/company/{slug}.png", lead, big, tail, meta, stamp)
        if slug in top_slugs or cevs[0]["start"] >= d30:
            og.statement(DIST / f"og/story/{slug}.png", lead, big, tail, meta, stamp, story=True)
    write("/companies/", companies_page(s))

    stat_defs = [
        ("ytd", f"People laid off in {YEAR_START.year}", fmt(s["ytd"]), f"across {fmt(s['companies'])} companies, every number sourced",
         f"{fmt(s['ytd'])} people laid off in {YEAR_START.year} so far."),
        ("30d", "People laid off in the last 30 days", fmt(s["d30"]), f"in {s['events30']} layoff events since {short_date((TODAY - timedelta(days=30)).isoformat())}",
         f"{fmt(s['d30'])} people laid off in the last 30 days."),
        ("events", f"Layoff events in {YEAR_START.year}", fmt(s["events"]), f"at {fmt(s['companies'])} companies, each confirmed by a filing or several outlets",
         f"{fmt(s['events'])} layoff events in {YEAR_START.year} so far."),
    ]
    stat_defs.append(("week", "This week in layoffs", fmt(wk_people), f"people at {wk_cos} companies, {wk_range}",
                      f"This week in layoffs: {fmt(wk_people)} people at {wk_cos} companies."))
    for name, v, _ in industries[:6]:
        n_co = len({x["slug"] for x in evs if x["industry"] == name})
        stat_defs.append((f"industry-{slugify(name)}", f"{name} layoffs in {YEAR_START.year}", fmt(v),
                          f"across {n_co} companies", f"{fmt(v)} people laid off in {name.lower()} in {YEAR_START.year}."))
    for key, eyebrow, number, sub, text in stat_defs:
        write(f"/stat/{key}/", stat_page(key, eyebrow, number, sub, text + f" Sourced tracker by {NAME}:"))
        if key != "week":
            og.card(DIST / f"og/stat-{key}.png", eyebrow, number, sub, stamp, spark=s["weekly"])

    con = connect()
    counts = [(SOURCE_NAMES.get(k, k), v) for k, v in con.execute(
        "SELECT source, COUNT(*) FROM items GROUP BY source ORDER BY 2 DESC")]
    write("/methodology/", methodology_page(s, counts))
    write("/404.html", page("/404.html", f"Not found: {NAME}", "Page not found.",
                            '<div class="prose"><h1>Not found</h1><p>That page does not exist. <a href="/">Back to the tracker</a>.</p></div>'))
    data = {"updated": updated.isoformat(), "totals": {k: s[k] for k in ("ytd", "d30", "events", "companies")},
            "events": [{k: x[k] for k in ("slug", "company", "start", "end", "headcount", "low", "high", "pct", "confidence",
                                          "label", "industry", "country", "headline", "kind", "horizon", "plan_n")}
                       | {"sources": [{"publisher": r["publisher"], "tier": r["tier"], "url": r["url"], "title": r["title"],
                                       "date": r["date"], "headcount": r["headcount"], "pct": r["pct"]} for r in x["sources"]]}
                       for x in evs]}
    (DIST / "data.json").write_text(json.dumps(data, separators=(",", ":")))
    live = {"updated": updated.isoformat(), "ytd": s["ytd"], "d30": s["d30"], "pace_per_hour": round(s["d30"] / 720, 2),
            "week": wk_people, "latest": [{"s": x["slug"], "c": x["company"], "d": x["start"], "n": x["headcount"], "ps": x["pct_show"]}
                                          for x in evs if x["headcount"] or x["pct_show"]][:12]}
    (DIST / "live.json").write_text(json.dumps(live, separators=(",", ":")))
    print(f"built {len(by_slug)} company pages, {len(stat_defs)} stat pages; ytd={s['ytd']:,} d30={s['d30']:,} events={s['events']}")


# ------------------------------------------------------------------ local sign-up API (mirrors functions/api/*.js)
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")
COUNTABLE = {"panel", "gate_view", "signup_open"}
_hits = defaultdict(list)


def _rate_ok(ip, limit, window=600):
    now = datetime.now().timestamp()
    _hits[ip] = [t for t in _hits[ip] if now - t < window]
    if len(_hits[ip]) >= limit:
        return False
    _hits[ip].append(now)
    return True


def _bump(name):
    p = DATA / "counts.json"
    counts = json.loads(p.read_text()) if p.exists() else {}
    day = date.today().isoformat()
    counts.setdefault(name, {})
    counts[name][day] = counts[name].get(day, 0) + 1
    p.write_text(json.dumps(counts, indent=1))
    return counts


class Handler(http.server.SimpleHTTPRequestHandler):
    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        ip = self.client_address[0]
        try:
            n = int(self.headers.get("Content-Length") or 0)
            d = json.loads(self.rfile.read(min(n, 4096)) or b"{}") if n else {}
        except (ValueError, json.JSONDecodeError):
            return self._json(400, {"ok": False, "error": "bad json"})
        if self.path == "/api/event":
            if d.get("t") not in COUNTABLE or not _rate_ok("ev:" + ip, 120):
                return self._json(204 if d.get("t") in COUNTABLE else 400, {"ok": False})
            _bump(d["t"])
            return self._json(200, {"ok": True})
        if self.path != "/api/signup":
            return self._json(404, {"ok": False})
        if d.get("website"):  # honeypot: pretend success, store nothing
            return self._json(200, {"ok": True})
        email = str(d.get("email") or "").strip().lower()
        if not EMAIL_RE.match(email) or len(email) > 254:
            return self._json(400, {"ok": False, "error": "Enter a valid email."})
        if not _rate_ok("su:" + ip, 5):
            return self._json(429, {"ok": False, "error": "Too many tries. Wait a few minutes."})
        p = DATA / "signups.jsonl"
        known = p.exists() and any(json.loads(l).get("email") == email for l in p.read_text().splitlines() if l.strip())
        if not known:
            with p.open("a") as f:
                f.write(json.dumps({"email": email, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                    "src": str(d.get("src") or "")[:80], "ua": (self.headers.get("User-Agent") or "")[:160]}) + "\n")
            _bump("signup")
        return self._json(200, {"ok": True, "known": bool(known)})

    def do_GET(self):
        if self.path.split("?")[0] == "/api/stats":
            p, sp = DATA / "counts.json", DATA / "signups.jsonl"
            counts = json.loads(p.read_text()) if p.exists() else {}
            n = sum(1 for l in sp.read_text().splitlines() if l.strip()) if sp.exists() else 0
            return self._json(200, {"signups": n, "totals": {k: sum(v.values()) for k, v in counts.items()}, "by_day": counts})
        return super().do_GET()

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
