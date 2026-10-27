"""Global sources: Google News per country edition and language, GDELT DOC 2.0, and free exchange disclosure feeds
(Japan TDnet, India NSE, Australia ASX). All are generators: items stream into the DB in batches.

Every item carries meta.lang (ISO 639-1) and meta.src_country (the edition's or outlet's country). The extractor uses
lang to pick its rules; consensus uses src_country only as a last-resort country when the text names none.
"""
import json
import re
import subprocess
import unicodedata
import urllib.parse
from datetime import date, datetime, timedelta, timezone
from html import unescape

from .ref import publisher_tier
from .sources import _gn_parse, _gn_url, _want_backfill
from .util import SINCE, TODAY, fetch, parse_date, strip_html

# ---------------------------------------------------------------- Google News: country editions x local keywords
# Layoff wording per language. Google News accepts OR and quoted phrases. Kept short so each query stays precise.
LANG_Q = {
    "en": 'layoffs OR "job cuts" OR redundancies OR "cut jobs" OR retrenchment',
    "de": 'Stellenabbau OR Entlassungen OR "streicht Stellen" OR "baut Stellen ab" OR Jobabbau OR Arbeitsplatzabbau',
    "fr": 'licenciements OR "suppressions de postes" OR "plan social" OR "suppression d\'emplois" OR "supprime postes"',
    "es": 'despidos OR ERE OR "recorte de empleos" OR "recorte de personal" OR "despido masivo"',
    "pt": 'demissões OR "demissão em massa" OR "corte de empregos" OR despedimentos OR "despedimento coletivo"',
    "it": 'licenziamenti OR esuberi OR "taglio di posti" OR "tagli al personale"',
    "nl": 'ontslagen OR "banen weg" OR "schrapt banen" OR "banen schrappen" OR ontslaggolf',
    "pl": '"zwolnienia grupowe" OR zwolnienia OR "redukcja etatów"',
    "sv": 'varsel OR varslar OR "säger upp" OR uppsägningar',
    "no": 'nedbemanning OR oppsigelser OR "kutter stillinger"',
    "da": 'fyringer OR afskedigelser OR fyrer OR "nedlægger stillinger"',
    "fi": 'irtisanoo OR irtisanomiset OR muutosneuvottelut OR yt-neuvottelut',
    "cs": 'propouštění OR propustí OR "hromadné propouštění"',
    "hu": 'leépítés OR elbocsátás OR leépít',
    "ro": 'concedieri OR disponibilizări OR concediază',
    "el": 'απολύσεις OR "περικοπές θέσεων"',
    "tr": '"işten çıkarma" OR "işten çıkardı" OR "işçi çıkarma" OR "toplu işten çıkarma"',
    "ru": '"сокращение сотрудников" OR сократит OR увольнения OR "массовые сокращения"',
    "uk": '"скорочення працівників" OR звільнення OR скоротить',
    "ja": '人員削減 OR 希望退職 OR 早期退職 OR リストラ',
    "zh": '裁员 OR 人员优化 OR 大裁员 OR 裁員',
    "ko": '구조조정 OR 희망퇴직 OR 감원 OR 정리해고',
    "hi": 'छंटनी OR "नौकरी से निकाल"',
    "bn": 'ছাঁটাই OR "কর্মী ছাঁটাই"',
    "id": 'PHK OR "pemutusan hubungan kerja"',
    "th": 'เลิกจ้าง OR ปลดพนักงาน',
    "vi": '"sa thải" OR "cắt giảm nhân sự"',
    "ar": 'تسريح OR "تسريح موظفين" OR "الاستغناء عن"',
    "he": 'פיטורים OR מפטרת',
}

