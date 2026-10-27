"""Quality report: `python -m radar report`. Read-only; prints the issues worth fixing as rules or aliases in code."""
import re
from collections import defaultdict
from datetime import date

from .db import connect
from .places import WORKFORCE
from .util import SINCE

JUNK = re.compile(r"(?i)^(the|a|an|this|these|its|our|their|new|more|top|big|major|global|local|state|federal|government|"
                  r"report|reports|layoffs?|jobs?|workers?|employees?|staff|company|companies|firm|firms|tech|union|"
                  r"why|how|what|who|when|after|amid|as|us|uk|eu|ceo|china|india|japan|germany|france)$|"
                  r"^\d|^[\W_]|\b(layoffs?|job cuts|laid off|workers|employees|says|said)\b")
BIG_NO_WF = 50_000  # headcount above this without a curated workforce row is suspicious


def _norm(s):
    s = re.sub(r"(?i)\b(inc|corp|corporation|ltd|limited|plc|group|holdings?|ag|se|sa|co|company|the)\b\.?", "", s or "")
    return re.sub(r"\W+", "", s.lower())


def report(limit=25):
    con = connect()
    evs = [dict(r) for r in con.execute(
        "SELECT id, slug, company, start, headcount, country, kind, label, n_publishers FROM events "
        "WHERE visible = 1 AND start >= ? ORDER BY start", (SINCE.isoformat(),))]
    counted = [e for e in evs if e["kind"] != "plan"]
    print(f"window {SINCE} -> today: {len(evs)} visible events ({len(evs) - len(counted)} announced plans), "
          f"{sum(e['headcount'] or 0 for e in counted):,} people counted, "
          f"{len({e['country'] for e in evs if e['country'] and e['country'] != 'Unknown'})} countries")

    print("\n## Suspected duplicates (same or near-same company, starts within 14 days)")
    by = defaultdict(list)
    for e in evs:
        by[_norm(e["company"])[:12]].append(e)
    dups = []
    for k, rows in by.items():
        for a, b in zip(rows, rows[1:]):
            if k and (date.fromisoformat(b["start"]) - date.fromisoformat(a["start"])).days <= 14:
                dups.append((a, b))
    for a, b in sorted(dups, key=lambda p: -max(p[0]["headcount"] or 0, p[1]["headcount"] or 0))[:limit]:
        print(f"  {a['company']!r} {a['start']} {a['headcount']} | {b['company']!r} {b['start']} {b['headcount']}")
    print(f"  total: {len(dups)}")

    print("\n## Unknown country")
    unk = [e for e in evs if not e["country"] or e["country"] == "Unknown"]
    for e in sorted(unk, key=lambda e: -(e["headcount"] or 0))[:limit]:
        print(f"  {e['company']!r} ({e['slug']}) {e['start']} {e['headcount']}")
    print(f"  total: {len(unk)}")

    print("\n## Headcount bigger than the company (or > 50k with no workforce row)")
    big = []
    for e in evs:
        n, wf = e["headcount"] or 0, WORKFORCE.get(e["slug"])
        if (wf and n > wf[0]) or (not wf and n > BIG_NO_WF):
            big.append((e, wf[0] if wf else None))
    for e, wf in sorted(big, key=lambda p: -p[0]["headcount"])[:limit]:
        print(f"  {e['company']!r} ({e['slug']}) {e['start']} {e['headcount']:,} vs workforce {wf} kind={e['kind']}")
    print(f"  total: {len(big)}")

    print("\n## Junk company names")
    junk = [e for e in evs if JUNK.search(e["company"] or "") or len(e["company"] or "") < 3 or len((e["company"] or "").split()) > 5]
    for e in sorted(junk, key=lambda e: -(e["headcount"] or 0))[:limit]:
        print(f"  {e['company']!r} ({e['slug']}) {e['start']} {e['headcount']}")
    print(f"  total: {len(junk)}")

    print("\n## Last fetch per source")
    for r in con.execute("""SELECT source, items, new_items, wall_s, ok, note FROM source_runs WHERE id IN
                            (SELECT MAX(id) FROM source_runs GROUP BY source) ORDER BY source"""):
        print(f"  {r['source']}: {r['items']} items ({r['new_items']} new) {r['wall_s']}s ok={r['ok']} {r['note'] or ''}"[:200])
