"""Where layoffs happen (for the map) and how big companies are (for "% of staff").

HQ: curated headquarters city for well-known companies (news rarely names a site).
WORKFORCE: curated total employees from the company's latest annual report before 2026.
  Approximate by nature. Shown as "≈ X% of staff" with the source and year, and only when the
  event has a stated headcount. If a company is missing here, no percentage is computed.
Coordinates come from the GeoNames gazetteer (cities over 5,000 people, CC-BY, downloaded once into data/geonames/).
OpenStreetMap Nominatim is a capped fallback for misses. All results are cached in the DB.
"""
import io
import json
import urllib.parse
import zipfile
from collections import defaultdict

from .util import BROWSER_UA, DATA, fetch

US_STATES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA", "colorado": "CO",
    "connecticut": "CT", "delaware": "DE", "district of columbia": "DC", "florida": "FL", "georgia": "GA", "hawaii": "HI",
    "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS", "kentucky": "KY", "louisiana": "LA",
    "maine": "ME", "maryland": "MD", "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ",
    "new mexico": "NM", "new york": "NY", "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC", "south dakota": "SD",
    "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
}
COUNTRY_ALIAS = {"usa": "US", "us": "US", "united states": "US", "uk": "GB", "united kingdom": "GB", "south korea": "KR",
                 "russia": "RU", "czech republic": "CZ", "uae": "AE"}
_G = {}
NOMINATIM_BUDGET = [25]  # per process; keeps hourly runs fast

