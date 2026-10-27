"""Fetchers. Each returns a list of item dicts:
{uid, source, tier, publisher, url, title, text, published, meta}
Official sources (EDGAR, WARN) put pre-structured fields in meta.
"""
import json
import re
import urllib.parse
import xml.etree.ElementTree as ET
import zipfile
from datetime import date, timedelta
from io import BytesIO

from .ref import DOMAIN_PUBLISHER, US_STATE_CODES, industry_from_naics, industry_from_sic, publisher_tier
from .util import SEC_UA, SINCE, TODAY, fetch, parse_date, strip_html

# ---------------------------------------------------------------- Google News
GN_QUERIES = ['layoffs', '"lay off"', '"job cuts"', '"cut jobs"', '"workforce reduction"', 'redundancies']
GN_RECENT_EDITIONS = [("US", "en-US", "US:en"), ("GB", "en-GB", "GB:en"), ("IN", "en-IN", "IN:en"),
                      ("CA", "en-CA", "CA:en"), ("AU", "en-AU", "AU:en"), ("SG", "en-SG", "SG:en")]


def _gn_url(q, gl="US", hl="en-US", ceid="US:en"):
    return f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl={hl}&gl={gl}&ceid={ceid}"


def _gn_parse(body, edition):
    out = []
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return out
    for it in root.iter("item"):
        title = it.findtext("title") or ""
        src = it.find("source")
        pub = (src.text if src is not None else "") or ""
        if pub and title.endswith(" - " + pub):
            title = title[: -len(pub) - 3]
        link = it.findtext("link") or ""
        guid = it.findtext("guid") or link
        out.append({
            "uid": "gn:" + guid, "source": "gnews", "tier": publisher_tier(pub), "publisher": pub or "Unknown",
            "url": link, "title": title.strip(), "text": "", "published": parse_date(it.findtext("pubDate")),
            "meta": {"edition": edition, "publisher_url": src.get("url") if src is not None else None},
        })
    return out


def _want_backfill(source="gnews"):
    """LR_BACKFILL=1 always, 0 never, auto (default): first run of that source, or once a day at 03:xx UTC."""
    import os
    from datetime import datetime, timezone
    from .util import DATA
    flag = os.environ.get("LR_BACKFILL", "auto")
    if flag in ("0", "1"):
        return flag == "1"
    import sqlite3
    try:
        n = sqlite3.connect(DATA / "radar.db").execute("SELECT COUNT(*) FROM items WHERE source = ?", (source,)).fetchone()[0]
    except sqlite3.Error:
        n = 0
    return n == 0 or datetime.now(timezone.utc).hour == 3


def google_news(backfill=None):
    backfill = _want_backfill() if backfill is None else backfill
    urls = []
    # Recent window across several English editions.
    for gl, hl, ceid in GN_RECENT_EDITIONS:
        for q in GN_QUERIES[:3]:
            urls.append((_gn_url(q + " when:30d", gl, hl, ceid), gl))
    # Year-to-date backfill in half-month windows (Google caps each query at 100 results).
    if backfill:
        d = SINCE
        while d < TODAY:
            e = min(d + timedelta(days=15), TODAY + timedelta(days=1))
            for q in GN_QUERIES:
                urls.append((_gn_url(f"{q} after:{d.isoformat()} before:{e.isoformat()}"), "US"))
            d = e
    n = 0
    for i, (u, ed) in enumerate(urls):
        body = fetch(u, ttl=6 * 3600, min_interval=1.2)
        if body:
            got = _gn_parse(body, ed)
            n += len(got)
            yield from got
        if i % 20 == 0:
            print(f"  gnews {i + 1}/{len(urls)} queries, {n} items")


