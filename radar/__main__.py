"""CLI: python -m radar [fetch [sources..] | process | build | serve [port] | all]"""
import json
import sys

from . import consensus, sources
from .db import connect
from .util import now_iso


def fetch(names=None):
    con = connect()
    names = names or list(sources.ALL)
    total = 0
    for n in names:
        print(f"fetch {n}")
        try:
            items = sources.ALL[n]()
        except Exception as e:  # one broken source must not stop the run
            print(f"  ! {n} failed: {e!r}")
            continue
        for it in items:
            con.execute("""INSERT INTO items(uid, source, tier, publisher, url, title, text, published, fetched_at, meta)
                VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(uid) DO UPDATE SET title=excluded.title, text=excluded.text,
                meta=excluded.meta, tier=excluded.tier""",
                (it["uid"], it["source"], it["tier"], it["publisher"], it["url"], it["title"], it["text"],
                 it["published"], now_iso(), json.dumps(it["meta"])))
        con.commit()
        total += len(items)
    print(f"fetched {total} items")


def process():
    con = connect()
    n_claims = consensus.build_claims(con)
    n_events = consensus.build_events(con)
    stats = {r[0]: r[1] for r in con.execute("SELECT source, COUNT(*) FROM items GROUP BY source")}
    stats.update(claims=n_claims, visible_events=n_events)
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
        build()
    elif cmd == "serve":
        from .build import serve
        serve(int(argv[1]) if len(argv) > 1 else 8000)
    elif cmd == "all":
        fetch(); process()
        from .build import build
        build()
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