# (gl, hl, ceid, lang, country, backfill window in days). Busy editions get shorter windows: Google returns at most
# 100 results per query, so a long window in a big market silently drops stories.
EDITIONS = [
    ("GB", "en-GB", "GB:en", "en", "United Kingdom", 7), ("IN", "en-IN", "IN:en", "en", "India", 7),
    ("CA", "en-CA", "CA:en", "en", "Canada", 14), ("AU", "en-AU", "AU:en", "en", "Australia", 14),
    ("SG", "en-SG", "SG:en", "en", "Singapore", 15), ("IE", "en-IE", "IE:en", "en", "Ireland", 15),
    ("NZ", "en-NZ", "NZ:en", "en", "New Zealand", 15), ("ZA", "en-ZA", "ZA:en", "en", "South Africa", 15),
    ("NG", "en-NG", "NG:en", "en", "Nigeria", 15), ("KE", "en-KE", "KE:en", "en", "Kenya", 30),
    ("PH", "en-PH", "PH:en", "en", "Philippines", 15), ("MY", "en-MY", "MY:en", "en", "Malaysia", 15),
    ("PK", "en-PK", "PK:en", "en", "Pakistan", 30), ("IL", "en-IL", "IL:en", "en", "Israel", 15),
    ("DE", "de", "DE:de", "de", "Germany", 7), ("AT", "de-AT", "AT:de", "de", "Austria", 15),
    ("CH", "de-CH", "CH:de", "de", "Switzerland", 15), ("FR", "fr", "FR:fr", "fr", "France", 7),
    ("BE", "fr-BE", "BE:fr", "fr", "Belgium", 30), ("BE", "nl-BE", "BE:nl", "nl", "Belgium", 15),
    ("CA", "fr-CA", "CA:fr", "fr", "Canada", 30), ("NL", "nl", "NL:nl", "nl", "Netherlands", 15),
    ("IT", "it", "IT:it", "it", "Italy", 7), ("ES", "es", "ES:es", "es", "Spain", 7),
    ("MX", "es-419", "MX:es-419", "es", "Mexico", 15), ("AR", "es-419", "AR:es-419", "es", "Argentina", 15),
    ("CO", "es-419", "CO:es-419", "es", "Colombia", 30), ("CL", "es-419", "CL:es-419", "es", "Chile", 30),
    ("PE", "es-419", "PE:es-419", "es", "Peru", 30), ("BR", "pt-BR", "BR:pt-419", "pt", "Brazil", 7),
    ("PT", "pt-PT", "PT:pt-150", "pt", "Portugal", 30), ("PL", "pl", "PL:pl", "pl", "Poland", 15),
    ("SE", "sv", "SE:sv", "sv", "Sweden", 15), ("NO", "no", "NO:no", "no", "Norway", 30),
    ("DK", "da", "DK:da", "da", "Denmark", 30), ("FI", "fi", "FI:fi", "fi", "Finland", 30),
    ("CZ", "cs", "CZ:cs", "cs", "Czechia", 30), ("HU", "hu", "HU:hu", "hu", "Hungary", 30),
    ("RO", "ro", "RO:ro", "ro", "Romania", 30), ("GR", "el", "GR:el", "el", "Greece", 30),
    ("TR", "tr", "TR:tr", "tr", "Turkey", 15), ("RU", "ru", "RU:ru", "ru", "Russia", 15),
    ("UA", "uk", "UA:uk", "uk", "Ukraine", 30), ("JP", "ja", "JP:ja", "ja", "Japan", 7),
    ("KR", "ko", "KR:ko", "ko", "South Korea", 7), ("CN", "zh-CN", "CN:zh-Hans", "zh", "China", 7),
    ("TW", "zh-TW", "TW:zh-Hant", "zh", "Taiwan", 15), ("HK", "zh-HK", "HK:zh-Hant", "zh", "Hong Kong", 15),
    ("IN", "hi", "IN:hi", "hi", "India", 15), ("BD", "bn", "BD:bn", "bn", "Bangladesh", 30),
    ("ID", "id", "ID:id", "id", "Indonesia", 7), ("TH", "th", "TH:th", "th", "Thailand", 30),
    ("VN", "vi", "VN:vi", "vi", "Vietnam", 30), ("SA", "ar", "SA:ar", "ar", "Saudi Arabia", 30),
    ("EG", "ar", "EG:ar", "ar", "Egypt", 30), ("AE", "ar", "AE:ar", "ar", "United Arab Emirates", 30),
    ("IL", "he", "IL:he", "he", "Israel", 15),
]


