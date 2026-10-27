"""Reference tables: source tiers, industry mapping, known companies, country cues."""
import re

TIER_WEIGHT = {"official": 1.0, "major": 0.7, "news": 0.45, "aggregator": 0.25, "social": 0.15}
TIER_LABEL = {"official": "Official filing", "major": "Major outlet", "news": "News",
              "aggregator": "Hacker News", "social": "Social"}

MAJOR_OUTLETS = {
    "reuters", "bloomberg", "cnbc", "the wall street journal", "wsj", "the new york times", "new york times",
    "financial times", "ft", "associated press", "ap news", "bbc", "bbc news", "the guardian", "the washington post",
    "washington post", "los angeles times", "cnn", "npr", "axios", "techcrunch", "the verge", "wired", "the information",
    "business insider", "fortune", "forbes", "variety", "the hollywood reporter", "deadline", "politico", "abc news",
    "cbs news", "nbc news", "fox business", "yahoo finance", "marketwatch", "barron's", "the economist", "nikkei asia",
    "the times of india", "economic times", "the economic times", "mint", "livemint", "hindustan times", "the hindu",
    "moneycontrol", "handelsblatt", "le monde", "der spiegel", "south china morning post", "the globe and mail",
    "cbc", "cbc news", "abc (australia)", "sydney morning herald", "the australian financial review", "geekwire",
    "fierce pharma", "fierce healthcare", "fierce biotech", "endpoints news", "stat", "ars technica", "engadget",
    "fast company", "semafor", "the register", "sky news", "the telegraph", "the independent", "usa today",
    "ctech", "calcalist", "the times", "evening standard", "pbs", "time", "newsweek", "quartz", "vox", "techradar",
}

DOMAIN_PUBLISHER = {
    "reuters.com": "Reuters", "bloomberg.com": "Bloomberg", "cnbc.com": "CNBC", "wsj.com": "WSJ",
    "nytimes.com": "The New York Times", "ft.com": "Financial Times", "apnews.com": "AP News", "bbc.com": "BBC",
    "bbc.co.uk": "BBC", "theguardian.com": "The Guardian", "washingtonpost.com": "The Washington Post",
    "techcrunch.com": "TechCrunch", "theverge.com": "The Verge", "wired.com": "Wired", "businessinsider.com": "Business Insider",
    "fortune.com": "Fortune", "forbes.com": "Forbes", "axios.com": "Axios", "geekwire.com": "GeekWire",
    "arstechnica.com": "Ars Technica", "theinformation.com": "The Information", "theregister.com": "The Register",
    "sfgate.com": "SFGate", "latimes.com": "Los Angeles Times", "variety.com": "Variety", "cnn.com": "CNN",
}

INDUSTRIES = [
    "Technology", "Media & Entertainment", "Telecom", "Finance", "Healthcare", "Pharma & Biotech",
    "Retail & Consumer", "Food & Hospitality", "Manufacturing", "Automotive", "Energy & Utilities",
    "Transportation & Logistics", "Construction & Real Estate", "Professional Services", "Education",
    "Government & Nonprofit", "Agriculture", "Other",
]


def industry_from_sic(sic):
    try:
        s = int(sic)
    except (TypeError, ValueError):
        return None
    if 100 <= s < 1000: return "Agriculture"
    if 1000 <= s < 1500 or 2900 <= s < 3000: return "Energy & Utilities"
    if 1500 <= s < 1800: return "Construction & Real Estate"
    if 2000 <= s < 2100: return "Retail & Consumer"
    if 2830 <= s <= 2836: return "Pharma & Biotech"
    if 3570 <= s <= 3579 or 3660 <= s <= 3679: return "Technology"
    if 3710 <= s <= 3716: return "Automotive"
    if 3840 <= s <= 3851: return "Healthcare"
    if 2000 <= s < 4000: return "Manufacturing"
    if 4000 <= s < 4800: return "Transportation & Logistics"
    if s in (4833, 4841): return "Media & Entertainment"
    if 4800 <= s < 4900: return "Telecom"
    if 4900 <= s < 5000: return "Energy & Utilities"
    if s == 5812: return "Food & Hospitality"
    if 5000 <= s < 6000: return "Retail & Consumer"
    if 6500 <= s < 6600: return "Construction & Real Estate"
    if 6000 <= s < 6800: return "Finance"
    if 7370 <= s <= 7379: return "Technology"
    if 7000 <= s < 7100: return "Food & Hospitality"
    if 7800 <= s < 8000: return "Media & Entertainment"
    if 8000 <= s < 8100: return "Healthcare"
    if 8200 <= s < 8300: return "Education"
    if 7000 <= s < 9000: return "Professional Services"
    return None