HQ = {
    "amazon": "Seattle, Washington, USA", "google": "Mountain View, California, USA", "microsoft": "Redmond, Washington, USA",
    "meta": "Menlo Park, California, USA", "apple": "Cupertino, California, USA", "netflix": "Los Gatos, California, USA",
    "oracle": "Austin, Texas, USA", "intel": "Santa Clara, California, USA", "ibm": "Armonk, New York, USA",
    "salesforce": "San Francisco, California, USA", "cisco": "San Jose, California, USA", "qualcomm": "San Diego, California, USA",
    "dell": "Round Rock, Texas, USA", "hp": "Palo Alto, California, USA", "hubspot": "Cambridge, Massachusetts, USA",
    "workday": "Pleasanton, California, USA", "ebay": "San Jose, California, USA", "paypal": "San Jose, California, USA",
    "tiktok": "Singapore", "bytedance": "Beijing, China", "tesla": "Austin, Texas, USA", "ford": "Dearborn, Michigan, USA",
    "general-motors": "Detroit, Michigan, USA", "stellantis": "Amsterdam, Netherlands", "volkswagen": "Wolfsburg, Germany",
    "bosch": "Gerlingen, Germany", "siemens": "Munich, Germany", "nissan": "Yokohama, Japan", "pfizer": "New York, New York, USA",
    "merck": "Rahway, New Jersey, USA", "novo-nordisk": "Bagsværd, Denmark", "bayer": "Leverkusen, Germany",
    "disney": "Burbank, California, USA", "warner-bros-discovery": "New York, New York, USA", "paramount": "New York, New York, USA",
    "starbucks": "Seattle, Washington, USA", "walmart": "Bentonville, Arkansas, USA", "target": "Minneapolis, Minnesota, USA",
    "nike": "Beaverton, Oregon, USA", "ups": "Atlanta, Georgia, USA", "fedex": "Memphis, Tennessee, USA",
    "boeing": "Arlington, Virginia, USA", "accenture": "Dublin, Ireland", "tcs": "Mumbai, India", "infosys": "Bengaluru, India",
    "wipro": "Bengaluru, India", "citigroup": "New York, New York, USA", "goldman-sachs": "New York, New York, USA",
    "jpmorgan": "New York, New York, USA", "wells-fargo": "San Francisco, California, USA", "hsbc": "London, United Kingdom",
    "pepsico": "Purchase, New York, USA", "procter-gamble": "Cincinnati, Ohio, USA", "nestle": "Vevey, Switzerland",
    "unilever": "London, United Kingdom", "uber": "San Francisco, California, USA", "lyft": "San Francisco, California, USA",
    "spotify": "Stockholm, Sweden", "ericsson": "Stockholm, Sweden", "nokia": "Espoo, Finland", "verizon": "New York, New York, USA",
    "at-t": "Dallas, Texas, USA", "x": "Bastrop, Texas, USA", "openai": "San Francisco, California, USA",
    "snap": "Santa Monica, California, USA", "block": "Oakland, California, USA", "rivian": "Irvine, California, USA",
    "nvidia": "Santa Clara, California, USA", "amd": "Santa Clara, California, USA", "samsung": "Suwon, South Korea",
    "sony": "Tokyo, Japan", "mass-general-brigham": "Boston, Massachusetts, USA", "kaiser-permanente": "Oakland, California, USA",
    "unitedhealth": "Minnetonka, Minnesota, USA", "ea": "Redwood City, California, USA",
    "universal-music-group": "Hilversum, Netherlands", "comcast": "Philadelphia, Pennsylvania, USA",
    "barclays": "London, United Kingdom", "american-express": "New York, New York, USA",
    "servicenow": "Santa Clara, California, USA", "kroger": "Cincinnati, Ohio, USA", "byd": "Shenzhen, China",
    "bmw": "Munich, Germany", "mercedes-benz": "Stuttgart, Germany", "porsche": "Stuttgart, Germany", "audi": "Ingolstadt, Germany",
    "heineken": "Amsterdam, Netherlands", "standard-chartered": "London, United Kingdom", "cognizant": "Teaneck, New Jersey, USA",
    "british-american-tobacco": "London, United Kingdom", "bt": "London, United Kingdom", "chevron": "Houston, Texas, USA",
    "exxonmobil": "Spring, Texas, USA", "bp": "London, United Kingdom", "shell": "London, United Kingdom",
    "dow": "Midland, Michigan, USA", "db-cargo": "Mainz, Germany", "icici-bank": "Mumbai, India",
    "morrisons": "Bradford, United Kingdom", "lufthansa": "Cologne, Germany", "commerzbank": "Frankfurt, Germany",
    "deutsche-bank": "Frankfurt, Germany", "ubs": "Zurich, Switzerland", "thyssenkrupp": "Essen, Germany",
    "continental": "Hanover, Germany", "zf": "Friedrichshafen, Germany", "honda": "Tokyo, Japan", "toyota": "Toyota City, Japan",
    "panasonic": "Kadoma, Osaka, Japan", "hcltech": "Noida, India", "tech-mahindra": "Pune, India", "capgemini": "Paris, France",
    "pwc": "London, United Kingdom", "deloitte": "London, United Kingdom", "kpmg": "Amstelveen, Netherlands",
    "ey": "London, United Kingdom", "mckinsey": "New York, New York, USA", "us-steel": "Pittsburgh, Pennsylvania, USA",
    "jaguar-land-rover": "Coventry, United Kingdom", "renault": "Boulogne-Billancourt, France", "volvo-cars": "Gothenburg, Sweden",
    "amdocs": "Chesterfield, Missouri, USA", "morgan-stanley": "New York, New York, USA", "royal-mail": "London, United Kingdom",
    "nab": "Melbourne, Australia", "cba": "Sydney, Australia", "aumovio": "Frankfurt, Germany", "intuit": "Mountain View, California, USA",
    "visa": "San Francisco, California, USA", "mastercard": "Purchase, New York, USA", "bank-of-america": "Charlotte, North Carolina, USA",
    "blackrock": "New York, New York, USA", "chegg": "Santa Clara, California, USA", "autodesk": "San Francisco, California, USA",
    "adobe": "San Jose, California, USA", "pinterest": "San Francisco, California, USA", "zoom": "San Jose, California, USA",
    "crowdstrike": "Austin, Texas, USA", "micron": "Boise, Idaho, USA", "applied-materials": "Santa Clara, California, USA",
    "texas-instruments": "Dallas, Texas, USA", "sap": "Walldorf, Germany", "philips": "Amsterdam, Netherlands",
    "vodafone": "Newbury, United Kingdom", "telstra": "Melbourne, Australia", "air-canada": "Montreal, Canada",
    "southwest-airlines": "Dallas, Texas, USA", "electronic-arts": "Redwood City, California, USA",
    "warner-music-group": "New York, New York, USA", "skydance": "Santa Monica, California, USA",
    "headspace": "Santa Monica, California, USA", "automattic": "San Francisco, California, USA",
    "johnson-johnson": "New Brunswick, New Jersey, USA", "novartis": "Basel, Switzerland",
    "bristol-myers-squibb": "Princeton, New Jersey, USA", "cvs-health": "Woonsocket, Rhode Island, USA",
    "mcdonalds": "Chicago, Illinois, USA", "coinbase": "San Francisco, California, USA", "patreon": "San Francisco, California, USA",
    "ubisoft": "Saint-Mandé, France", "linkedin": "Sunnyvale, California, USA", "elementor": "Ramat Gan, Israel",
    "epic-games": "Cary, North Carolina, USA", "bbc": "London, United Kingdom", "wisetech": "Sydney, Australia",
    "washington-post": "Washington, District of Columbia, USA", "arsenal": "London, United Kingdom",
    "telegraph": "London, United Kingdom", "innodata": "Ridgefield Park, New Jersey, USA",
    "sucker-punch": "Bellevue, Washington, USA", "westpac": "Sydney, Australia", "asml": "Veldhoven, Netherlands",
    "atlassian": "Sydney, Australia", "cloudflare": "San Francisco, California, USA", "flock-safety": "Atlanta, Georgia, USA",
}