def gnews_intl(backfill=None):
    """Google News in ~55 editions with local-language layoff keywords: last 7 days every run, plus a windowed
    backfill from LR_SINCE (or Jan 1) on the first run and once a day."""
    backfill = _want_backfill("gnews_intl") if backfill is None else backfill
    jobs = []
    for gl, hl, ceid, lang, cty, step in EDITIONS:
        q = LANG_Q[lang]
        jobs.append((_gn_url(f"({q}) when:7d", gl, hl, ceid), ceid, lang, cty, 3 * 3600))
        if backfill:
            d = SINCE
            while d < TODAY:
                e = min(d + timedelta(days=step), TODAY + timedelta(days=1))
                # Closed windows never change: cache them for a month. The open one refreshes like the recent query.
                ttl = 30 * 86400 if e <= TODAY - timedelta(days=2) else 6 * 3600
                jobs.append((_gn_url(f"({q}) after:{d.isoformat()} before:{e.isoformat()}", gl, hl, ceid), ceid, lang, cty, ttl))
                d = e
    n = 0
    for i, (u, ceid, lang, cty, ttl) in enumerate(jobs):
        body = fetch(u, ttl=ttl, min_interval=1.5)
        if body:
            for it in _gn_parse(body, ceid):
                it["source"] = "gnews_intl"
                it["uid"] = "gn:" + it["uid"][3:]  # same article id space as English Google News, so no double rows
                it["meta"].update(lang=lang, src_country=cty)
                n += 1
                yield it
        if i % 50 == 0:
            print(f"  gnews_intl {i + 1}/{len(jobs)} queries, {n} items")


# ---------------------------------------------------------------- GDELT DOC 2.0
# The DOC API full-text searches the machine-translated text of ~65 languages, so one English query finds
# "Stellenabbau" and "裁员" stories too. It covers a rolling ~3 months and allows one request per 5 seconds.
GDELT_Q = '(layoffs OR "job cuts" OR "laid off" OR redundancies OR "cut jobs")'
GDELT_LANGS = ["english", "german", "french", "spanish", "portuguese", "italian", "dutch", "polish", "swedish",
               "japanese", "chinese", "korean", "russian", "turkish", "indonesian", "arabic", "hindi", "vietnamese",
               "thai", "hebrew", "czech", "romanian", "danish", "norwegian", "finnish", "greek", "hungarian", "ukrainian"]
GDELT_LANG_CODE = {"english": "en", "german": "de", "french": "fr", "spanish": "es", "portuguese": "pt", "italian": "it",
                   "dutch": "nl", "polish": "pl", "swedish": "sv", "japanese": "ja", "chinese": "zh", "korean": "ko",
                   "russian": "ru", "turkish": "tr", "indonesian": "id", "arabic": "ar", "hindi": "hi", "vietnamese": "vi",
                   "thai": "th", "hebrew": "he", "czech": "cs", "romanian": "ro", "danish": "da", "norwegian": "no",
                   "finnish": "fi", "greek": "el", "hungarian": "hu", "ukrainian": "uk", "bengali": "bn", "malay": "ms"}
GDELT_COUNTRY = {"United Kingdom": "United Kingdom", "UK": "United Kingdom", "South Korea": "South Korea",
                 "Korea, South": "South Korea", "Czech Republic": "Czechia", "Russia": "Russia"}
THROTTLE = b"Please limit requests"


class SourceBlocked(Exception):
    pass


def _gdelt_get(params, ttl):
    import time
    u = "https://api.gdeltproject.org/api/v2/doc/doc?" + urllib.parse.urlencode(params)
    for attempt in range(3):
        body = fetch(u, ttl=ttl, min_interval=10, timeout=60, retries=1)
        if body and not body.startswith(THROTTLE):
            return body
        if body and body.startswith(THROTTLE):
            from .util import CACHE
            import hashlib
            (CACHE / hashlib.sha1(u.encode()).hexdigest()).unlink(missing_ok=True)  # never cache the throttle page
        print(f"  .. GDELT throttled, waiting {45 * (attempt + 1)}s")
        time.sleep(45 * (attempt + 1))
    raise SourceBlocked("GDELT DOC API keeps answering 'Please limit requests'")