def industry_from_naics(code):
    c = re.sub(r"\D", "", str(code or ""))
    if not c:
        return None
    if c.startswith("334") or c.startswith("5415") or c.startswith("518") or c.startswith("5112") or c.startswith("5132") or c.startswith("519"):
        return "Technology"
    if c.startswith("3254"): return "Pharma & Biotech"
    if c[:4] in ("3361", "3362", "3363"): return "Automotive"
    if c.startswith("517"): return "Telecom"
    two = c[:2]
    return {
        "11": "Agriculture", "21": "Energy & Utilities", "22": "Energy & Utilities", "23": "Construction & Real Estate",
        "31": "Manufacturing", "32": "Manufacturing", "33": "Manufacturing", "42": "Retail & Consumer",
        "44": "Retail & Consumer", "45": "Retail & Consumer", "48": "Transportation & Logistics",
        "49": "Transportation & Logistics", "51": "Media & Entertainment", "52": "Finance",
        "53": "Construction & Real Estate", "54": "Professional Services", "55": "Professional Services",
        "56": "Professional Services", "61": "Education", "62": "Healthcare", "71": "Media & Entertainment",
        "72": "Food & Hospitality", "81": "Professional Services", "92": "Government & Nonprofit", "99": "Other",
    }.get(two)


INDUSTRY_HINTS = [
    (r"\b(hospital|health ?system|clinic|medical center|healthcare|health care|nurses?)\b", "Healthcare"),
    (r"\b(pharma\w*|biotech\w*|drugmaker|vaccine|therapeutics|biosciences)\b", "Pharma & Biotech"),
    (r"\b(bank|banks|lender|mortgage|insurer|insurance|fintech|asset manager|brokerage|credit union)\b", "Finance"),
    (r"\b(university|college|school district|schools?)\b", "Education"),
    (r"\b(newsroom|newspaper|studio|streaming|media|magazine|broadcaster|publisher|game studio|video game|gaming)\b", "Media & Entertainment"),
    (r"\b(airline|trucking|logistics|railroad|rail|shipping|freight|delivery)\b", "Transportation & Logistics"),
    (r"\b(automaker|carmaker|auto ?parts|EV maker|electric vehicle|truck factory)\b", "Automotive"),
    (r"\b(retailer|store closures?|stores|supermarket|grocer|apparel|e-commerce)\b", "Retail & Consumer"),
    (r"\b(restaurant|hotel|casino|resort)\b", "Food & Hospitality"),
    (r"\b(software|tech|startup|semiconductor|chipmaker|chip|cloud|SaaS|cybersecurity|robotics)\b", "Technology"),
    (r"\b(federal|agency|department of|county|city of|state of|government|nonprofit|ministry)\b", "Government & Nonprofit"),
    (r"\b(oil|gas|energy|solar|utility|utilities|mining|coal)\b", "Energy & Utilities"),
    (r"\b(factory|plant|mill|manufactur\w+|steel|foundry)\b", "Manufacturing"),
    (r"\b(telecom|wireless|carrier)\b", "Telecom"),
]