# slug -> (employees, fiscal year of the figure). Source: the company's annual report / 10-K for that year.
WORKFORCE = {
    "amazon": (1_556_000, 2024), "microsoft": (228_000, 2025), "meta": (74_067, 2024), "google": (183_323, 2024),
    "apple": (164_000, 2024), "netflix": (14_000, 2024), "oracle": (162_000, 2025), "intel": (108_900, 2024),
    "salesforce": (76_453, 2025), "cisco": (90_400, 2024), "qualcomm": (49_000, 2024), "dell": (108_000, 2025),
    "hp": (58_000, 2024), "ibm": (270_300, 2024), "workday": (20_400, 2025), "ebay": (11_500, 2024),
    "paypal": (24_400, 2024), "tesla": (125_665, 2024), "ford": (171_000, 2024), "ups": (490_000, 2024), "boeing": (172_000, 2024),
    "disney": (233_000, 2024), "starbucks": (361_000, 2024), "nike": (77_800, 2025), "uber": (31_100, 2024),
    "pfizer": (81_000, 2024), "citigroup": (229_000, 2024), "goldman-sachs": (46_500, 2024), "verizon": (99_600, 2024),
    "at-t": (141_000, 2024), "nvidia": (36_000, 2025), "volkswagen": (679_000, 2024), "bmw": (159_000, 2024),
    "nokia": (78_000, 2024), "ericsson": (94_000, 2024), "accenture": (774_000, 2024), "tcs": (607_000, 2025),
    "infosys": (317_240, 2024), "wipro": (233_000, 2025), "cognizant": (336_800, 2024), "intuit": (18_800, 2024),
    "visa": (31_600, 2024), "american-express": (75_100, 2024), "morgan-stanley": (80_000, 2024), "kroger": (409_000, 2024),
    "autodesk": (15_300, 2025), "spotify": (7_300, 2024), "snap": (4_911, 2024), "coinbase": (3_772, 2024),
    "ea": (14_500, 2025), "comcast": (182_000, 2024), "hsbc": (211_000, 2024), "barclays": (90_000, 2024),
    "cloudflare": (4_263, 2024), "adobe": (30_709, 2024),
}


