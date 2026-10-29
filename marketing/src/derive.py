"""Derive every marketing number from a data.json snapshot.

python3 marketing/src/derive.py [snapshot.json]  ->  marketing/data/numbers.json
Rule: label Official/Corroborated, kind != plan, minus EXCLUDE (with reasons).
"""
import json, os, sys, re
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
SNAP = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "data/data-2026-10-29.json"
TODAY = date.fromisoformat(os.environ.get("LR_TODAY", "2026-10-29")) if len(sys.argv) < 2 else date.today()

# (slug, headcount or None=any, reason). User-specified first, then audit finds.
EXCLUDE = [
    ("ups", 48000, "user: 48,000 is a multi-year total, not a new layoff"),
    ("rockstar", None, "user: GTA (the '6' is 'GTA 6')"),
    ("reino-unido", None, "user: GTA story (Rockstar ex-staff), junk company name"),
    ("soriana", None, "user: denied by the company"),
    ("astrazeneca", 2000, "user: 2,000 is the Spain staff count, not the cut"),
    ("meta", 60000, "audit: the 60,000 is Microsoft's voluntary-retirement offer (Korean headline), misattributed to Meta"),
    ("microsoft", 60, "audit: same Microsoft voluntary-retirement story, '60 thousand' parsed as 60"),
    ("porsche", 50000, "audit: 50,000 is the Volkswagen group plan, not Porsche"),
    ("porsche", 9000, "audit: headline says Porsche denies more cuts; 9,000 is a past cumulative figure"),
    ("blizzard", 1900, "audit: 1,900 workers won job protections; not a layoff"),
    ("ingiliz", None, "audit: duplicate of GSK Belgium ('Ingiliz' = 'British' in Turkish)"),
    ("meta", 2000, "audit: the 2,000 were laid off by a moderation contractor, not by Meta"),
]
JLR_RE = re.compile(r"jaguar|land.?rover|jlr|ジャガー|捷豹|ягуар|재규어", re.I)


def excluded(x):
    for slug, n, why in EXCLUDE:
        if x["slug"] == slug and (n is None or x["headcount"] == n):
            return why
    if JLR_RE.search(x["company"]) and x["slug"] != "jaguar-land-rover":
        return "user: Jaguar Land Rover non-English duplicate"
    return None


def main():
    d = json.loads(SNAP.read_text())
    d30 = (TODAY - timedelta(days=30)).isoformat()
    keep, dropped = [], []
    for x in d["events"]:
        if x["label"] not in ("Official", "Corroborated") or x["kind"] == "plan":
            continue
        why = excluded(x)
        if why:
            dropped.append({"company": x["company"], "slug": x["slug"], "headcount": x["headcount"], "start": x["start"], "why": why})
        else:
            keep.append(x)
    counted = [x for x in keep if x["headcount"]]
    last30 = [x for x in counted if x["start"] >= d30]

    def top(rows, key, n):
        agg = defaultdict(lambda: {"people": 0, "events": 0})
        for x in rows:
            a = agg[key(x)]
            a["people"] += x["headcount"]
            a["events"] += 1
        return [{"name": k, **v} for k, v in sorted(agg.items(), key=lambda kv: -kv[1]["people"])][:n]

    names = {}
    for x in counted:
        names.setdefault(x["slug"], x["company"])
    comps = top(counted, lambda x: x["slug"], 10)
    for c in comps:
        c["slug"] = c["name"]
        c["name"] = names[c["slug"]]
        c["country"] = next(x["country"] for x in counted if x["slug"] == c["slug"])
    total = sum(x["headcount"] for x in counted)
    ind = top(counted, lambda x: x["industry"], 20)
    for r in ind:
        r["share"] = round(100 * r["people"] / total, 1)
    named_ind = [r for r in ind if r["name"] != "Other"]
    tech = next((r for r in ind if r["name"] == "Technology"), {"people": 0, "share": 0})
    countries = top([x for x in counted if x["country"] not in ("Unknown",)], lambda x: x["country"], 10)
    n_countries = len({x["country"] for x in keep if x["country"] != "Unknown"})

    # "massive" headlines vs the consensus number
    word = re.compile(r"\b(massive|massiv\w*|masiv\w*|massif|massifs|sweeping|huge|drastic\w*|mass layoffs?)\b", re.I)
    massive = []
    for x in counted:
        for s in x["sources"]:
            m = word.search(s["title"])
            if m:
                massive.append({"company": x["company"], "word": m.group(0), "publisher": s["publisher"], "title": s["title"],
                                "headcount": x["headcount"], "pct": x["pct"], "start": x["start"], "label": x["label"]})
                break
    massive.sort(key=lambda r: r["headcount"])
    sizes = sorted(x["headcount"] for x in counted)
    median = sizes[len(sizes) // 2] if len(sizes) % 2 else (sizes[len(sizes) // 2 - 1] + sizes[len(sizes) // 2]) // 2

    out = {
        "snapshot": SNAP.name, "updated": d["updated"], "today": TODAY.isoformat(), "d30_from": d30,
        "window_from": min(x["start"] for x in keep), "window_to": max(x["start"] for x in keep),
        "site_totals_unfiltered": d["totals"],
        "totals": {
            "people": total, "people_30d": sum(x["headcount"] for x in last30),
            "events": len(keep), "events_with_headcount": len(counted), "events_30d": len([x for x in keep if x["start"] >= d30]),
            "companies": len({x["slug"] for x in keep}), "countries": n_countries,
            "official_events": sum(1 for x in keep if x["label"] == "Official"),
            "median_layoff": median, "per_hour_30d": round(sum(x["headcount"] for x in last30) / 720),
            "us_people": sum(x["headcount"] for x in counted if x["country"] == "United States"),
            "non_us_share": round(100 * sum(x["headcount"] for x in counted if x["country"] not in ("United States", "Unknown")) / total, 1),
            "finance_people": sum(x["headcount"] for x in counted if x["industry"] == "Finance"), "undisclosed_events": len(keep) - len(counted),
        },
        "industries": ind, "industries_named": named_ind[:6], "tech": tech,
        "companies_top10": comps,
        "companies_top10_30d": top(last30, lambda x: x["company"], 10),
        "countries_top10": countries,
        "countries_top10_30d": top([x for x in last30 if x["country"] != "Unknown"], lambda x: x["country"], 10),
        "massive_headlines": massive,
        "excluded": dropped,
        "events_kept": [{k: x[k] for k in ("slug", "company", "start", "headcount", "pct", "country", "industry", "label", "kind")}
                        for x in sorted(keep, key=lambda x: x["start"])],
    }
    dst = HERE / "data/numbers.json"
    dst.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(json.dumps({k: out[k] for k in ("totals", "window_from", "window_to")}, indent=1))
    print("excluded:", len(dropped))


if __name__ == "__main__":
    main()