# Known companies: canonical slug -> (display name, industry, country, email domains)
KNOWN = {
    "amazon": ("Amazon", "Technology", "United States", ["amazon.com"]),
    "google": ("Google", "Technology", "United States", ["google.com"]),
    "microsoft": ("Microsoft", "Technology", "United States", ["microsoft.com"]),
    "meta": ("Meta", "Technology", "United States", ["meta.com", "fb.com"]),
    "apple": ("Apple", "Technology", "United States", ["apple.com"]),
    "netflix": ("Netflix", "Media & Entertainment", "United States", ["netflix.com"]),
    "oracle": ("Oracle", "Technology", "United States", ["oracle.com"]),
    "intel": ("Intel", "Technology", "United States", ["intel.com"]),
    "ibm": ("IBM", "Technology", "United States", ["ibm.com"]),
    "salesforce": ("Salesforce", "Technology", "United States", ["salesforce.com"]),
    "cisco": ("Cisco", "Technology", "United States", ["cisco.com"]),
    "qualcomm": ("Qualcomm", "Technology", "United States", ["qualcomm.com"]),
    "dell": ("Dell", "Technology", "United States", ["dell.com"]),
    "hp": ("HP", "Technology", "United States", ["hp.com"]),
    "hubspot": ("HubSpot", "Technology", "United States", ["hubspot.com"]),
    "workday": ("Workday", "Technology", "United States", ["workday.com"]),
    "ebay": ("eBay", "Technology", "United States", ["ebay.com"]),
    "paypal": ("PayPal", "Finance", "United States", ["paypal.com"]),
    "tiktok": ("TikTok", "Technology", "China", ["tiktok.com", "bytedance.com"]),
    "bytedance": ("ByteDance", "Technology", "China", ["bytedance.com"]),
    "tesla": ("Tesla", "Automotive", "United States", ["tesla.com"]),
    "ford": ("Ford", "Automotive", "United States", ["ford.com"]),
    "general-motors": ("General Motors", "Automotive", "United States", ["gm.com"]),
    "stellantis": ("Stellantis", "Automotive", "Netherlands", ["stellantis.com"]),
    "volkswagen": ("Volkswagen", "Automotive", "Germany", ["volkswagen.de", "vw.com"]),
    "bosch": ("Bosch", "Manufacturing", "Germany", ["bosch.com"]),
    "siemens": ("Siemens", "Manufacturing", "Germany", ["siemens.com"]),
    "nissan": ("Nissan", "Automotive", "Japan", ["nissan.com"]),
    "pfizer": ("Pfizer", "Pharma & Biotech", "United States", ["pfizer.com"]),
    "merck": ("Merck", "Pharma & Biotech", "United States", ["merck.com"]),
    "novo-nordisk": ("Novo Nordisk", "Pharma & Biotech", "Denmark", ["novonordisk.com"]),
    "bayer": ("Bayer", "Pharma & Biotech", "Germany", ["bayer.com"]),
    "disney": ("Disney", "Media & Entertainment", "United States", ["disney.com"]),
    "warner-bros-discovery": ("Warner Bros. Discovery", "Media & Entertainment", "United States", ["wbd.com"]),
    "paramount": ("Paramount", "Media & Entertainment", "United States", ["paramount.com"]),
    "starbucks": ("Starbucks", "Food & Hospitality", "United States", ["starbucks.com"]),
    "walmart": ("Walmart", "Retail & Consumer", "United States", ["walmart.com"]),
    "target": ("Target", "Retail & Consumer", "United States", ["target.com"]),
    "nike": ("Nike", "Retail & Consumer", "United States", ["nike.com"]),
    "ups": ("UPS", "Transportation & Logistics", "United States", ["ups.com"]),
    "fedex": ("FedEx", "Transportation & Logistics", "United States", ["fedex.com"]),
    "boeing": ("Boeing", "Manufacturing", "United States", ["boeing.com"]),
    "accenture": ("Accenture", "Professional Services", "Ireland", ["accenture.com"]),
    "tcs": ("TCS", "Technology", "India", ["tcs.com"]),
    "infosys": ("Infosys", "Technology", "India", ["infosys.com"]),
    "wipro": ("Wipro", "Technology", "India", ["wipro.com"]),
    "citigroup": ("Citigroup", "Finance", "United States", ["citi.com"]),
    "goldman-sachs": ("Goldman Sachs", "Finance", "United States", ["gs.com"]),
    "jpmorgan": ("JPMorgan Chase", "Finance", "United States", ["jpmorgan.com", "jpmchase.com"]),
    "wells-fargo": ("Wells Fargo", "Finance", "United States", ["wellsfargo.com"]),
    "hsbc": ("HSBC", "Finance", "United Kingdom", ["hsbc.com"]),
    "pepsico": ("PepsiCo", "Retail & Consumer", "United States", ["pepsico.com"]),
    "procter-gamble": ("Procter & Gamble", "Retail & Consumer", "United States", ["pg.com"]),
    "nestle": ("Nestlé", "Retail & Consumer", "Switzerland", ["nestle.com"]),
    "unilever": ("Unilever", "Retail & Consumer", "United Kingdom", ["unilever.com"]),
    "uber": ("Uber", "Technology", "United States", ["uber.com"]),
    "lyft": ("Lyft", "Technology", "United States", ["lyft.com"]),
    "spotify": ("Spotify", "Media & Entertainment", "Sweden", ["spotify.com"]),
    "ericsson": ("Ericsson", "Telecom", "Sweden", ["ericsson.com"]),
    "nokia": ("Nokia", "Telecom", "Finland", ["nokia.com"]),
    "verizon": ("Verizon", "Telecom", "United States", ["verizon.com"]),
    "at-t": ("AT&T", "Telecom", "United States", ["att.com"]),
    "x": ("X", "Technology", "United States", ["x.com"]),
    "openai": ("OpenAI", "Technology", "United States", ["openai.com"]),
    "snap": ("Snap", "Technology", "United States", ["snap.com"]),
    "block": ("Block", "Finance", "United States", ["block.xyz", "squareup.com"]),
    "rivian": ("Rivian", "Automotive", "United States", ["rivian.com"]),
    "nvidia": ("Nvidia", "Technology", "United States", ["nvidia.com"]),
    "amd": ("AMD", "Technology", "United States", ["amd.com"]),
    "samsung": ("Samsung", "Technology", "South Korea", ["samsung.com"]),
    "sony": ("Sony", "Technology", "Japan", ["sony.com"]),
    "mass-general-brigham": ("Mass General Brigham", "Healthcare", "United States", ["mgb.org"]),
    "kaiser-permanente": ("Kaiser Permanente", "Healthcare", "United States", ["kp.org"]),
    "unitedhealth": ("UnitedHealth", "Healthcare", "United States", ["uhg.com"]),
    "ea": ("Electronic Arts", "Media & Entertainment", "United States", ["ea.com"]),
    "universal-music-group": ("Universal Music Group", "Media & Entertainment", "Netherlands", ["umusic.com"]),
    "comcast": ("Comcast", "Telecom", "United States", ["comcast.com"]),
    "barclays": ("Barclays", "Finance", "United Kingdom", ["barclays.com"]),
    "american-express": ("American Express", "Finance", "United States", ["aexp.com"]),
    "servicenow": ("ServiceNow", "Technology", "United States", ["servicenow.com"]),
    "kroger": ("Kroger", "Retail & Consumer", "United States", ["kroger.com"]),
    "byd": ("BYD", "Automotive", "China", []),
    "bmw": ("BMW", "Automotive", "Germany", []),
    "mercedes-benz": ("Mercedes-Benz", "Automotive", "Germany", []),
    "porsche": ("Porsche", "Automotive", "Germany", []),
    "audi": ("Audi", "Automotive", "Germany", []),
    "heineken": ("Heineken", "Retail & Consumer", "Netherlands", []),
    "standard-chartered": ("Standard Chartered", "Finance", "United Kingdom", []),
    "cognizant": ("Cognizant", "Technology", "United States", []),
    "british-american-tobacco": ("British American Tobacco", "Retail & Consumer", "United Kingdom", []),
    "bt": ("BT", "Telecom", "United Kingdom", []),
    "chevron": ("Chevron", "Energy & Utilities", "United States", []),
    "exxonmobil": ("ExxonMobil", "Energy & Utilities", "United States", []),
    "bp": ("BP", "Energy & Utilities", "United Kingdom", []),
    "shell": ("Shell", "Energy & Utilities", "United Kingdom", []),
    "dow": ("Dow", "Manufacturing", "United States", []),
    "db-cargo": ("DB Cargo", "Transportation & Logistics", "Germany", []),
    "icici-bank": ("ICICI Bank", "Finance", "India", []),
    "morrisons": ("Morrisons", "Retail & Consumer", "United Kingdom", []),
    "lufthansa": ("Lufthansa", "Transportation & Logistics", "Germany", []),
    "commerzbank": ("Commerzbank", "Finance", "Germany", []),
    "deutsche-bank": ("Deutsche Bank", "Finance", "Germany", []),
    "ubs": ("UBS", "Finance", "Switzerland", []),
    "thyssenkrupp": ("Thyssenkrupp", "Manufacturing", "Germany", []),
    "continental": ("Continental", "Automotive", "Germany", []),
    "zf": ("ZF", "Automotive", "Germany", []),
    "honda": ("Honda", "Automotive", "Japan", []),
    "toyota": ("Toyota", "Automotive", "Japan", []),
    "panasonic": ("Panasonic", "Technology", "Japan", []),
    "hcltech": ("HCLTech", "Technology", "India", []),
    "tech-mahindra": ("Tech Mahindra", "Technology", "India", []),
    "capgemini": ("Capgemini", "Professional Services", "France", []),
    "pwc": ("PwC", "Professional Services", "United Kingdom", []),
    "deloitte": ("Deloitte", "Professional Services", "United Kingdom", []),
    "kpmg": ("KPMG", "Professional Services", "Netherlands", []),
    "ey": ("EY", "Professional Services", "United Kingdom", []),
    "mckinsey": ("McKinsey", "Professional Services", "United States", []),
    "us-steel": ("U.S. Steel", "Manufacturing", "United States", []),
    "jaguar-land-rover": ("Jaguar Land Rover", "Automotive", "United Kingdom", []),
    "renault": ("Renault", "Automotive", "France", []),
    "volvo-cars": ("Volvo Cars", "Automotive", "Sweden", []),
    "amdocs": ("Amdocs", "Technology", "United States", []),
    "morgan-stanley": ("Morgan Stanley", "Finance", "United States", []),
    "royal-mail": ("Royal Mail", "Transportation & Logistics", "United Kingdom", []),
    "nab": ("NAB", "Finance", "Australia", []),
    "cba": ("Commonwealth Bank", "Finance", "Australia", []),
    "aumovio": ("Aumovio", "Automotive", "Germany", []),
    "intuit": ("Intuit", "Technology", "United States", []),
    "visa": ("Visa", "Finance", "United States", []),
    "mastercard": ("Mastercard", "Finance", "United States", []),
    "bank-of-america": ("Bank of America", "Finance", "United States", []),
    "citigroup": ("Citigroup", "Finance", "United States", []),
    "blackrock": ("BlackRock", "Finance", "United States", []),
    "chegg": ("Chegg", "Education", "United States", []),
    "autodesk": ("Autodesk", "Technology", "United States", []),
    "adobe": ("Adobe", "Technology", "United States", []),
    "pinterest": ("Pinterest", "Technology", "United States", []),
    "zoom": ("Zoom", "Technology", "United States", []),
    "crowdstrike": ("CrowdStrike", "Technology", "United States", []),
    "micron": ("Micron", "Technology", "United States", []),
    "applied-materials": ("Applied Materials", "Technology", "United States", []),
    "texas-instruments": ("Texas Instruments", "Technology", "United States", []),
    "sap": ("SAP", "Technology", "Germany", []),
    "philips": ("Philips", "Healthcare", "Netherlands", []),
    "ericsson": ("Ericsson", "Telecom", "Sweden", []),
    "vodafone": ("Vodafone", "Telecom", "United Kingdom", []),
    "telstra": ("Telstra", "Telecom", "Australia", []),
    "air-canada": ("Air Canada", "Transportation & Logistics", "Canada", []),
    "southwest-airlines": ("Southwest Airlines", "Transportation & Logistics", "United States", []),
    "electronic-arts": ("Electronic Arts", "Media & Entertainment", "United States", []),
    "warner-music-group": ("Warner Music Group", "Media & Entertainment", "United States", []),
    "skydance": ("Skydance", "Media & Entertainment", "United States", []),
    "headspace": ("Headspace", "Healthcare", "United States", []),
    "automattic": ("Automattic", "Technology", "United States", []),
    "johnson-johnson": ("Johnson & Johnson", "Pharma & Biotech", "United States", []),
    "novartis": ("Novartis", "Pharma & Biotech", "Switzerland", []),
    "bristol-myers-squibb": ("Bristol Myers Squibb", "Pharma & Biotech", "United States", []),
    "cvs-health": ("CVS Health", "Healthcare", "United States", []),
    "starbucks": ("Starbucks", "Food & Hospitality", "United States", []),
    "mcdonalds": ("McDonald's", "Food & Hospitality", "United States", []),
    "coinbase": ("Coinbase", "Finance", "United States", []),
    "patreon": ("Patreon", "Technology", "United States", []),
    "ubisoft": ("Ubisoft", "Media & Entertainment", "France", []),
    "linkedin": ("LinkedIn", "Technology", "United States", []),
    "elementor": ("Elementor", "Technology", "Israel", []),
    "epic-games": ("Epic Games", "Media & Entertainment", "United States", []),
    "bbc": ("BBC", "Media & Entertainment", "United Kingdom", []),
    "wisetech": ("WiseTech Global", "Technology", "Australia", []),
    "washington-post": ("The Washington Post", "Media & Entertainment", "United States", []),
    "arsenal": ("Arsenal FC", "Media & Entertainment", "United Kingdom", []),
    "telegraph": ("The Telegraph", "Media & Entertainment", "United Kingdom", []),
    "innodata": ("Innodata", "Technology", "United States", []),
    "sucker-punch": ("Sucker Punch Productions", "Media & Entertainment", "United States", []),
    "westpac": ("Westpac", "Finance", "Australia", []),
    "asml": ("ASML", "Technology", "Netherlands", []),
    "atlassian": ("Atlassian", "Technology", "Australia", []),
    "cloudflare": ("Cloudflare", "Technology", "United States", []),
    "flock-safety": ("Flock Safety", "Technology", "United States", ["flocksafety.com"]),
}

