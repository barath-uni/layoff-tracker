"""Single place for branding, deploy settings and the source registry."""
import os

BRAND = os.environ.get("LR_BRAND", "Layoff Tracker")
SITE_URL = os.environ.get("SITE_URL", "http://localhost:8000").rstrip("/")

# Source registry: name -> "module:adapter". One adapter (a generator or list of items) per source; `radar fetch`
# runs them in this order. Comment a line out to disable a source.
SOURCES = {
    "gnews": "sources:google_news",          # Google News, English editions
    "gnews_intl": "sources_intl:gnews_intl",  # Google News, country editions x local-language keywords (GNEWS_EDITIONS)
    "edgar": "sources:edgar",                 # SEC 8-K Item 2.05
    "warn_ca": "sources:warn_ca", "warn_md": "sources:warn_md",
    "warn_tx": "warn_more:warn_tx", "warn_pa": "warn_more:warn_pa", "warn_co": "warn_more:warn_co", "warn_wa": "warn_more:warn_wa",
    "tdnet": "sources_intl:tdnet",            # Japan timely disclosures
    "nse": "sources_intl:nse",                # India NSE announcements
    "asx": "sources_intl:asx",                # Australia ASX announcements
    "hn": "sources:hackernews",
    "reddit": "sources:reddit",
    # "gdelt": "sources_intl:gdelt",          # DISABLED: the GDELT DOC API rate-limits (429). Use the bulk files instead (ROADMAP).
}

# Google News country editions for the ~40 largest economies: (gl, hl, ceid, lang, country, backfill step in days).
# Busy editions get shorter steps: Google returns at most 100 results per query, so a long window drops stories.
# Local-language keywords per lang live in sources_intl.LANG_Q.
GNEWS_EDITIONS = [
    ("GB", "en-GB", "GB:en", "en", "United Kingdom", 7), ("IN", "en-IN", "IN:en", "en", "India", 7),
    ("CA", "en-CA", "CA:en", "en", "Canada", 14), ("AU", "en-AU", "AU:en", "en", "Australia", 14),
    ("SG", "en-SG", "SG:en", "en", "Singapore", 15), ("IE", "en-IE", "IE:en", "en", "Ireland", 15),
    ("ZA", "en-ZA", "ZA:en", "en", "South Africa", 15), ("NG", "en-NG", "NG:en", "en", "Nigeria", 15),
    ("PH", "en-PH", "PH:en", "en", "Philippines", 15), ("MY", "en-MY", "MY:en", "en", "Malaysia", 15),
    ("IL", "en-IL", "IL:en", "en", "Israel", 15),
    ("DE", "de", "DE:de", "de", "Germany", 7), ("AT", "de-AT", "AT:de", "de", "Austria", 15),
    ("CH", "de-CH", "CH:de", "de", "Switzerland", 15), ("FR", "fr", "FR:fr", "fr", "France", 7),
    ("BE", "nl-BE", "BE:nl", "nl", "Belgium", 15), ("NL", "nl", "NL:nl", "nl", "Netherlands", 15),
    ("IT", "it", "IT:it", "it", "Italy", 7), ("ES", "es", "ES:es", "es", "Spain", 7),
    ("MX", "es-419", "MX:es-419", "es", "Mexico", 15), ("AR", "es-419", "AR:es-419", "es", "Argentina", 15),
    ("CO", "es-419", "CO:es-419", "es", "Colombia", 30), ("CL", "es-419", "CL:es-419", "es", "Chile", 30),
    ("BR", "pt-BR", "BR:pt-419", "pt", "Brazil", 7), ("PL", "pl", "PL:pl", "pl", "Poland", 15),
    ("SE", "sv", "SE:sv", "sv", "Sweden", 15), ("NO", "no", "NO:no", "no", "Norway", 30),
    ("DK", "da", "DK:da", "da", "Denmark", 30), ("TR", "tr", "TR:tr", "tr", "Turkey", 15),
    ("RU", "ru", "RU:ru", "ru", "Russia", 15), ("JP", "ja", "JP:ja", "ja", "Japan", 7),
    ("KR", "ko", "KR:ko", "ko", "South Korea", 7), ("CN", "zh-CN", "CN:zh-Hans", "zh", "China", 7),
    ("TW", "zh-TW", "TW:zh-Hant", "zh", "Taiwan", 15), ("HK", "zh-HK", "HK:zh-Hant", "zh", "Hong Kong", 15),
    ("IN", "hi", "IN:hi", "hi", "India", 15), ("BD", "bn", "BD:bn", "bn", "Bangladesh", 30),
    ("ID", "id", "ID:id", "id", "Indonesia", 7), ("TH", "th", "TH:th", "th", "Thailand", 30),
    ("VN", "vi", "VN:vi", "vi", "Vietnam", 30), ("SA", "ar", "SA:ar", "ar", "Saudi Arabia", 30),
    ("EG", "ar", "EG:ar", "ar", "Egypt", 30), ("AE", "ar", "AE:ar", "ar", "United Arab Emirates", 30),
]
