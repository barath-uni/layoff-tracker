"""Shared helpers: paths, HTTP with on-disk cache, text and date utilities."""
import hashlib
import html
import os
import re
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CACHE = Path(os.environ["LR_CACHE"]) if os.environ.get("LR_CACHE") else DATA / "cache"  # LR_CACHE: cold-run measurements
DIST = ROOT / "dist"
SITE = ROOT / "site"
ASSETS = ROOT / "assets"

# Today can be pinned for reproducible builds (LR_TODAY=2026-10-27).
TODAY = date.fromisoformat(os.environ["LR_TODAY"]) if os.environ.get("LR_TODAY") else date.today()
YEAR_START = date(TODAY.year, 1, 1)
# How far back fetchers look (LR_SINCE=2025-01-01 for a two-year backfill). The site still reports YEAR_START onward.
SINCE = date.fromisoformat(os.environ["LR_SINCE"]) if os.environ.get("LR_SINCE") else YEAR_START

BROWSER_UA = "Mozilla/5.0 (X11; Linux x86_64) layoff-radar/0.1 (+public layoff tracker)"
# SEC asks for a descriptive UA with a contact. Set LR_CONTACT to your address.
SEC_UA = f"layoff-radar research {os.environ.get('LR_CONTACT', 'contact@layoffradar.invalid')}"

_last_hit = {}
# Network counters for the scale measurements (reset per source by the CLI).
NET = {"requests": 0, "bytes": 0, "cache_hits": 0, "errors": 0}


def mem_available_mb():
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) // 1024
    except OSError:
        pass
    return 10_000


def mem_guard(min_mb=1500, max_wait=600):
    """Pause while the machine is short on memory (8 GB box that has frozen before). Returns MB available."""
    waited, step = 0, 5
    avail = mem_available_mb()
    while avail < min_mb and waited < max_wait:
        print(f"  .. low memory ({avail} MB available), pausing {step}s")
        import gc
        gc.collect()
        time.sleep(step)
        waited += step
        step = min(step * 2, 60)
        avail = mem_available_mb()
    return avail


def peak_rss_mb():
    import resource
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024


def fetch(url, ttl=6 * 3600, ua=BROWSER_UA, min_interval=1.0, max_bytes=4_000_000, timeout=30, headers=None, data=None,
          cache_key=None, retries=2):
    """GET (or POST with data) a URL with a polite per-host delay and a disk cache. Returns bytes or None.
    429/503 answers back off and retry; the cached copy (if any) is the fallback."""
    CACHE.mkdir(parents=True, exist_ok=True)
    key = CACHE / hashlib.sha1(cache_key.encode() if cache_key else url.encode() + (data or b"")).hexdigest()
    if key.exists() and (ttl is None or time.time() - key.stat().st_mtime < ttl):
        NET["cache_hits"] += 1
        return key.read_bytes()
    host = url.split("/")[2]
    hdrs = {"User-Agent": ua, "Accept-Encoding": "identity"}
    hdrs.update(headers or {})
    for attempt in range(retries + 1):
        wait = min_interval - (time.time() - _last_hit.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        _last_hit[host] = time.time()
        req = urllib.request.Request(url, headers=hdrs, data=data)
        NET["requests"] += 1
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read(max_bytes)
            NET["bytes"] += len(body)
            break
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and attempt < retries:
                print(f"  .. {e.code} from {host}, backing off {30 * (attempt + 1)}s")
                time.sleep(30 * (attempt + 1))
                continue
            NET["errors"] += 1
            print(f"  ! fetch failed {url[:90]}: {e}")
            return key.read_bytes() if key.exists() else None
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            NET["errors"] += 1
            print(f"  ! fetch failed {url[:90]}: {e}")
            return key.read_bytes() if key.exists() else None
    key.write_bytes(body)
    return body


def slugify(s):
    """ASCII slug for Latin-script names ('Telefónica' -> 'telefonica'); names in other scripts keep their letters
    ('コーセーHD' -> 'コーセーhd', 'Газпром' -> 'газпром') instead of collapsing to 'hd' or 'unknown'."""
    s = unicodedata.normalize("NFKC", s or "")
    a = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    a = re.sub(r"[^a-zA-Z0-9]+", "-", a.lower()).strip("-")
    letters = sum(1 for ch in s if ch.isalnum())
    if letters and sum(1 for ch in a if ch.isalnum()) < 0.6 * letters:
        a = re.sub(r"[\W_]+", "-", s.lower()).strip("-")
    return a[:60] or "unknown"


def strip_html(s):
    s = re.sub(r"(?is)<(script|style).*?</\1>", " ", s or "")
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = html.unescape(html.unescape(s))
    return re.sub(r"\s+", " ", s).strip()


def parse_date(s):
    """Best-effort: RFC 822, ISO, US m/d/Y, Excel serial. Returns ISO date string or None."""
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None
    if re.fullmatch(r"\d{5}(\.\d+)?", s):  # Excel serial
        return date.fromordinal(date(1899, 12, 30).toordinal() + int(float(s))).isoformat()
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", s)
    if m:
        mo, d, y = map(int, m.groups())
        y = y + 2000 if y < 100 else y
        try:
            return date(y, mo, d).isoformat()
        except ValueError:
            return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        pass
    try:
        return parsedate_to_datetime(s).astimezone(timezone.utc).date().isoformat()
    except (TypeError, ValueError):
        return None


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def days_between(a, b):
    return abs((date.fromisoformat(a) - date.fromisoformat(b)).days)