# ---------------------------------------------------------------- SEC EDGAR 8-K Item 2.05
def _edgar_headcount(text):
    """Pull headcount / % from the Item 2.05 section of an 8-K."""
    i = text.find("Item 2.05")
    seg = text[i: i + 6000] if i >= 0 else text[:8000]
    hc = pct = None
    m = re.search(r"(?:approximately|about|roughly|up to|an estimated)\s+(\d{1,3}(?:,\d{3})+|\d+)\s+(?:\w+\s+){0,3}?"
                  r"(?:employees|positions|roles|jobs|team members|associates|full-time)", seg, re.I)
    if m:
        hc = int(m.group(1).replace(",", ""))
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:%|percent)\s+of\s+(?:the\s+)?(?:Company['’]s\s+|its\s+|our\s+)?(?:global\s+|total\s+|current\s+|overall\s+)?"
                  r"(?:workforce|employees|headcount|employee base|staff)", seg, re.I)
    if m:
        pct = float(m.group(1))
    return hc, pct, seg[:2500]


def edgar(start=None):
    start = start or SINCE.isoformat()
    items, frm = [], 0
    while True:
        u = ("https://efts.sec.gov/LATEST/search-index?q=%22Item%202.05%22&forms=8-K&dateRange=custom"
             f"&startdt={start}&enddt={TODAY.isoformat()}&from={frm}")
        body = fetch(u, ttl=6 * 3600, ua=SEC_UA, min_interval=0.3)
        if not body:
            break
        hits = json.loads(body)["hits"]
        for h in hits["hits"]:
            s = h["_source"]
            if "2.05" not in (s.get("items") or []):
                continue
            adsh, fname = h["_id"].split(":", 1)
            cik = (s.get("ciks") or ["0"])[0].lstrip("0")
            doc_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{adsh.replace('-', '')}/{fname}"
            name = re.sub(r"\s*\(.*$", "", (s.get("display_names") or ["?"])[0]).strip()
            loc = (s.get("biz_locations") or [""])[0]
            st = loc.rsplit(",", 1)[-1].strip() if "," in loc else ""
            country = "United States" if st in US_STATE_CODES else None
            raw = fetch(doc_url, ttl=None, ua=SEC_UA, min_interval=0.15, max_bytes=3_000_000)
            text = strip_html(raw.decode("utf-8", "ignore")) if raw else ""
            hc, pct, snippet = _edgar_headcount(text)
            items.append({
                "uid": "edgar:" + h["_id"], "source": "edgar", "tier": "official", "publisher": "SEC EDGAR (8-K Item 2.05)",
                "url": doc_url, "title": f"{name} files 8-K Item 2.05 (exit or disposal costs)", "text": snippet,
                "published": s.get("file_date"),
                "meta": {"company": name, "headcount": hc, "pct": pct, "location": loc, "country": country,
                         "industry": industry_from_sic((s.get("sics") or [None])[0]), "kind": "layoff"},
            })
        frm += 100
        if frm >= hits["total"]["value"] or frm > 3000:
            break
    print(f"  edgar {len(items)} filings")
    return items


# ---------------------------------------------------------------- WARN: California EDD (xlsx)
CA_WARN_XLSX = "https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx"
CA_WARN_PAGE = "https://edd.ca.gov/en/jobs_and_training/Layoff_Services_WARN/"
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def _xlsx_rows(body):
    z = zipfile.ZipFile(BytesIO(body))
    sst = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS):
            sst.append("".join(t.text or "" for t in si.iter("{%s}t" % NS["m"])))
    for name in sorted(n for n in z.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", n)):
        for r in ET.fromstring(z.read(name)).iter("{%s}row" % NS["m"]):
            row = []
            for c in r.findall("m:c", NS):
                v = c.findtext("m:v", namespaces=NS)
                if c.get("t") == "s" and v is not None:
                    v = sst[int(v)]
                elif c.get("t") == "inlineStr":
                    v = "".join(t.text or "" for t in c.iter("{%s}t" % NS["m"]))
                row.append(v)
            yield name, row


def warn_ca():
    body = fetch(CA_WARN_XLSX, ttl=12 * 3600)
    if not body:
        return []
    items, header, sheet = [], None, None
    for name, row in _xlsx_rows(body):
        raw = [(x or "").strip() for x in row]
        cells = [re.sub(r"\s+", " ", x) for x in raw]
        if "Company" in cells and "County/Parish" in cells:
            header, sheet = cells, name
            continue
        if not header or name != sheet or len(cells) < 7:
            continue
        rec = dict(zip(header, cells))
        raw_addr = dict(zip(header, raw)).get("Address", "")
        kind = rec.get("Layoff/ Closure", "")
        if "Temporary" in kind:
            continue  # count permanent job losses only
        notice = parse_date(rec.get("Notice Date"))
        try:
            n = int(float(rec.get("No. Of Employees") or 0))
        except ValueError:
            continue
        if not notice or notice < SINCE.isoformat() or n <= 0:
            continue
        company = strip_html(rec.get("Company", ""))
        addr = rec.get("Address", "")
        city = re.sub(r"\s+CA\s+\d{5}.*$", "", raw_addr).split("  ")[-1].strip()
        items.append({
            "uid": f"warn_ca:{company}:{notice}:{addr}", "source": "warn_ca", "tier": "official",
            "publisher": "California EDD (WARN notice)", "url": CA_WARN_PAGE,
            "title": f"{company}: WARN notice, {n} employee{'s' if n != 1 else ''} ({kind.lower()}), {city}, CA",
            "text": "", "published": notice,
            "meta": {"company": company, "headcount": n, "location": f"{city}, CA", "country": "United States",
                     "industry": industry_from_naics((rec.get("Related Industry") or "").split(" ")[0]),
                     "kind": "closure" if "Closure" in kind else "layoff",
                     "effective": parse_date(rec.get("Effective Date")), "county": rec.get("County/Parish")},
        })
    print(f"  warn_ca {len(items)} notices")
    return items


# ---------------------------------------------------------------- WARN: Maryland (HTML table)
MD_WARN = "https://labor.maryland.gov/employment/warn.shtml"


def warn_md():
    from html.parser import HTMLParser

    class T(HTMLParser):
        def __init__(self):
            super().__init__()
            self.rows, self.row, self.cell, self.inc = [], None, [], False

        def handle_starttag(self, tag, a):
            if tag == "tr": self.row = []
            elif tag in ("td", "th"): self.cell, self.inc = [], True
            elif tag == "br" and self.inc: self.cell.append(" ")

        def handle_endtag(self, tag):
            if tag in ("td", "th") and self.row is not None:
                self.row.append(re.sub(r"\s+", " ", "".join(self.cell)).strip()); self.inc = False
            elif tag == "tr" and self.row:
                self.rows.append(self.row); self.row = None

        def handle_data(self, d):
            if self.inc: self.cell.append(d)

    body = fetch(MD_WARN, ttl=12 * 3600)
    if not body:
        return []
    p = T(); p.feed(body.decode("utf-8", "ignore"))
    items, header = [], None
    for r in p.rows:
        if "Company" in r and "Notice Date" in r:
            header = r; continue
        if not header or len(r) < len(header):
            continue
        rec = dict(zip(header, r))
        notice = parse_date(rec.get("Notice Date"))
        typ = rec.get("Type", "")
        if not notice or notice < SINCE.isoformat() or "Temporary" in typ:
            continue
        try:
            n = int(re.sub(r"\D", "", rec.get("Total Employees", "")) or 0)
        except ValueError:
            continue
        if n <= 0:
            continue
        company = rec["Company"]
        loc = rec.get("Location", "")
        m = re.search(r"([A-Z][A-Za-z .]+),\s*MD", loc)
        city = m.group(1).split("  ")[-1].strip() if m else rec.get("Local Area", "")
        city = re.sub(r"^.*?(?:Suite \w+|Street|St\.|Road|Rd\.|Blvd\.?|Avenue|Ave\.?|Drive|Dr\.?|Pike|Way|Lane|Court|Parkway)\s+", "", city)
        items.append({
            "uid": f"warn_md:{company}:{notice}:{loc}", "source": "warn_md", "tier": "official",
            "publisher": "Maryland DOL (WARN notice)", "url": MD_WARN,
            "title": f"{company}: WARN notice, {n} employee{'s' if n != 1 else ''} ({typ.lower()}), {city}, MD", "text": "",
            "published": notice,
            "meta": {"company": company, "headcount": n, "location": f"{city}, MD", "country": "United States",
                     "industry": industry_from_naics(rec.get("NAICS Code")),
                     "kind": "closure" if "Closure" in typ else "layoff", "effective": parse_date(rec.get("Effective Date"))},
        })
    print(f"  warn_md {len(items)} notices")
    return items


# ---------------------------------------------------------------- Hacker News (Algolia)
def hackernews():
    items = []
    since = int(date(SINCE.year, SINCE.month, SINCE.day).strftime("%s"))
    for q in ["layoffs", "lays off", "laying off", "job cuts"]:
        for page in range(5):
            u = ("https://hn.algolia.com/api/v1/search_by_date?tags=story&hitsPerPage=100"
                 f"&query={urllib.parse.quote(q)}&numericFilters=created_at_i>{since}&page={page}")
            body = fetch(u, ttl=6 * 3600, min_interval=0.5)
            if not body:
                break
            d = json.loads(body)
            for h in d.get("hits", []):
                url = h.get("url") or f"https://news.ycombinator.com/item?id={h['objectID']}"
                dom = urllib.parse.urlparse(url).netloc.removeprefix("www.")
                items.append({
                    "uid": "hn:" + h["objectID"], "source": "hn", "tier": "aggregator",
                    "publisher": DOMAIN_PUBLISHER.get(dom, dom or "Hacker News"), "url": url,
                    "title": h.get("title") or "", "text": "", "published": parse_date(h.get("created_at")),
                    "meta": {"hn": f"https://news.ycombinator.com/item?id={h['objectID']}", "points": h.get("points")},
                })
            if page + 1 >= d.get("nbPages", 0):
                break
    print(f"  hn {len(items)} stories")
    return items


# ---------------------------------------------------------------- Reddit (RSS; JSON API needs OAuth)
def reddit():
    items = []
    for sub in ["layoffs"]:
        body = fetch(f"https://www.reddit.com/r/{sub}/new/.rss?limit=100", ttl=3 * 3600, min_interval=2)
        if not body:
            continue
        try:
            root = ET.fromstring(body)
        except ET.ParseError:
            continue
        A = "{http://www.w3.org/2005/Atom}"
        for e in root.iter(A + "entry"):
            link = e.find(A + "link").get("href")
            items.append({
                "uid": "reddit:" + (e.findtext(A + "id") or link), "source": "reddit", "tier": "social",
                "publisher": f"Reddit r/{sub}", "url": link, "title": e.findtext(A + "title") or "",
                "text": strip_html(e.findtext(A + "content") or "")[:600],
                "published": parse_date(e.findtext(A + "updated") or e.findtext(A + "published")), "meta": {},
            })
    print(f"  reddit {len(items)} posts")
    return items


def _all():
    """The registry lives in config.SOURCES ("module:adapter"), one adapter per source."""
    import importlib
    from .config import SOURCES
    out = {}
    for name, ref in SOURCES.items():
        mod, fn = ref.split(":")
        out[name] = getattr(importlib.import_module("radar." + mod), fn)
    return out


class _Lazy(dict):
    def _fill(self):
        if not dict.__len__(self):
            self.update(_all())

    def __getitem__(self, k):
        self._fill()
        return dict.__getitem__(self, k)

    def __iter__(self):
        self._fill()
        return dict.__iter__(self)

    def __len__(self):
        self._fill()
        return dict.__len__(self)


ALL = _Lazy()