ALIASES = {
    "airbaltic": "air-baltic", "24hr-homecare": "24-hour-home-care", "o-briens-market": "o-brien-s-market",
    "alphabet": "google", "meta-platforms": "meta", "facebook": "meta", "amazon-com": "amazon", "aws": "amazon",
    "amazon-web-services": "amazon", "gm": "general-motors", "international-business-machines": "ibm",
    "jpmorgan-chase": "jpmorgan", "jp-morgan": "jpmorgan", "citi": "citigroup", "p-g": "procter-gamble",
    "procter-and-gamble": "procter-gamble", "warner-bros": "warner-bros-discovery", "wbd": "warner-bros-discovery",
    "pepsi": "pepsico", "tata-consultancy-services": "tcs", "vw": "volkswagen", "twitter": "x",
    "walt-disney": "disney", "the-walt-disney": "disney", "hewlett-packard": "hp", "hp-inc": "hp", "at-t-inc": "at-t",
    "nestle-s-a": "nestle", "wisetech-global": "wisetech", "the-washington-post": "washington-post", "federal-express": "fedex", "jlr": "jaguar-land-rover", "amex": "american-express", "jack-dorsey": "block",
    "mark-zuckerberg": "meta", "andy-jassy": "amazon", "sundar-pichai": "google", "satya-nadella": "microsoft",
    "square": "block", "volvo": "volvo-cars", "national-australia-bank": "nab", "commonwealth-bank": "cba", "bat": "british-american-tobacco", "stanchart": "standard-chartered", "vw-group": "volkswagen",
    "volkswagen-group": "volkswagen", "bmw-group": "bmw", "mercedes": "mercedes-benz", "deutsche-bahn": "db-cargo", "kaiser": "kaiser-permanente", "electronic-arts": "ea", "universal-music": "universal-music-group", "united-parcel-service": "ups", "snap-inc": "snap", "block-inc": "block",
}

