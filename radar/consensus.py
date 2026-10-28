"""Claims -> events. Clustering, robust headcount and confidence scoring."""
import json
import re
from collections import Counter, defaultdict
from datetime import date

from .extract import canonical_slug, claims_from_item, extract_headline, is_title_case
from .llm import get_llm
from .ref import KNOWN, PRIOR_FIGURES

JOIN_GAP = 14      # days between consecutive claims of one event
MAX_SPAN = 60      # max days an event can span
ECHO_GAP = 45      # number-less follow-up coverage within this many days folds into the previous event
VISIBLE_MIN = 0.5
STALE_DAYS = 60    # a company+number first reported more than this many days earlier is a re-citation, not a new event
WORKFORCE = re.compile(r"(?i)\b(workforce|reduction in force|employees|positions|headcount|jobs|staff|personnel|team members|severance)\b")


def d(s):
    return date.fromisoformat(s)


def publisher_key(name):
    return re.sub(r"[^a-z0-9]", "", (name or "").lower().replace("the ", ""))


SECOND_LEVEL = {"co", "com", "org", "net", "gov", "ac", "ne", "or", "go", "edu", "gob", "nic", "info", "biz", "news", "gv", "web"}


def domain_key(host):
    """'www.sueddeutsche.de' -> 'sueddeutsche', 'bbc.co.uk' -> 'bbc', 'finance.yahoo.com' -> 'yahoo'."""
    host = re.sub(r"^https?://", "", (host or "").lower()).split("/")[0].split(":")[0]
    labels = [x for x in host.split(".") if x and x not in ("www", "m", "amp", "mobile")]
    if not labels:
        return ""
    if len(labels) >= 3 and labels[-2] in SECOND_LEVEL:
        return labels[-3]
    return labels[-2] if len(labels) >= 2 else labels[0]


def item_pubkey(r):
    """One key per outlet across sources: Google News names it, GDELT gives its domain; both map to the domain."""
    if r["tier"] == "official":
        return r["source"]
    meta = r["meta"]
    host = meta.get("publisher_url") or meta.get("domain")
    if not host and r["source"] in ("hn", "gdelt"):
        host = r["url"]
    k = domain_key(host) if host else ""
    return k or publisher_key(r["publisher"])


def weighted_median(pairs):
    pairs = sorted(pairs)
    total = sum(w for _, w in pairs)
    acc = 0
    for v, w in pairs:
        acc += w
        if acc >= total / 2:
            return v
    return pairs[-1][0]


CHUNK = 2000
from .config import SOURCES as _SOURCES  # noqa: E402
from .util import SINCE  # noqa: E402
_SRC_IN = ",".join("'%s'" % k for k in _SOURCES)


def iter_items(con):
    """Stream items in id order, a chunk at a time (the corpus never sits in memory as a whole)."""
    last = 0
    while True:
        # Only the data window (util.SINCE) and enabled sources (config.SOURCES); older rows stay in the DB as cache.
        rows = con.execute("SELECT id, source, tier, publisher, url, title, text, published, meta FROM items "
                           f"WHERE published IS NOT NULL AND published >= ? AND source IN ({_SRC_IN}) AND id > ? "
                           "ORDER BY id LIMIT ?", (SINCE.isoformat(), last, CHUNK)).fetchall()
        if not rows:
            return
        for r in rows:
            r = dict(r)
            r["meta"] = json.loads(r["meta"] or "{}")
            yield r
        last = rows[-1]["id"]


def build_claims(con):
    from .extract import item_lang
    from .intl import VOCAB, Gazetteer, learn_vocab
    VOCAB.clear()
    from .ref import ALIASES
    from .util import mem_guard
    # Gazetteer: known companies, official filers, and names from sentence-case English headlines (reliable boundaries).
    gaz = set(KNOWN)
    names = {v[0]: k for k, v in KNOWN.items()}
    names.update({a.replace("-", " "): b for a, b in ALIASES.items() if len(a) > 3})
    seen_en = Counter()
    for r in iter_items(con):
        if r["tier"] == "official" and r["meta"].get("company"):
            gaz.add(canonical_slug(r["meta"]["company"]))
            if r["source"] != "tdnet":
                from .extract import clean_company
                co = clean_company(r["meta"]["company"])
                if co:
                    names.setdefault(co, canonical_slug(co))
        elif r["tier"] != "official" and item_lang(r) != "en":
            learn_vocab(r["title"], item_lang(r))
        elif r["tier"] != "official" and item_lang(r) == "en" and not is_title_case(r["title"]):
            ex = extract_headline(r["title"])
            if ex:
                gaz.add(canonical_slug(ex["company"]))
                seen_en[ex["company"]] += 1
    for n, k in seen_en.items():
        if k >= 2:  # a name seen in two or more English headlines is a fair bet for matching other languages
            names.setdefault(n, canonical_slug(n))
    intl_gaz = Gazetteer(names)
    del seen_en
    mem_guard()
    llm = get_llm()
    con.execute("DELETE FROM claims")
    seen = set()
    n = 0
    batch = []
    for r in iter_items(con):
        pk = item_pubkey(r)
        key = (pk, re.sub(r"\W+", "", r["title"].lower())[:80])
        if r["tier"] != "official":
            if key in seen:
                continue  # same headline syndicated through several queries/editions/sources
            seen.add(key)
        c = claims_from_item(r, gaz, llm, intl_gaz)
        if not c:
            continue
        batch.append((r["id"], c["company"], canonical_slug(c["company"]), c["headcount"], c["pct"], c["kind"], c["date"],
                      c["country"], c["location"], c["industry"], c["weight"], c["speculative"], c["method"],
                      c.get("horizon"), c.get("lang"), c.get("src_country"), pk))
        n += 1
        if len(batch) >= 1000:
            _insert_claims(con, batch)
            batch = []
    _insert_claims(con, batch)
    con.commit()
    return n


