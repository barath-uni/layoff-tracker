"""More US WARN states: Texas (open-data API), Pennsylvania (HTML), Colorado (public Google Sheet), Washington
(ASP.NET table). Same item shape as warn_ca / warn_md: official tier, structured fields in meta."""
import csv
import io
import json
import re
import urllib.parse
from html import unescape

from .ref import industry_from_naics
from .util import BROWSER_UA, SINCE, fetch, parse_date, strip_html


def _item(src, publisher, url, company, n, notice, city, st, kind, effective=None, industry=None, extra=None):
    company = re.sub(r"\s+", " ", company or "").strip()
    meta = {"company": company, "headcount": n, "location": f"{city}, {st}" if city else st, "country": "United States",
            "industry": industry, "kind": kind, "effective": effective}
    meta.update(extra or {})
    return {"uid": f"{src}:{company}:{notice}:{city}:{n}", "source": src, "tier": "official", "publisher": publisher,
            "url": url, "title": f"{company}: WARN notice, {n} employee{'s' if n != 1 else ''} ({kind}), {city or st}, {st}",
            "text": "", "published": notice, "meta": meta}


def _int(s):
    s = re.sub(r"[^\d]", "", str(s or ""))
    return int(s) if s else 0


# ---------------------------------------------------------------- Texas Workforce Commission (data.texas.gov, Socrata)
TX_API = "https://data.texas.gov/resource/8w53-c4f6.json"
TX_PAGE = "https://www.twc.texas.gov/data-reports/warn-notice"


def warn_tx():
    n = 0
    off = 0
    while True:
        q = urllib.parse.urlencode({"$where": f"notice_date >= '{SINCE.isoformat()}T00:00:00'", "$limit": 1000,
                                    "$offset": off, "$order": "notice_date"})
        body = fetch(f"{TX_API}?{q}", ttl=12 * 3600)
        rows = json.loads(body or b"[]")
        for r in rows:
            cnt = _int(r.get("total_layoff_number"))
            notice = parse_date(r.get("notice_date"))
            if not cnt or not notice:
                continue
            n += 1
            yield _item("warn_tx", "Texas Workforce Commission (WARN notice)", TX_PAGE, r.get("job_site_name"), cnt, notice,
                        (r.get("city_name") or "").title(), "TX", "layoff", parse_date(r.get("layoff_date")),
                        extra={"county": r.get("county_name")})
        if len(rows) < 1000:
            break
        off += 1000
    print(f"  warn_tx {n} notices")


# ---------------------------------------------------------------- Pennsylvania L&I (accordion page: year > month > company)
PA_PAGE = "https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices"
MONTHS = {m: i for i, m in enumerate("January February March April May June July August September October November December".split(), 1)}


def warn_pa():
    body = fetch(PA_PAGE, ttl=12 * 3600, max_bytes=8_000_000)
    if not body:
        return
    s = body.decode("utf-8", "ignore")
    tok = re.compile(r'cmp-accordion__title">([^<]+)<|repo:modifyDate&#34;:&#34;([\d-]+)T[^&]*&#34;,&#34;xdm:text&#34;:&#34;(.*?)&#34;}}"', re.S)
    from .util import TODAY
    # The page lists months newest first without year headings: count the year down whenever the month goes up.
    year, month, company = TODAY.year, None, None
    n = 0
    for m in tok.finditer(s):
        if m.group(1):
            t = unescape(m.group(1)).strip()
            if re.fullmatch(r"20\d\d", t):
                year, month = int(t), None
            elif t in MONTHS:
                if month and MONTHS[t] > month or (month is None and MONTHS[t] > TODAY.month):
                    year -= 1
                month = MONTHS[t]
            else:
                company = t
            continue
        if not (year and month and company):
            continue
        txt = unescape(unescape(m.group(3))).replace("\\r", " ").replace("\\n", " ")
        txt = re.sub(r"<[^>]+>", "\n", txt).replace("​", "")
        lines = [re.sub(r"\s+", " ", x).strip() for x in txt.split("\n") if x.strip()]
        flat = " ".join(lines)
        cnt = _int((re.search(r"# AFFECTED:\s*([\d,]+)", flat) or [None, ""])[1])
        kind_m = re.search(r"CLOSURE OR LAYOFF:\s*(\w+)", flat)
        eff = re.search(r"EFFECTIVE DATE:\s*(?:beginning\s*)?(\d{1,2}/\d{1,2}/\d{2,4})", flat)
        city_m = re.search(r",?\s*([A-Z][A-Za-z .'-]+),\s*PA\b", flat)
        modified = m.group(2)
        notice = modified if modified and modified[:7] == f"{year}-{month:02d}" else f"{year}-{month:02d}-01"
        if not cnt or notice < SINCE.isoformat():
            company = None
            continue
        city = city_m.group(1).split("  ")[-1].strip() if city_m else ""
        city = re.sub(r"^.*?\d+\s+[\w .]+?(?:Street|St\.?|Road|Rd\.?|Avenue|Ave\.?|Boulevard|Blvd\.?|Drive|Dr\.?|Pike|Way|Lane|Highway|Parkway)\s+", "", city)
        kind = "closure" if kind_m and kind_m.group(1).lower().startswith("closure") else "layoff"
        if re.search(r"(?i)temporary", flat):
            company = None
            continue
        n += 1
        yield _item("warn_pa", "Pennsylvania L&I (WARN notice)", PA_PAGE, company, cnt, notice, city, "PA", kind,
                    parse_date(eff.group(1)) if eff else None, extra={"county": (re.search(r"COUNTY:\s*([A-Za-z ]+?)\s+#", flat) or [None, None])[1]})
        company = None
    print(f"  warn_pa {n} notices")