def _load():
    if _G:
        return _G
    gdir = DATA / "geonames"
    gdir.mkdir(parents=True, exist_ok=True)
    for name in ("cities5000.zip", "countryInfo.txt"):
        if not (gdir / name).exists():
            body = fetch(f"https://download.geonames.org/export/dump/{name}", ttl=None, max_bytes=50_000_000, timeout=120)
            if body:
                (gdir / name).write_bytes(body)
    city, city_cc, admin = {}, {}, defaultdict(list)
    try:
        with zipfile.ZipFile(gdir / "cities5000.zip") as z:
            for line in io.TextIOWrapper(z.open("cities5000.txt"), encoding="utf-8"):
                f = line.rstrip("\n").split("\t")
                lat, lon, cc, a1, pop = float(f[4]), float(f[5]), f[8], f[10], int(f[14] or 0)
                for nm in {f[1].lower(), f[2].lower()}:
                    k = (nm, cc, a1)
                    if k not in city or city[k][2] < pop:
                        city[k] = (lat, lon, pop)
                    k2 = (nm, cc)
                    if k2 not in city_cc or city_cc[k2][2] < pop:
                        city_cc[k2] = (lat, lon, pop)
                admin[(cc, a1)].append((lat, lon))
    except (OSError, zipfile.BadZipFile):
        pass
    names, capital = dict(COUNTRY_ALIAS), {}
    try:
        for line in (gdir / "countryInfo.txt").read_text(encoding="utf-8").splitlines():
            if line.startswith("#"):
                continue
            f = line.split("\t")
            names[f[4].lower()] = f[0]
            capital[f[0]] = f[5].lower()
    except OSError:
        pass
    _G.update(city=city, city_cc=city_cc, admin=admin, names=names, capital=capital)
    return _G


def offline(place):
    """GeoNames lookup for 'City, ST, USA', 'City, Country', 'ST, USA' or 'Country'."""
    g = _load()
    if not g.get("city"):
        return None
    parts = [p.strip() for p in place.split(",") if p.strip()]
    cc = g["names"].get(parts[-1].lower())
    if not cc:
        return None
    rest = parts[:-1]
    if cc == "US" and rest:
        st = rest[-1].upper() if len(rest[-1]) == 2 else US_STATES.get(rest[-1].lower())
        if st and len(rest) >= 2:
            words = rest[0].split()
            for n in (1, 2, 3):  # tolerate street prefixes: "4941 Allison Parkway Suite B Vacaville"
                hit = g["city"].get((" ".join(words[-n:]).lower(), "US", st))
                if hit:
                    return hit[:2]
        if st and g["admin"].get(("US", st)):
            pts = g["admin"][("US", st)]
            return (round(sum(p[0] for p in pts) / len(pts), 3), round(sum(p[1] for p in pts) / len(pts), 3))
        if not st:
            hit = g["city_cc"].get((rest[0].lower(), "US"))
            return hit[:2] if hit else None
        return None
    if rest:
        hit = g["city_cc"].get((rest[0].lower(), cc))
        if hit:
            return hit[:2]
    cap = g["capital"].get(cc)
    hit = g["city_cc"].get((cap, cc)) if cap else None
    return hit[:2] if hit else None


def geocode(con, place):
    """(lat, lon) for a free-text place: DB cache, then GeoNames, then a capped number of Nominatim calls."""
    if not place:
        return None
    row = con.execute("SELECT lat, lon FROM geo WHERE place = ?", (place,)).fetchone()
    if row and row[0] is not None:
        return (row[0], row[1])
    hit = offline(place)
    if hit:
        con.execute("INSERT OR REPLACE INTO geo(place, lat, lon) VALUES(?,?,?)", (place, *hit))
        con.commit()
        return hit
    if row or NOMINATIM_BUDGET[0] <= 0:
        return None
    NOMINATIM_BUDGET[0] -= 1
    url = "https://nominatim.openstreetmap.org/search?format=json&limit=1&q=" + urllib.parse.quote(place)
    body = fetch(url, ttl=None, ua=BROWSER_UA, min_interval=1.1)
    hit = None
    try:
        res = json.loads(body or b"[]")
        if res:
            hit = (round(float(res[0]["lat"]), 3), round(float(res[0]["lon"]), 3))
    except (ValueError, KeyError):
        pass
    con.execute("INSERT OR REPLACE INTO geo(place, lat, lon) VALUES(?,?,?)", (place, *(hit or (None, None))))
    con.commit()
    return hit