US_STATES = ("Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida|Georgia|Hawaii|Idaho|"
             "Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|"
             "Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|New York|North Carolina|North Dakota|"
             "Ohio|Oklahoma|Oregon|Pennsylvania|Rhode Island|South Carolina|South Dakota|Tennessee|Texas|Utah|Vermont|"
             "Virginia|Washington state|West Virginia|Wisconsin|Wyoming|Silicon Valley|Bay Area|Seattle|Chicago|Boston|"
             "Los Angeles|San Francisco|Atlanta|Detroit|Houston|Dallas|Austin|Denver|Phoenix|Pittsburgh")
US_STATE_CODES = set("AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC "
                     "ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split())

COUNTRY_CUES = [
    (r"\b(U\.?S\.?|USA|American|United States|" + US_STATES + r")\b", "United States"),
    (r"\b(UK|U\.K\.|Britain|British|England|Scotland|Wales|London|Manchester)\b", "United Kingdom"),
    (r"\b(India|Indian|Bengaluru|Bangalore|Mumbai|Hyderabad|Pune|Chennai|Gurugram|Noida|Delhi)\b", "India"),
    (r"\b(Germany|German|Berlin|Munich)\b", "Germany"),
    (r"\b(France|French|Paris)\b", "France"),
    (r"\b(Canada|Canadian|Toronto|Vancouver|Montreal|Ontario|Quebec)\b", "Canada"),
    (r"\b(Australia|Australian|Sydney|Melbourne)\b", "Australia"),
    (r"\b(Ireland|Irish|Dublin)\b", "Ireland"),
    (r"\b(Israel|Israeli|Tel Aviv)\b", "Israel"),
    (r"\b(Japan|Japanese|Tokyo)\b", "Japan"),
    (r"\b(China|Chinese|Beijing|Shanghai|Shenzhen)\b", "China"),
    (r"\b(Singapore)\b", "Singapore"),
    (r"\b(Netherlands|Dutch|Amsterdam)\b", "Netherlands"),
    (r"\b(Sweden|Swedish|Stockholm)\b", "Sweden"),
    (r"\b(Switzerland|Swiss|Zurich)\b", "Switzerland"),
    (r"\b(Spain|Spanish|Madrid)\b", "Spain"),
    (r"\b(Italy|Italian|Milan)\b", "Italy"),
    (r"\b(South Korea|Korean|Seoul)\b", "South Korea"),
    (r"\b(Brazil|Brazilian|São Paulo|Sao Paulo)\b", "Brazil"),
    (r"\b(Mexico|Mexican)\b", "Mexico"),
    (r"\b(Poland|Polish)\b", "Poland"),
    (r"\b(Denmark|Danish|Copenhagen)\b", "Denmark"),
    (r"\b(Finland|Finnish)\b", "Finland"),
    (r"\b(Belgium|Belgian|Brussels)\b", "Belgium"),
    (r"\b(Philippines|Filipino|Manila)\b", "Philippines"),
    (r"\b(Nigeria|Nigerian|Lagos)\b", "Nigeria"),
    (r"\b(South Africa|Johannesburg|Cape Town)\b", "South Africa"),
    (r"\b(New Zealand)\b", "New Zealand"),
    (r"\b(Europe|European)\b", "Europe (multi)"),
]
_COUNTRY_RX = [(re.compile(p), c) for p, c in COUNTRY_CUES]

COUNTRIES_FOR_FORM = sorted({c for _, c in COUNTRY_CUES if "multi" not in c} | {"Other"})


def country_from_text(text):
    for rx, c in _COUNTRY_RX:
        if rx.search(text or ""):
            return c
    return None


def industry_from_text(text):
    for p, ind in INDUSTRY_HINTS:
        if re.search(p, text or "", re.I):
            return ind
    return None


def publisher_tier(name):
    n = (name or "").strip().lower()
    return "major" if n in MAJOR_OUTLETS else "news"


FREEMAIL = {"gmail.com", "googlemail.com", "yahoo.com", "outlook.com", "hotmail.com", "live.com", "icloud.com",
            "me.com", "proton.me", "protonmail.com", "aol.com", "gmx.com", "gmx.de", "mail.com", "yandex.com", "zoho.com"}