def _gdelt_items(body, lang_hint=None):
    try:
        arts = json.loads(body.decode("utf-8", "ignore") or "{}").get("articles", [])
    except json.JSONDecodeError:
        return
    for a in arts:
        dom = (a.get("domain") or "").lower().removeprefix("www.")
        title = unescape(a.get("title") or "").strip()
        title = re.sub(r"\s+([:,;!?])", r"\1", title)  # GDELT spaces out punctuation ("Tamedia : 400 ...")
        title = re.sub(r"\s+-\s+", " - ", title)
        lang = GDELT_LANG_CODE.get((a.get("language") or "").lower(), lang_hint)
        sd = a.get("seendate") or ""
        pub = f"{sd[:4]}-{sd[4:6]}-{sd[6:8]}" if len(sd) >= 8 else None
        cty = a.get("sourcecountry") or None
        yield {"uid": "gdelt:" + a.get("url", ""), "source": "gdelt", "tier": publisher_tier(dom), "publisher": dom or "Unknown",
               "url": a.get("url", ""), "title": title, "text": "", "published": pub,
               "meta": {"lang": lang, "src_country": GDELT_COUNTRY.get(cty, cty), "domain": dom}}


def gdelt(backfill=None):
    """Hourly: the last 6 hours, all languages. Backfill: two-day windows over the last 4 weeks, all languages
    (250 articles each). GDELT answered most requests from this IP with 429 / 'Please limit requests', so the
    per-language, 12-week plan (GDELT_LANGS x weeks, ~360 requests) is kept for a VPS: LR_GDELT_FULL=1."""
    import os
    backfill = _want_backfill("gdelt") if backfill is None else backfill
    base = {"query": GDELT_Q, "mode": "artlist", "format": "json", "maxrecords": 250, "sort": "datedesc"}
    n = 0
    for it in _gdelt_items(_gdelt_get(dict(base, timespan="6h"), 1800)):
        n += 1
        yield it
    if not backfill:
        return
    full = os.environ.get("LR_GDELT_FULL") == "1"
    start = max(SINCE, TODAY - timedelta(days=84 if full else 28))
    step = 7 if full else 2
    d, fails = start, 0
    while d <= TODAY:
        e = min(d + timedelta(days=step), TODAY + timedelta(days=1))
        closed = e <= TODAY - timedelta(days=1)
        for lang in (GDELT_LANGS if full else [None]):
            q = f"{GDELT_Q} sourcelang:{lang}" if lang else GDELT_Q
            p = dict(base, query=q, startdatetime=d.strftime("%Y%m%d000000"), enddatetime=e.strftime("%Y%m%d000000"))
            try:
                body = _gdelt_get(p, 30 * 86400 if closed else 6 * 3600)
                fails = 0
            except SourceBlocked:
                fails += 1
                print(f"  ! gdelt window {d} {lang or 'all'} skipped (throttled)")
                if fails >= 3:
                    raise
                continue
            for it in _gdelt_items(body, GDELT_LANG_CODE.get(lang)):
                n += 1
                yield it
        print(f"  gdelt window {d}: {n} items so far")
        d = e


# ---------------------------------------------------------------- Japan: TDnet timely disclosures
# Listed companies must disclose voluntary-retirement programs (希望退職 / 早期退職), the standard way Japanese firms cut
# staff. TDnet keeps about 31 days of lists, so this source is recent-only; hourly runs keep it complete.
TDNET_KW = re.compile(r"希望退職|早期退職|人員削減|人員の削減|退職者の募集|退職者募集|転進支援|セカンドキャリア|ネクストキャリア|"
                      r"事業所の閉鎖|工場の閉鎖|工場閉鎖|拠点の閉鎖|生産拠点の再編")
TDNET_SKIP = re.compile(r"訂正|延期|中止|結果は未定|撤回")
JA_NUM = re.compile(r"([0-9０-９][0-9０-９,，]*)\s*(?:名|人)")


def _ja_num(s):
    s = s.translate(str.maketrans("０１２３４５６７８９，", "0123456789,")).replace(",", "")
    try:
        return int(s)
    except ValueError:
        return None


