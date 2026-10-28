"""CLI: python -m radar [fetch [sources..] | process | build | serve [port] | report | all]"""
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

from . import consensus, sources
from .db import connect
from .util import NET, mem_available_mb, mem_guard, now_iso, peak_rss_mb


BATCH = 400


def fetch(names=None):
    """Stream each source into the DB in small batches, one source at a time, and log what it cost."""
    con = connect()
    explicit = bool(names)
    names = names or list(sources.ALL)
    # LR_DAILY=edgar,...: in a full fetch, these sources run at most once a day (skipped if an ok run is < 23 h old).
    daily = {s for s in os.environ.get("LR_DAILY", "").split(",") if s} if not explicit else set()
    total = 0
    mode = "backfill" if os.environ.get("LR_BACKFILL") == "1" else os.environ.get("LR_BACKFILL", "auto")
    for n in names:
        if n in daily:
            last = con.execute("SELECT MAX(at) FROM source_runs WHERE source = ? AND ok = 1", (n,)).fetchone()[0]
            if last and last > (datetime.now(timezone.utc) - timedelta(hours=23)).replace(microsecond=0).isoformat():
                print(f"fetch {n}: skipped (daily source, last ok run {last})")
                continue
        print(f"fetch {n}")
        for k in NET:
            NET[k] = 0
        t0, count, new, ok, note = time.time(), 0, 0, 1, ""
        min_avail = mem_guard()
        before = con.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        try:
            batch = []
            for it in sources.ALL[n]():
                batch.append(it)
                if len(batch) >= BATCH:
                    _store(con, batch)
                    count += len(batch)
                    batch = []
                    min_avail = min(min_avail, mem_guard())
            _store(con, batch)
            count += len(batch)
        except Exception as e:  # one broken source must not stop the run
            print(f"  ! {n} failed: {e!r}")
            ok, note = 0, repr(e)[:300]
        new = con.execute("SELECT COUNT(*) FROM items").fetchone()[0] - before
        wall = round(time.time() - t0, 1)
        con.execute("""INSERT INTO source_runs(at, source, mode, wall_s, items, new_items, requests, cache_hits, net_bytes, errors,
                       rss_mb, min_avail_mb, ok, note) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (now_iso(), n, mode, wall, count, new, NET["requests"], NET["cache_hits"], NET["bytes"], NET["errors"],
                     peak_rss_mb(), min(min_avail, mem_available_mb()), ok, note))
        con.commit()
        print(f"  {n}: {count} items ({new} new) in {wall}s, {NET['requests']} requests, "
              f"{NET['bytes'] / 1e6:.1f} MB, peak RSS {peak_rss_mb()} MB")
        total += count
    print(f"fetched {total} items")


def _store(con, items):
    for it in items:
        con.execute("""INSERT INTO items(uid, source, tier, publisher, url, title, text, published, fetched_at, meta)
            VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(uid) DO UPDATE SET title=excluded.title, text=excluded.text,
            meta=excluded.meta, tier=excluded.tier""",
            (it["uid"], it["source"], it["tier"], it["publisher"], it["url"], it["title"], it["text"],
             it["published"], now_iso(), json.dumps(it["meta"], ensure_ascii=False)))
    con.commit()


def process():
    con = connect()
    t0 = time.time()
    mem_guard()
    n_claims = consensus.build_claims(con)
    t1 = time.time()
    mem_guard()
    n_events = consensus.build_events(con)
    stats = {r[0]: r[1] for r in con.execute("SELECT source, COUNT(*) FROM items GROUP BY source")}
    stats.update(claims=n_claims, visible_events=n_events, claims_s=round(t1 - t0, 1), events_s=round(time.time() - t1, 1),
                 rss_mb=peak_rss_mb())
    con.execute("INSERT INTO runs(at, stats) VALUES(?,?)", (now_iso(), json.dumps(stats)))
    con.commit()
    print("process:", stats)


def main(argv):
    cmd = argv[0] if argv else "all"
    if cmd == "fetch":
        fetch(argv[1:] or None)
    elif cmd == "process":
        process()
    elif cmd == "build":
        from .build import build
        t0 = time.time()
        build()
        print(f"build {time.time() - t0:.1f}s, peak RSS {peak_rss_mb()} MB")
    elif cmd == "serve":
        from .build import serve
        serve(int(argv[1]) if len(argv) > 1 else 8000)
    elif cmd == "report":
        from .report import report
        report()
    elif cmd == "all":
        t0 = time.time()
        fetch(); process()
        from .build import build
        build()
        print(f"all done in {time.time() - t0:.0f}s")
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
