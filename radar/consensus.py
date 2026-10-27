"""Claims -> events. Clustering, robust headcount and confidence scoring."""
import json
import re
from collections import Counter, defaultdict
from datetime import date

from .extract import canonical_slug, claims_from_item, extract_headline, is_title_case
from .llm import get_llm
from .ref import KNOWN

JOIN_GAP = 14      # days between consecutive claims of one event
MAX_SPAN = 60      # max days an event can span
ECHO_GAP = 45      # number-less follow-up coverage within this many days folds into the previous event
VISIBLE_MIN = 0.5
WORKFORCE = re.compile(r"(?i)\b(workforce|reduction in force|employees|positions|headcount|jobs|staff|personnel|team members|severance)\b")


def d(s):
    return date.fromisoformat(s)


def publisher_key(name):
    return re.sub(r"[^a-z0-9]", "", (name or "").lower().replace("the ", ""))


def weighted_median(pairs):
    pairs = sorted(pairs)
    total = sum(w for _, w in pairs)
    acc = 0
    for v, w in pairs:
        acc += w
        if acc >= total / 2:
            return v
    return pairs[-1][0]


def build_claims(con):
    rows = [dict(r) for r in con.execute("SELECT * FROM items WHERE published IS NOT NULL")]
    for r in rows:
        r["meta"] = json.loads(r["meta"] or "{}")
    # Gazetteer: known companies, official filers, and names from sentence-case headlines (reliable boundaries).
    gaz = set(KNOWN)
    for r in rows:
        if r["tier"] == "official" and r["meta"].get("company"):
            gaz.add(canonical_slug(r["meta"]["company"]))
    for r in rows:
        if r["tier"] != "official" and not is_title_case(r["title"]):
            ex = extract_headline(r["title"])
            if ex:
                gaz.add(canonical_slug(ex["company"]))
    llm = get_llm()
    con.execute("DELETE FROM claims")
    seen = set()
    n = 0
    for r in rows:
        key = (publisher_key(r["publisher"]), re.sub(r"\W+", "", r["title"].lower())[:80])
        if r["tier"] != "official":
            if key in seen:
                continue  # same headline syndicated through several queries/editions
            seen.add(key)
        c = claims_from_item(r, gaz, llm)
        if not c:
            continue
        con.execute("""INSERT INTO claims(item_id, company, slug, headcount, pct, kind, date, country, location, industry,
                       weight, speculative, method) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (r["id"], c["company"], canonical_slug(c["company"]), c["headcount"], c["pct"], c["kind"], c["date"],
                     c["country"], c["location"], c["industry"], c["weight"], c["speculative"], c["method"]))
        n += 1
    con.commit()
    return n


def _cluster(claims):
    claims.sort(key=lambda c: c["date"])
    clusters = []
    for c in claims:
        cur = clusters[-1] if clusters else None
        if cur and (d(c["date"]) - d(cur[-1]["date"])).days <= JOIN_GAP and (d(c["date"]) - d(cur[0]["date"])).days <= MAX_SPAN:
            cur.append(c)
        else:
            clusters.append([c])
    merged = []
    for cl in clusters:
        weak = not any(c["headcount"] or c["pct"] or c["tier"] == "official" for c in cl)
        if merged and weak and (d(cl[0]["date"]) - d(merged[-1][-1]["date"])).days <= ECHO_GAP:
            merged[-1].extend(cl)
        else:
            merged.append(cl)
    return merged


def _score(cl):
    by_pub = {}
    for c in cl:
        k = publisher_key(c["publisher"]) if c["tier"] != "official" else c["source"] + str(c["item_id"])
        by_pub[k] = max(by_pub.get(k, 0), c["weight"])
    miss = 1.0
    for w in by_pub.values():
        miss *= (1 - w)
    return 1 - miss, len({publisher_key(c["publisher"]) for c in cl if c["weight"] > 0})


def _headcount(cl):
    edgar = [c["headcount"] for c in cl if c["source"] == "edgar" and c["headcount"]]
    warn_rows = {(c["company"], c["date"], c["location"], c["headcount"]) for c in cl if c["source"].startswith("warn")}
    warn = sum(r[3] for r in warn_rows)
    buyouts = [c["headcount"] for c in cl if c["kind"] == "buyout" and c["headcount"]]
    news = [(c["headcount"], c["weight"], c["speculative"]) for c in cl
            if c["tier"] != "official" and c["headcount"] and c["kind"] != "buyout"
            and not any(abs(c["headcount"] - b) <= 0.05 * b for b in buyouts)]
    if any(not s for _, _, s in news):
        news = [x for x in news if not x[2]]  # firm reports beat speculation
    news = [(v, w) for v, w, _ in news]
    if len(news) >= 3:
        med = weighted_median(news)
        shown = [v for v, _ in news if med / 4 <= v <= med * 4]
    else:
        shown = [v for v, _ in news]
    all_vals = edgar + shown
    if len(news) >= 3:
        med = weighted_median(news)
        news = [(v, w) for v, w in news if med / 2.5 <= v <= med * 2.5]
    vals = edgar + [v for v, _ in news]
    if edgar:
        est = max(edgar)
    elif news:
        est = weighted_median(news)
    else:
        est = None
    if warn and (est is None or warn > est):
        est = warn
        vals.append(warn)
    pcts = sorted(c["pct"] for c in cl if c["pct"] and not c["speculative"]) or sorted(c["pct"] for c in cl if c["pct"])
    pct = pcts[len(pcts) // 2] if pcts else None
    if est is None:
        return None, None, None, pct, warn
    if not all_vals or est == warn:
        all_vals = all_vals + [est]
    return est, min(all_vals), max(all_vals), pct, warn


ADDITIVE = re.compile(r"(?i)\b(more (?:jobs|workers|employees|staff\w*|roles|positions|layoffs|cuts)|another|additional|new round|second round|third round|fresh round|again|further (?:job )?cuts)\b")


def _additive(cl):
    """A cluster is a new round only if a solid share of its coverage says so."""
    news = [c for c in cl if c["tier"] != "official"]
    hits = sum(1 for c in news if ADDITIVE.search(c["title"] or ""))
    return bool(news) and hits >= max(1, 0.3 * len(news))


def _dedupe_company(clusters):
    """Collapse re-reporting of one announcement across a company's timeline.

    A later news-only cluster (within 365 days, without "another round" wording) folds into the
    previous event when it has no number of its own, or when its number is on the same scale
    (0.5x-2.5x: a re-report or an upward revision of the same program). Clusters that stay
    separate drop news numbers that merely repeat an earlier figure for this company.
    """
    out, seen = [], []

    def nums(cl):
        return [(c["headcount"], d(c["date"])) for c in cl if c["headcount"] and c["tier"] != "official"]

    for cl in clusters:
        has_off = any(c["tier"] == "official" for c in cl)
        if out and not has_off and not _additive(cl):
            est = _headcount(cl)[0]
            has_num = any(c["headcount"] or c["pct"] for c in cl)
            target = None
            for prev in reversed(out):
                if (d(cl[0]["date"]) - d(prev[-1]["date"])).days > 365:
                    break
                if not has_num:
                    target = prev
                    break
                pest = _headcount(prev)[0]
                if est and pest and 0.5 * pest <= est <= 2.5 * pest:
                    target = prev
                    break
            if target is not None:
                target.extend(cl)
                target.sort(key=lambda c: c["date"])
                seen += nums(cl)
                continue
        # An identical figure is a repeat, even under "more layoffs" wording.
        for c in cl:
            if c["tier"] != "official" and c["headcount"] and any(
                    abs(c["headcount"] - v) <= 0.1 * v and 0 < (d(c["date"]) - dt).days <= 365 for v, dt in seen):
                c["headcount"], c["repeat"] = None, 1
        out.append(cl)
        seen += nums(cl)
    return out


def build_events(con):
    rows = [dict(r) for r in con.execute(
        "SELECT c.*, i.tier, i.source, i.publisher, i.title, i.url, i.text FROM claims c JOIN items i ON i.id = c.item_id")]
    for r in rows:
        # An 8-K Item 2.05 is an exit/disposal filing; it only counts as a layoff record when it mentions people.
        if r["source"] == "edgar" and not (r["headcount"] or r["pct"] or WORKFORCE.search(r["text"] or "")):
            r["tier"], r["weight"] = "filing-nonworkforce", 0.0
    by_slug = defaultdict(list)
    for r in rows:
        by_slug[r["slug"]].append(r)
    con.execute("DELETE FROM events")
    con.execute("DELETE FROM event_claims")
    rank = {"major": 0, "news": 1, "official": 2, "aggregator": 3, "social": 4, "filing-nonworkforce": 5}
    n_vis = 0
    for slug, claims in by_slug.items():
        known = KNOWN.get(slug)
        names = Counter(c["company"] for c in claims if c["tier"] != "official") or Counter(c["company"] for c in claims)
        display = known[0] if known else names.most_common(1)[0][0]
        if re.match(r"^E[A-Z][a-z]", display):
            display = "e" + display[1:]  # "EBay" -> "eBay"
        ind_votes = Counter(c["industry"] for c in claims if c["industry"] and c["tier"] == "official") or \
            Counter(c["industry"] for c in claims if c["industry"])
        co_industry = known[1] if known else (ind_votes.most_common(1)[0][0] if ind_votes else "Other")
        cty_votes = Counter(c["country"] for c in claims if c["country"] and c["tier"] == "official") or \
            Counter(c["country"] for c in claims if c["country"] and "multi" not in c["country"])
        co_country = known[2] if known else (cty_votes.most_common(1)[0][0] if cty_votes else "Unknown")
        for cl in _dedupe_company(_cluster(claims)):
            conf, n_pub = _score(cl)
            has_off = any(c["tier"] == "official" for c in cl)
            est, low, high, pct, warn = _headcount(cl)
            if low and high and high / max(low, 1) > 2.5:
                conf *= 0.9  # sources disagree
            ev_cty = Counter(c["country"] for c in cl if c["country"] and "multi" not in c["country"]).most_common(1)
            country = co_country
            kinds = {c["kind"] for c in cl}
            kind = "buyout" if kinds == {"buyout"} else ("closure" if kinds == {"closure"} else "layoff")
            n_major = len({publisher_key(c["publisher"]) for c in cl if c["tier"] == "major"})
            if has_off:
                label, score = "Official", max(95, round(conf * 100))
            else:
                score = min(94, round(conf * 100))
                if n_pub >= 3 or (n_pub >= 2 and n_major >= 1):
                    label = "Corroborated"
                elif conf >= 0.4:
                    label = "Reported"
                else:
                    label = "Unverified"
            best = sorted(cl, key=lambda c: (0 if est and c["headcount"] == est else 1, rank[c["tier"]],
                                             0 if c["headcount"] else 1, c["speculative"]))[0]
            headline = best["title"]
            if all(c["source"].startswith("warn") for c in cl):
                sites = len({c["location"] for c in cl})
                headline = (f"WARN notice{'s' if len(cl) > 1 else ''}: {warn:,} employees"
                            + (f" across {sites} sites" if sites > 1 else f" in {cl[0]['location']}"))
            if est and est > 50000 and not has_off and not (n_major >= 1 and n_pub >= 3):
                est = low = high = None  # extraordinary numbers need extraordinary corroboration
            # Accuracy over coverage: official records, or at least two independent publishers.
            visible = int(kind != "buyout" and (has_off or (n_pub >= 2 and conf >= VISIBLE_MIN)))
            n_vis += visible
            cur = con.execute("""INSERT INTO events(slug, company, start, end, headcount, low, high, pct, confidence, label,
                industry, country, n_sources, n_publishers, has_official, kind, headline, visible)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (slug, display, cl[0]["date"], cl[-1]["date"], est, low, high, pct, score, label, co_industry, country,
                 len(cl), n_pub, int(has_off), kind, headline, visible))
            con.executemany("INSERT INTO event_claims VALUES(?,?)", [(cur.lastrowid, c["id"]) for c in cl])
    con.commit()
    return n_vis