def _tdnet_pdf_numbers(pdf_url):
    """募集人員 (solicited) / 応募者数 (accepted) / 削減 (cut) counts from the disclosure PDF."""
    body = fetch(pdf_url, ttl=None, min_interval=1.0, max_bytes=3_000_000)
    if not body or not body.startswith(b"%PDF"):
        return None, ""
    try:
        txt = subprocess.run(["pdftotext", "-layout", "-l", "4", "-", "-"], input=body, capture_output=True, timeout=60).stdout
    except (OSError, subprocess.SubprocessError):
        return None, ""
    t = re.sub(r"\s+", " ", txt.decode("utf-8", "ignore"))
    for label in (r"応募(?:者)?数", r"応募(?:者)?は", r"募集人(?:員|数)", r"削減(?:人数|規模)?", r"対象人(?:員|数)"):
        if "対象" in label:
            break  # eligibility pool, not a cut
        m = re.search(label + r"[^0-9０-９]{0,25}" + JA_NUM.pattern, t)
        if m:
            v = _ja_num(m.group(1))
            if v and 3 <= v <= 200_000:
                return v, t[max(0, m.start() - 200): m.end() + 300]
    return None, t[:600]


def tdnet(days=None):
    backfill = _want_backfill("tdnet")
    days = days or (31 if backfill else 2)
    n = 0
    for k in range(days):
        day = TODAY - timedelta(days=k)
        if day < SINCE:
            break
        for page in range(1, 40):
            u = f"https://www.release.tdnet.info/inbs/I_list_{page:03d}_{day.strftime('%Y%m%d')}.html"
            body = fetch(u, ttl=(30 * 86400 if k > 1 else 1800), min_interval=1.0)
            if not body:
                break
            html = body.decode("utf-8", "ignore")
            rows = re.findall(r"(?s)<tr>(.*?)</tr>", html)
            got = 0
            for r in rows:
                title_m = re.search(r'kjTitle[^>]*>\s*<a href="([^"]+)"[^>]*>([^<]+)', r)
                if not title_m:
                    continue
                got += 1
                title = title_m.group(2).strip()
                if not TDNET_KW.search(title) or TDNET_SKIP.search(title):
                    continue
                name = unicodedata.normalize("NFKC", strip_html((re.search(r'kjName[^>]*>(.*?)</td>', r, re.S) or [None, ""])[1]))
                title = unicodedata.normalize("NFKC", title)
                code = strip_html((re.search(r'kjCode[^>]*>(.*?)</td>', r, re.S) or [None, ""])[1])
                tm = strip_html((re.search(r'kjTime[^>]*>(.*?)</td>', r, re.S) or [None, ""])[1])
                pdf = "https://www.release.tdnet.info/inbs/" + title_m.group(1)
                hc, snippet = _tdnet_pdf_numbers(pdf)
                kind = "closure" if re.search(r"閉鎖|再編", title) and not re.search(r"退職|人員", title) else "layoff"
                n += 1
                yield {"uid": f"tdnet:{title_m.group(1)}", "source": "tdnet", "tier": "official",
                       "publisher": "TDnet (Tokyo Stock Exchange disclosure)", "url": pdf,
                       "title": f"{name}: {title}", "text": snippet[:1500], "published": day.isoformat(),
                       "meta": {"company": name, "code": code, "headcount": hc, "country": "Japan", "lang": "ja",
                                "kind": kind, "time": tm, "program": "voluntary retirement" if "退職" in title else None}}
            if got < 100:
                break
    print(f"  tdnet {n} workforce disclosures")


# ---------------------------------------------------------------- India: NSE corporate announcements
NSE_KW = re.compile(r"(?i)\b(retrench\w*|voluntary retirement scheme|\bVRS\b|reduction (?:in|of) (?:the )?workforce|"
                    r"workforce (?:reduction|rationali[sz]ation)|closure of (?:the |its |our )?(?:plant|unit|factory|manufacturing|operations|facility))")


