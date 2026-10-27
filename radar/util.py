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
CACHE = DATA / "cache"
DIST = ROOT / "dist"
SITE = ROOT / "site"
ASSETS = ROOT / "assets"

# Today can be pinned for reproducible builds (LR_TODAY=2026-10-27).
TODAY = date.fromisoformat(os.environ["LR_TODAY"]) if os.environ.get("LR_TODAY") else date.today()
YEAR_START = date(TODAY.year, 1, 1)

BROWSER_UA = "Mozilla/5.0 (X11; Linux x86_64) layoff-radar/0.1 (+public layoff tracker)"
# SEC asks for a descriptive UA with a contact. Set LR_CONTACT to your address.
SEC_UA = f"layoff-radar research {os.environ.get('LR_CONTACT', 'contact@layoffradar.invalid')}"

_last_hit = {}


def fetch(url, ttl=6 * 3600, ua=BROWSER_UA, min_interval=1.0, max_bytes=4_000_000, timeout=30):
    """GET a URL with a polite per-host delay and a disk cache. Returns bytes or None."""
    CACHE.mkdir(parents=True, exist_ok=True)
    key = CACHE / hashlib.sha1(url.encode()).hexdigest()
    if key.exists() and (ttl is None or time.time() - key.stat().st_mtime < ttl):
        return key.read_bytes()
    host = url.split("/")[2]
    wait = min_interval - (time.time() - _last_hit.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    _last_hit[host] = time.time()
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept-Encoding": "identity"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read(max_bytes)
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        print(f"  ! fetch failed {url[:90]}: {e}")
        return key.read_bytes() if key.exists() else None
    key.write_bytes(body)
    return body


def slugify(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s.lower()).strip("-")
    return s[:60] or "unknown"


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