def _insert_claims(con, batch):
    con.executemany("""INSERT INTO claims(item_id, company, slug, headcount, pct, kind, date, country, location, industry,
                       weight, speculative, method, horizon, lang, src_country, pubkey) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    batch)


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
        k = c["pubkey"] if c["tier"] != "official" else c["source"] + str(c["item_id"])
        by_pub[k] = max(by_pub.get(k, 0), c["weight"])
    miss = 1.0
    for w in by_pub.values():
        miss *= (1 - w)
    return 1 - miss, len({c["pubkey"] for c in cl if c["weight"] > 0})


def _headcount(cl):
    edgar = [c["headcount"] for c in cl if c["source"] in ("edgar", "tdnet", "nse") and c["tier"] == "official" and c["headcount"]]
    warn_rows = {(c["company"], c["date"], c["location"], c["headcount"]) for c in cl if c["source"].startswith("warn")}
    warn = sum(r[3] for r in warn_rows)
    buyouts = [c["headcount"] for c in cl if c["kind"] == "buyout" and c["headcount"]]
    news = [(c["headcount"], c["weight"], c["speculative"]) for c in cl
            if c["tier"] != "official" and c["headcount"] and c["kind"] != "buyout"
            and not any(abs(c["headcount"] - b) <= 0.05 * b for b in buyouts)]
    # A figure most outlets frame as a rumour ("could", "report says", "传", "pertimbangkan") stays a rumour even where
    # one outlet drops the hedge.
    def _near(a, b):
        return abs(a - b) <= 0.05 * b
    news = [x for x in news if not x[2] and sum(1 for y in news if y[2] and _near(y[0], x[0]))
            <= sum(1 for y in news if not y[2] and _near(y[0], x[0]))]
    news = [x for x in news if not x[2]]  # rumours and hypotheticals never set the number
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


def _drop_stale_numbers(claims, slug):
    """Past or cumulative totals are not new events: a news number equal to a figure announced before the window
    (ref.PRIOR_FIGURES), or to one this company already had reported more than STALE_DAYS earlier, is dropped."""
    prior = PRIOR_FIGURES.get(slug, ())
    first = []
    for c in sorted(claims, key=lambda c: c["date"]):
        v = c["headcount"]
        if not v or c["tier"] == "official":
            continue
        if any(abs(v - p) <= 0.02 * p for p in prior):
            c["headcount"], c["repeat"] = None, 1
            continue
        seen = next((dt for pv, dt in first if abs(v - pv) <= 0.05 * pv), None)
        if seen is None:
            first.append((v, d(c["date"])))
        elif (d(c["date"]) - seen).days > STALE_DAYS:
            c["headcount"], c["repeat"] = None, 1


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
        # Earlier number-less news coverage (rumours, "plans cuts") becomes part of the confirmed event.
        while out and not any(c["headcount"] or c["pct"] or c["tier"] == "official" for c in out[-1]) \
                and any(c["headcount"] for c in cl) and (d(cl[0]["date"]) - d(out[-1][-1]["date"])).days <= 90:
            cl = out.pop() + cl
        out.append(cl)
        seen += nums(cl)
    return out


def _norm(t):
    return " " + re.sub(r"[^a-z0-9&]+", " ", (t or "").lower().replace("’", "'").replace("'s ", " ")) + " "


def resolve_entities(rows):
    """Merge entity A into B when most of A's headlines also name B, B is the bigger story, and the
    dates overlap. Catches products, units and people extracted as companies
    ("Ghost of Yotei" -> Sucker Punch, "Xbox" -> Microsoft, "Jack Dorsey" -> Block)."""
    from .extract import STOP_SINGLE
    by = defaultdict(list)
    for r in rows:
        by[r["slug"]].append(r)
    size = {k: len(v) for k, v in by.items()}
    names = {}
    for k, v in by.items():
        n = Counter(c["company"] for c in v).most_common(1)[0][0]
        if len(n) >= 3 and n.lower() not in STOP_SINGLE:
            names[k] = _norm(n)
    dates = {k: sorted(d(c["date"]) for c in v) for k, v in by.items()}
    remap = {}
    name_index = defaultdict(list)  # normalised name -> slugs (only big enough stories can absorb others)
    for b, nb in names.items():
        if size[b] >= 3:
            name_index[nb.strip()].append(b)
    for a, claims in by.items():
        titles = [_norm(c["title"]) for c in claims if c["tier"] != "official"]
        na = names.get(a)
        if not titles or not na or a in KNOWN or any(c["tier"] == "official" for c in claims):
            continue
        cands = set()
        for t in titles:
            w = t.split()
            for i in range(len(w)):
                for n in (1, 2, 3, 4):
                    for b in name_index.get(" ".join(w[i:i + n]), ()):
                        cands.add(b)
        best, best_share = None, 0.0
        for b in cands:
            nb = names[b]
            if b == a or size[b] < max(3, size[a]) or nb == na:
                continue

            def near(t):  # B named right next to A ("Ghost of Yotei developer Sucker Punch", "Microsoft Xbox")
                i, j = t.find(na), t.find(nb)
                if i < 0 or j < 0:
                    return False
                gap = t[min(i + len(na), j + len(nb)):max(i, j)] if i != j else ""
                return (j >= i and j < i + len(na)) or (i >= j and i < j + len(nb)) or len(gap.split()) <= 2
            share = sum(1 for t in titles if near(t)) / len(titles)
            if share > best_share:
                best, best_share = b, share
        if best and best_share >= 0.5:
            near = any(abs((x - y).days) <= 14 for x in dates[a] for y in dates[best][:400])
            if near:
                remap[a] = best
    for a in list(remap):  # follow chains a -> b -> c
        seen = {a}
        while remap[a] in remap and remap[a] not in seen:
            seen.add(remap[a])
            remap[a] = remap[remap[a]]
    return remap


EXCHANGE = {"edgar", "nse", "tdnet", "asx"}
WORKFORCE_JA = re.compile(r"人員|退職|従業員|雇用|解雇")


def build_events(con):
    rows = [dict(r) for r in con.execute(
        "SELECT c.*, i.tier, i.source, i.publisher, i.title, i.url, "
        "CASE WHEN i.source IN ('edgar','nse','tdnet','asx') THEN i.text ELSE '' END AS text "
        "FROM claims c JOIN items i ON i.id = c.item_id")]
    for r in rows:
        # An exchange filing (8-K Item 2.05, NSE closure, TDnet restructuring) only counts as a layoff record when it
        # mentions people; a plant or subsidiary closure on its own says nothing about jobs.
        if r["source"] in EXCHANGE and not (r["headcount"] or r["pct"] or WORKFORCE.search(r["text"] or "")
                                            or WORKFORCE_JA.search(r["title"] or "")):
            r["tier"], r["weight"] = "filing-nonworkforce", 0.0
    remap = resolve_entities(rows)
    by_slug = defaultdict(list)
    for r in rows:
        r["slug"] = remap.get(r["slug"], r["slug"])
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
            Counter(c["country"] for c in claims if c["country"] and "multi" not in c["country"]) or \
            Counter(c["src_country"] for c in claims if c["src_country"])  # last resort: where the outlets are
        co_country = known[2] if known else (cty_votes.most_common(1)[0][0] if cty_votes else "Unknown")
        _drop_stale_numbers(claims, slug)
        for cl in _dedupe_company(_cluster(claims)):
            conf, n_pub = _score(cl)
            has_off = any(c["tier"] == "official" for c in cl)
            est, low, high, pct, warn = _headcount(cl)
            if low and high and high / max(low, 1) > 2.5:
                conf *= 0.9  # sources disagree
            ev_cty = Counter(c["country"] for c in cl if c["country"] and "multi" not in c["country"]).most_common(1)
            country = co_country
            kinds = {c["kind"] for c in cl if c["kind"] != "plan"} or {"layoff"}
            kind = "buyout" if kinds == {"buyout"} else ("closure" if kinds == {"closure"} else "layoff")
            # An announced multi-year plan: enough of the coverage gives the deadline ("by 2030"); the rest just omits it.
            plan_pubs = {c["pubkey"] for c in cl if c["kind"] == "plan" and not c["speculative"]}
            num_pubs = {c["pubkey"] for c in cl if (c["headcount"] or c["pct"]) and c["tier"] != "official"}
            horizon = None
            if plan_pubs and not has_off and (len(plan_pubs) >= 2 or len(plan_pubs) >= 0.3 * max(1, len(num_pubs))):
                kind = "plan"
                hz = [c["horizon"] for c in cl if c.get("horizon")]
                years = sorted(h for h in hz if h != "multi-year")
                horizon = years[-1] if years else "multi-year"
            n_major = len({c["pubkey"] for c in cl if c["tier"] == "major"})
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
                industry, country, n_sources, n_publishers, has_official, kind, headline, visible, horizon)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (slug, display, cl[0]["date"], cl[-1]["date"], est, low, high, pct, score, label, co_industry, country,
                 len(cl), n_pub, int(has_off), kind, headline, visible, horizon))
            con.executemany("INSERT INTO event_claims VALUES(?,?)", [(cur.lastrowid, c["id"]) for c in cl])
    con.commit()
    return n_vis