# ---------------------------------------------------------------- Colorado CDLE (public Google Sheets, one per year)
CO_PAGE = "https://cdle.colorado.gov/employers/layoff-separations/layoff-warn-list"
CO_SHEETS = ["19jmo4Cwj933cmSBKV1t0zZ5O-2H5IpiLIhSH9MF8WF0", "1aFv4ntRhjnTMFKqBnuzbIkExCWgp6vnblYGm_h9GUeI",
             "1tDQPJ8jVqmyGbLYs6hUZiiNQIsablkZyLJt8rLIzanY"]


def warn_co():
    n, seen = 0, set()
    for i, sid in enumerate(CO_SHEETS):
        if i and SINCE.year >= 2026:
            break  # older sheets only matter for a 2025 backfill
        body = fetch(f"https://docs.google.com/spreadsheets/d/{sid}/export?format=csv", ttl=12 * 3600)
        if not body:
            continue
        for r in csv.DictReader(io.StringIO(body.decode("utf-8", "ignore"))):
            r = {(k or "").strip(): (v or "").strip() for k, v in r.items()}
            notice = parse_date(r.get("WARN Date") or r.get("Received"))
            perm = _int(r.get("# Permanent"))
            if not notice or notice < SINCE.isoformat() or not perm or "update" in (r.get("Company") or "").lower():
                continue
            area = (r.get("Workforce Area") or "").split(",")[0].strip()
            key = (r.get("Company"), notice, perm)
            if key in seen:
                continue
            seen.add(key)
            reason = r.get("Reason for Layoffs") or ""
            n += 1
            yield _item("warn_co", "Colorado CDLE (WARN notice)", CO_PAGE, r.get("Company"), perm, notice, area, "CO",
                        "closure" if "closure" in reason.lower() else "layoff", parse_date(r.get("Begin Date")),
                        industry_from_naics((r.get("NAICS") or "")[:6]), extra={"reason": reason[:120]})
    print(f"  warn_co {n} notices")


# ---------------------------------------------------------------- Washington ESD (ASP.NET grid, newest first, postback paging)
WA_URL = "https://fortress.wa.gov/esd/file/WARN/Public/SearchWARN.aspx"
WA_PAGE = "https://esd.wa.gov/employer-requirements/layoffs-and-employee-notifications/worker-adjustment-and-retraining-notification-warn-layoff-and-closure-database"


def _wa_fields(html):
    return {k: unescape(v) for k, v in re.findall(r'<input type="hidden" name="(__\w+)" id="\w+" value="([^"]*)"', html)}


def warn_wa(max_pages=60):
    body = fetch(WA_URL, ttl=6 * 3600)
    n = 0
    for page in range(2, max_pages + 2):
        if not body:
            break
        html = body.decode("utf-8", "ignore")
        oldest = None
        for row in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", html):
            c = [strip_html(x) for x in re.findall(r"(?is)<td[^>]*>(.*?)</td>", row)]
            if len(c) < 7 or not re.search(r"\d", c[3] or ""):
                continue
            company, loc, start, cnt, kind, typ, recv = c[:7]
            notice = parse_date(recv)
            if not notice:
                continue
            oldest = min(oldest or notice, notice)
            if notice < SINCE.isoformat() or "temp" in typ.lower() or not _int(cnt):
                continue
            city = loc.split(",")[0].strip().title()
            n += 1
            yield _item("warn_wa", "Washington ESD (WARN notice)", WA_PAGE, company, _int(cnt), notice, city, "WA",
                        "closure" if "closure" in kind.lower() else "layoff", parse_date(start))
        if oldest and oldest < SINCE.isoformat():
            break
        f = _wa_fields(html)
        if "__VIEWSTATE" not in f:
            break
        f.update({"__EVENTTARGET": "ucPSW$gvMain", "__EVENTARGUMENT": f"Page${page}"})
        data = urllib.parse.urlencode(f).encode()
        body = fetch(WA_URL, ttl=6 * 3600, data=data, cache_key=f"{WA_URL}#page{page}", min_interval=1.5,
                     headers={"Content-Type": "application/x-www-form-urlencoded", "Referer": WA_URL, "User-Agent": BROWSER_UA})
    print(f"  warn_wa {n} notices")