def nse():
    n, d = 0, SINCE
    hdr = {"Accept": "application/json", "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-announcements"}
    while d <= TODAY:
        e = min(d + timedelta(days=4), TODAY)
        u = ("https://www.nseindia.com/api/corporate-announcements?index=equities"
             f"&from_date={d.strftime('%d-%m-%Y')}&to_date={e.strftime('%d-%m-%Y')}")
        body = fetch(u, ttl=(30 * 86400 if e < TODAY - timedelta(days=2) else 3 * 3600), min_interval=2.0,
                     headers=hdr, max_bytes=20_000_000, timeout=60)
        try:
            rows = json.loads(body or b"[]")
        except json.JSONDecodeError:
            rows = []
        for r in rows if isinstance(rows, list) else []:
            txt = f"{r.get('desc') or ''}. {r.get('attchmntText') or ''}"
            if not NSE_KW.search(txt) or re.search(r"(?i)\blay-?off\b", txt) and not re.search(r"(?i)retrench|closure", txt):
                continue  # Indian "lay-off" (ID Act) is a temporary idling, not a job loss
            m = re.search(r"(?i)(\d{1,3}(?:,\d{3})+|\d+)\s+(?:\w+\s+){0,2}?(?:employees|workmen|workers|staff|persons)", txt)
            hc = int(m.group(1).replace(",", "")) if m else None
            pub = parse_date((r.get("an_dt") or "")[:11].replace("-", " ")) or d.isoformat()
            n += 1
            yield {"uid": f"nse:{r.get('seq_id') or r.get('attchmntFile')}", "source": "nse", "tier": "official",
                   "publisher": "NSE India (corporate announcement)", "url": r.get("attchmntFile") or "https://www.nseindia.com",
                   "title": f"{r.get('sm_name')}: {(r.get('attchmntText') or r.get('desc') or '')[:200]}", "text": txt[:1500],
                   "published": pub,
                   "meta": {"company": r.get("sm_name") or r.get("symbol"), "headcount": hc, "country": "India", "lang": "en",
                            "kind": "closure" if re.search(r"(?i)closure", txt) else "layoff",
                            "industry": None, "symbol": r.get("symbol")}}
        d = e + timedelta(days=1)
    print(f"  nse {n} workforce announcements")


# ---------------------------------------------------------------- Australia: ASX announcements (recent only)
ASX_KW = re.compile(r"(?i)redundanc|restructur\w* .{0,30}(?:workforce|roles|jobs|staff)|workforce reduction|job cuts|"
                    r"(?:closure|close) of .{0,30}(?:plant|mine|operations|facility|smelter|refinery)")


def _asx_names():
    body = fetch("https://www.asx.com.au/asx/research/ASXListedCompanies.csv", ttl=7 * 86400)
    out = {}
    for line in (body or b"").decode("utf-8", "ignore").splitlines()[3:]:
        m = re.match(r'"(.*?)","(\w+)"', line)
        if m:
            out[m.group(2)] = m.group(1).title().replace(" Limited", "").replace(" Ltd", "")
    return out


def asx():
    n = 0
    names = _asx_names()
    for page in range(0, 100):
        u = f"https://asx.api.markitdigital.com/asx-research/1.0/markets/announcements?itemsPerPage=100&page={page}"
        body = fetch(u, ttl=1800, min_interval=1.0)
        try:
            items = json.loads(body or b"{}").get("data", {}).get("items", [])
        except json.JSONDecodeError:
            items = []
        if not items:
            break
        for a in items:
            h = a.get("headline") or ""
            if not ASX_KW.search(h):
                continue
            sym = a.get("symbol") or ""
            n += 1
            yield {"uid": f"asx:{a.get('documentKey')}", "source": "asx", "tier": "official",
                   "publisher": "ASX (company announcement)",
                   "url": f"https://www.asx.com.au/markets/trade-our-cash-market/announcements.{sym.lower()}",
                   "title": f"{sym}: {h}", "text": "", "published": parse_date(a.get("date")),
                   "meta": {"company": names.get(sym), "symbol": sym, "headcount": None, "country": "Australia", "lang": "en",
                            "kind": "layoff", "headline_only": True}}
        last = parse_date(items[-1].get("date"))
        if last and last < (TODAY - timedelta(days=3 if not _want_backfill("asx") else 14)).isoformat():
            break
    print(f"  asx {n} matching headlines")
