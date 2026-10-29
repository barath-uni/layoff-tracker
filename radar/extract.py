"""Heuristic extraction of (company, headcount, pct, kind, country, industry) from headlines.

Regex first. An optional LLM hook (radar/llm.py) can fill in items the rules miss; it is off by default.
"""
import re

from .ref import ALIASES, JUNK_NAMES, KNOWN, TIER_WEIGHT, US_STATES, country_from_text, industry_from_text
from .util import slugify

# ------------------------------------------------------------------ building blocks
TOK = r"(?:[A-Z0-9][\w'’.&\-]*|[a-z]{1,2}[A-Z][\w'’.&\-]*)"
NAME = rf"(?P<co>{TOK}(?:\s+(?:(?:&|of|de|for)\s+)?{TOK}){{0,5}})"
AUX = r"(?:(?i:is|are|will|to|plans?\s+to|set\s+to|reportedly|quietly|now|also|again|begins?\s+to|starts?\s+to|moves?\s+to|expected\s+to|could|may|would|says?\s+it\s+will)\s+)*"
JOBNOUN = r"(?i:jobs?|employees?|workers?|staff(?:ers)?|positions?|roles?|workforce|headcount|people|layoffs?|personnel|engineers?|corporate|redundanc(?:y|ies)|nurses?|managers?|teams?)"
VERB_STRICT = r"(?i:lay(?:s|ing)?\s+off|laid\s+off|lay\s*off)"
VERB_CUT = r"(?i:cut(?:s|ting)?|slash(?:es|ing)?|eliminat(?:e|es|ing)|axe[sd]?|axing|shed(?:s|ding)?|trim(?:s|ming)?|reduc(?:e|es|ing)|furlough(?:s|ing)?)"
NOUN_LAYOFF = r"(?i:(?:new\s+|more\s+|fresh\s+|mass\s+|major\s+|sweeping\s+|another\s+round\s+of\s+|a\s+round\s+of\s+|round\s+of\s+|global\s+)*(?:layoffs?|job\s+cuts|redundancies|cuts))"
VERB_ANNOUNCE = r"(?i:announc(?:e|es|ed|ing)|confirm(?:s|ed)?|begin(?:s)?|start(?:s)?|issu(?:e|es|ed)|plan(?:s|ned)?|launch(?:es)?|unveil(?:s)?|carr(?:y|ies)\s+out|conduct(?:s)?|hit\s+by|hit\s+with|makes?|making|reveal(?:s)?|order(?:s)?)"

RX_A = re.compile(rf"^{NAME}\s+{AUX}(?P<verb>{VERB_STRICT}|{VERB_CUT})\b(?P<rest>.*)$")
RX_C = re.compile(rf"^{NAME}\s+{AUX}{VERB_ANNOUNCE}\s+(?:its\s+|their\s+|a\s+|an\s+)?(?:\w+\s+){{0,2}}?{NOUN_LAYOFF}\b(?P<rest>.*)$")
RX_D = re.compile(rf"^{NAME}(?:['’]s)?\s+(?:(?i:latest|new|fresh|mass|more|major|massive|global|another\s+round\s+of)\s+)?(?i:layoffs?|job\s+cuts|redundancies)\b(?P<rest>.*)$")
RX_B = re.compile(rf"(?i:layoffs?|job\s+cuts|redundancies|cuts)\s+(?:(?i:announced|reported|confirmed|coming|underway|continue|hit|strike|loom|planned|expected)\s+)?(?i:at|hit|for|from)\s+{NAME}(?P<rest>.*)$")
RX_E = re.compile(rf"(?P<num>\d{{1,3}}(?:,\d{{3}})+|\d+)\s+(?:\w+\s+){{0,2}}?{JOBNOUN}\s+(?i:to\s+be\s+)?(?i:cut|laid\s+off|lose\s+(?:their\s+)?jobs|axed|eliminated)\s+(?i:at|by)\s+{NAME}")

NUM = r"(?P<n>\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?\s*(?:[kK]|thousand|million)?|\d+)"
COUNTNOUN = r"(?i:jobs?|employees?|workers?|staff(?:ers)?|positions?|roles?|people|layoffs?|personnel|engineers?|redundanc(?:y|ies)|nurses?|managers?)"
RX_COUNT = re.compile(rf"(?<![$€£\d.,])(?:(?i:about|around|roughly|nearly|almost|approximately|some|over|more\s+than|up\s+to|at\s+least|another|an?\s+additional)\s+)?{NUM}\s+(?:(?:more|additional|corporate|tech|office|full-time|global|white-collar|local|union|U\.S\.|US|UK|India|salaried|hourly|remote|plant|factory|retail|warehouse|store|frontline|non-union|[A-Z]\w+)\s+){{0,2}}{COUNTNOUN}")
RX_COUNT2 = re.compile(rf"(?<![$€£\d.,]){NUM}\s+(?i:laid\s+off|layoffs|job\s+cuts|jobs\s+cut|jobs\s+lost)")
RX_PCT = re.compile(r"(\d+(?:\.\d+)?)\s*(?:%|percent|per\s+cent)\s+of\s+(?:its\s+|the\s+|their\s+|our\s+|global\s+|total\s+|corporate\s+|overall\s+)*(?:workforce|staff|employees|jobs|headcount|work\s+force|employee\s+base|team)", re.I)

KEYWORD = re.compile(r"(?i)lay(?:s|ing)?\s*off|laid off|layoff|job cuts|cut(?:s|ting)? .{0,30}(jobs|workforce|staff|employees|workers|positions|roles)|redundanc|workforce reduction|eliminat\w+ .{0,25}(jobs|positions|roles)|slash\w* .{0,20}(jobs|workforce|staff)|shed\w* .{0,20}jobs|axe\w* .{0,20}jobs|furlough")
ROUNDUP = re.compile(r"(?i)\b(tracking|tracker|list of|these companies|companies (?:that|which|cutting|laying)|and others|roundup|so far this year|all the (?:job|layoff)|biggest layoffs of|every company|here are|here's who|which companies|layoffs? this week|week in layoffs|hit this week|in history)\b")
NEGATIVE = re.compile(r"(?i)\b(block layoffs|blocks layoffs|no layoffs|without layoffs|rules? out|denies|won't lay|will not lay|avoid(?:s|ed)? layoffs|not planning|reverses?|rehir\w+|hiring spree|lawsuit|sued|sues|settlement|cancel(?:s|led|ed)?\s+(?:\w+\s+){0,2}(?:plans?\s+(?:to|for)\s+)?(?:lay|layoffs?|job cuts)|scraps?\s+(?:\w+\s+){0,2}(?:layoffs?|job cuts)|calls? off|walks? back|fact.?check|false claim|fake news)\b")
SPECULATIVE = re.compile(r"(?i)\b(reportedly|report says|sources say|sources said|considering|weighs|weighing|mulls|could|may|might|rumou?r|according to (?:a )?report|eyes|looming|soon|expected to|likely to|set to face|braces for|fears?|at risk|in jeopardy|threatened)\b|\?|[:\-–] report$")
PROTEST = re.compile(r"(?i)\b(protest\w*|rall(?:y|ies|ied)|march(?:es|ed)? against|strike|strikes|picket\w*|demonstrat\w*)\b")
# Numbers that describe the past or a multi-year target, not this event.
RETRO = re.compile(r"(?i)\b(in (?:the )?(?:past|last) (?:\w+ )?(?:years?|months?)|over (?:the )?(?:past|last)|in (?:two|three|four|five|six|seven|eight|ten|\d+) months|in (?:a|one|the) year|since 20\d\d|so far|last year|this year|in 20\d\d|in FY ?\d+|in total|total|total of|cumulative|to date|years? of|over the years|year-to-date|ytd|already|so far|until now|thus far)\b")
# A future, multi-year target ("by 2030", "over the next three years"): an announced plan, shown but never counted.
PLAN = re.compile(r"(?i)\b(?:by|through|until|before|by the end of|by end of)\s+(?:the\s+)?(?:end\s+of\s+)?(?:fiscal\s+(?:year\s+)?|FY\s?)?(20\d\d)\b|"
                  r"\b(?:over|in|within|during) the (?:next|coming|following) (?:\w+ )?years\b|\bby the end of the decade\b|\bmulti-?year\b|"
                  r"\bover (?:two|three|four|five|six|seven|eight|ten|\d+) years\b|\bin (?:two|three|four|five|\d+) years\b")
# Past tense without an auxiliary usually recaps an earlier round ("Amazon Laid Off 30,000 Workers While ...").
PAST_RECAP = re.compile(r"(?i)(?<!has )(?<!have )(?<!had )(?<!been )(?<!be )(?<!to )(?<!will )\b(laid off|slashed|eliminated|axed)\s+(?:about |around |roughly |nearly |over |more than )?\d")
# "UPS Cut 48,000 Jobs and Doubled Down on Automation": a bare "cut N jobs" joined to another past-tense verb is a recap.
PAST_CUT_AND = re.compile(r"(?i)\bcut\s+(?:about |around |roughly |nearly |over |more than )?\d[\d,.]*\s*[kK]?\s+\w+\s+(?:and|while|but|then)\s+(?!will\b)\w+ed\b")
NUM_CUTOFF = re.compile(r"(?i)\b(after|following|on top of|since|having|months after|weeks after|than)\b")
BUYOUT = re.compile(r"(?i)\b(buyouts?|voluntary (?:separation|exit|redundancy|retirement)|early retirement)\b")

PREFIX = re.compile(r"^(?:(?i:exclusive|breaking|update\s*\d*|watch|live|report|analysis|opinion|video|podcast|scoop|just in|sources)\s*[:\-–—|]\s*)+")

# Single-word names that are really common words or generic subjects.
STOP_SINGLE = set("""
why how what when where who as after amid more mass massive major big new latest another tech federal state local
government trump biden musk ai companies company workers employees employers report reports study survey here this these
those the a an it its i we you they our us uk eu jobs job layoffs layoff cuts cut hiring markets stocks wall street analysts
experts ceo ceos industry sector startups startup businesses firms firm bank banks hospitals hospital university universities
school schools city county retailers retail automakers carmakers chipmakers airlines nonprofits media newsrooms video gaming
game games january february march april may june july august september october november december monday tuesday wednesday
thursday friday saturday sunday some many nearly about over hundreds thousands dozens two three four five six seven eight nine ten
top global worldwide several multiple area regional national is are will could should does did can every all most your my
first second third last next one more inside tracking fearing exclusive breaking update watch live opinion analysis explainer
podcast photos now today week year years month months ahead amidst despite following before during while if once since
silicon valley wall-street pentagon congress senate house white doge irs usps nasa state-run agencies agency department
officials union unions staffers staff people women men americans britons indians canadians australians europeans
california texas florida ohio michigan york washington india china japan germany britain canada australia europe asia
america american british indian german french chinese japanese canadian australian european global international
economy economic market labor labour employment unemployment manufacturing manufacturers factories factory plants plant
software hardware cloud cybersecurity fintech crypto healthcare pharma biotech banking insurance energy oil gas telecom
time times plans stock what know depot hospice journalism engineers small fresh sweeping from u.s u.s. u.k u.k. newspaper newspapers publishers studios streaming hollywood mortgage xbox gaming contractors contractor district
""".split())
NEVER_START = set("""why how what when where who as after amid inside tracking fearing exclusive breaking update watch live opinion
analysis explainer podcast here these those this some many more most nearly about over hundreds thousands dozens if once
while despite following before during since will could should does did can is are every all your my our their his her
with without ex former local mass. largest biggest big us u.s. uk u.k. mark nearly
""".split())
DESCRIPTOR = set("""chipmaker chip-maker automaker carmaker retailer giant tech-giant startup firm drugmaker pharma
streaming e-commerce ecommerce social media software maker bank lender insurer airline conglomerate brewer company
group operator provider developer publisher studio network chain manufacturer supplier distributor platform app
the a an embattled troubled struggling beleaguered ailing cash-strapped fintech edtech healthtech biotech telecom
german french indian swedish chinese japanese korean british canadian australian dutch swiss irish israeli american
us u.s. uk u.k. european finnish danish norwegian spanish italian brazilian mexican singaporean taiwanese
tech ai crypto gaming video game electric ev vehicle search cloud semiconductor networking cybersecurity payments
delivery ride-hailing food home appliance consumer""".split())
NATIONALITY = set("""german french indian swedish chinese japanese korean british canadian australian dutch swiss irish israeli
american us u.s. uk u.k. european finnish danish norwegian spanish italian brazilian mexican singaporean taiwanese""".split())
# Title-case words that end a company name ("Netflix Gearing Up ..." -> "Netflix").
BREAK = set("""gearing up eyes makes making more job jobs acknowledge acknowledges means restructuring ceo ceos co-ceos hit hits
announces confirms plans cuts cutting is to will reportedly begins starts quietly latest new major mass staff workers employees
layoffs layoff after amid as with in at on by from sees faces says set prepares preps looks considers weighs readies unveils
launches issues conducts carries out now again also just another round second third global worldwide developer studio maker
parent owner exec execs executives boss chief cfo president union could may might has have had was were be being slashes
lays laying cut axes sheds trims eliminates reduces impacted affected tv told tells unexpectedly employee
india us u.s. uk u.k. germany canada australia europe ireland japan china singapore uae""".split())
TRAIL_PLACE = set("india us u.s. uk u.k. germany canada australia europe ireland japan china singapore uae emea asia america".split())
CITIES = set("""minneapolis seattle chicago boston atlanta detroit houston dallas austin denver phoenix pittsburgh portland
cleveland columbus cincinnati milwaukee nashville charlotte miami orlando tampa baltimore philadelphia sacramento oakland
san jose san diego st. louis kansas city indianapolis omaha toronto vancouver london paris berlin munich dublin bengaluru
mumbai sydney melbourne singapore tokyo hyderabad pune chennai montreal calgary manchester birmingham glasgow""".split("\n")[0].split()) | {
    "san jose", "san diego", "st. louis", "kansas city", "san francisco", "los angeles", "new york", "silicon valley"}
CITIES |= set("""cleveland columbus cincinnati milwaukee nashville charlotte miami orlando tampa baltimore philadelphia sacramento
oakland toronto vancouver london paris berlin munich dublin bengaluru mumbai sydney melbourne singapore tokyo hyderabad pune
chennai montreal calgary manchester birmingham glasgow omaha indianapolis""".split())
AUX_TRAIL = set("is are will to plans plan set reportedly quietly now also again begins starts moves expected could may would says".split())

LEGAL_SUFFIX = re.compile(r"(?i)[,\s]+(inc\.?|incorporated|corp\.?|corporation|llc|l\.l\.c\.|ltd\.?|limited|co\.?|company|plc|"
                          r"holdings?|groups?|n\.a\.?|n\.v\.?|l\.p\.|lp|s\.a\.|ag|gmbh|se|nv|n\.v\.|bv|oyj|asa|pty|pte|/[a-z]{2}/?)$")


def clean_company(name):
    """Normalise a raw company string to a display name ('' if it is not a company)."""
    name = re.sub(r"&rsquo;|&#8217;", "’", name or "").strip(" ,.;:-–—'\"“”‘’")
    name = re.sub(r"\s+dba\s+.*$", "", name, flags=re.I)
    name = re.sub(r"(?i)[\s,(]+(?:updated?|update|amended|revised|corrected|etal|et\.? al\.?)\)?\s*$", "", name)
    name = re.split(r"\s+[-–]\s+", name)[0]  # WARN site suffixes: "Intel Corporation - SC11"
    name = re.split(r"\s+/\s+", name)[0]  # WARN multi-site: "Maverick Washington LLC / Palace Casino"
    name = re.sub(r"(?i)(,?\s+(?:inc|llc|corp|ltd)\.?)\s+\S.*$", r"\1", name)  # "Uber Technologies, Inc. 1725 3rd Street"
    name = re.sub(r"^\S+-(?:owned|backed|based)\s+", "", name)
    name = re.sub(r"(?i)^.+?\s+(?:rivals?|competitor|peer)\s+(?=\S)", "", name)  # "Ford Rival VW" -> "VW"
    name = re.sub(r"\s*\(.*?\)\s*", " ", name).strip()
    for _ in range(3):
        name = LEGAL_SUFFIX.sub("", name).strip(" ,.")
    toks = name.split()
    while toks and toks[-1].lower() in AUX_TRAIL:
        toks.pop()
    while len(toks) > 1 and toks[0].lower().strip(":") in DESCRIPTOR:
        if toks[0].lower() in NATIONALITY and (toks[1].lower() not in DESCRIPTOR or toks[1].lower() in NATIONALITY):
            break  # "American Express" stays; "German automaker VW" -> "VW"
        toks.pop(0)
    while len(toks) > 1 and toks[-1].lower() in TRAIL_PLACE | {"stock", "shares", "ceo"}:
        toks.pop()
    while len(toks) > 1 and toks[-1].lower() in ("layoffs", "layoff", "jobs", "cuts", "workers", "employees", "staff"):
        toks.pop()
    if len(toks) == 1 and toks[0].endswith(("'s", "’s")):
        toks = [toks[0][:-2]]
    name = " ".join(toks).strip(" ,.:")
    if not name or len(name) < 2:
        return ""
    if name.isupper() and len(name) > 4:  # SEC-style ALL CAPS
        name = " ".join(w if len(w) <= 3 and w.isalpha() and w not in ("THE", "AND") else w.capitalize() for w in name.split())
    return name


def canonical_slug(name):
    s = slugify(name)
    return ALIASES.get(s, s)


def valid_company(name, strict=True):
    if not name:
        return False
    toks = name.split()
    if len(toks) > 6:
        return False
    if canonical_slug(name) in KNOWN:
        return True
    if toks[0].lower() in NEVER_START:
        return False
    if len(toks) == 1 and name.lower().replace("'s", "") in STOP_SINGLE:
        return False
    if all(t.lower() in STOP_SINGLE or t.lower() in DESCRIPTOR for t in toks):
        return False
    if re.fullmatch(r"[\d,.%]+", name) or re.search(r"\d{4}", name) or re.fullmatch(r"(?i)(q[1-4]|h[12]|fy\d*)", toks[0]):
        return False
    if any(re.fullmatch(r"\d+(\.\d+)?[kKmM]", t) for t in toks) or re.search(r"['’]s\s", name):
        return False
    if len(toks) <= 2 and name.lower() in CITIES:
        return False
    if len(toks) <= 2 and (re.fullmatch(US_STATES, name) or (len(toks) == 1 and country_from_text(name))):
        return False
    if strict and len(toks) >= 4 and sum(t[0].isupper() for t in toks) < len(toks) - 1:
        return False
    return True


PRODUCT_SEP = {"developer", "dev", "studio", "maker", "publisher", "owner", "parent", "operator", "creator", "firm"}


def refine(co, title_case, gazetteer):
    """Trim over-captured names: product->company ("Ghost of Yotei Dev Sucker Punch" -> "Sucker Punch"),
    then the longest known prefix or suffix, then break words in Title Case headlines."""
    toks = co.split()
    for i, t in enumerate(toks[1:], 1):
        if t.lower().strip(".'’") in PRODUCT_SEP and i + 1 < len(toks) and toks[i + 1][:1].isupper():
            toks = toks[i + 1:]
            break
    co = " ".join(toks)
    if len(toks) == 1:
        return co
    if gazetteer:
        for i in range(len(toks), 0, -1):
            if canonical_slug(" ".join(toks[:i])) in gazetteer:
                return " ".join(toks[:i])
        for i in range(1, len(toks)):
            if canonical_slug(" ".join(toks[i:])) in gazetteer and len(" ".join(toks[i:])) > 3:
                return " ".join(toks[i:])
    if title_case:
        for i, t in enumerate(toks[1:], 1):
            if t.lower().strip("'’") in BREAK:
                return " ".join(toks[:i])
    return co


def parse_count(s):
    had_sep = "," in s
    s = s.strip().lower().replace(",", "")
    mult = 1
    if s.endswith("k"): mult, s = 1000, s[:-1]
    elif s.endswith("thousand"): mult, s = 1000, s[:-8]
    elif s.endswith("million"): mult, s = 1_000_000, s[:-7]
    try:
        v = float(s.strip()) * mult
    except ValueError:
        return None
    v = int(round(v))
    if v < 3 or v > 500_000 or (1990 <= v <= 2035 and mult == 1 and "." not in s and not had_sep):  # "2,000 jobs" is not a year
        return None
    return v


def plan_horizon(text, year=None):
    """'2030' / 'multi-year' when the headline states a future multi-year target, else None."""
    m = PLAN.search(text)
    if not m:
        return None
    if m.group(1):
        return m.group(1) if year and int(m.group(1)) > year else None
    return "multi-year"


def numbers(text, year=None):
    m = NUM_CUTOFF.search(text)
    if m and m.start() > 15:
        text = text[: m.start()]
    horizon = plan_horizon(text, year)
    past_year = year and any(int(y) < year for y in re.findall(r"(?<!\d)(20\d\d)(?!\d)", text))
    if not horizon and (RETRO.search(text) or PAST_RECAP.search(text) or PAST_CUT_AND.search(text) or past_year):
        return None, None
    hc = pct = None
    for rx in (RX_COUNT, RX_COUNT2):
        for m in rx.finditer(text):
            v = parse_count(m.group("n"))
            if v:
                hc = max(hc or 0, v)
        if hc:
            break
    m = RX_PCT.search(text)
    if m:
        p = float(m.group(1))
        if 0 < p <= 100:
            pct = p
    return hc, pct


def _match_company(t):
    """Try patterns in priority order on one headline segment. Returns (company, method)."""
    for rx, method in ((RX_A, "verb"), (RX_C, "announce"), (RX_D, "noun"), (RX_E, "count-at"), (RX_B, "at")):
        m = rx.search(t)
        if not m:
            continue
        if method == "verb":
            verb = m.group("verb").lower()
            if not re.match(r"lay|laid", verb) and not re.search(JOBNOUN + r"|\d+\s*%", m.group("rest")):
                continue
        co = clean_company(m.group("co"))
        if valid_company(co, strict=method != "verb"):
            return co, method
    return None, None


def is_title_case(t):
    words = [w for w in re.findall(r"[A-Za-z][\w'’]*", t) if len(w) > 3]
    return bool(words) and sum(w[0].isupper() for w in words) / len(words) > 0.7


def extract_headline(title, text="", gazetteer=None, year=None):
    """Return dict(company, headcount, pct, kind, speculative, country, industry, method, horizon) or None."""
    t = re.sub(r"\s+", " ", (title or "").replace(" ", " ")).strip()
    t = re.sub(r"[“”]", '"', t).replace("’", "'")
    if not t or NEGATIVE.search(t) or ROUNDUP.search(t):
        return None
    if len(re.findall(r",(?!\d{3})", t)) >= 3 or t.count("|") >= 2:  # lists / newsletter digests
        return None
    if not KEYWORD.search(t):
        return None
    segs = [PREFIX.sub("", t)]
    if ":" in segs[0]:
        a, b = segs[0].split(":", 1)
        segs = [b.strip(), a.strip()] if len(a.split()) <= 4 else [segs[0], b.strip()]
    co = method = None
    for s in segs:
        co, method = _match_company(s)
        if co:
            break
    if not co:
        return None
    co = re.sub(r"['’]s$", "", refine(co, is_title_case(t), gazetteer))
    if not valid_company(co, strict=False):
        return None
    hc, pct = numbers(t, year)
    full = f"{t} {text or ''}"
    kind = "buyout" if BUYOUT.search(t) and not re.search(VERB_STRICT, t) else "layoff"
    horizon = plan_horizon(t, year)
    if horizon and (hc or pct) and kind == "layoff":
        # the deadline must belong to the job number ("cut 35,000 jobs by 2030"), not to another goal in the headline
        pm = PLAN.search(t)
        cm = RX_COUNT.search(t) or RX_COUNT2.search(t) or RX_PCT.search(t)
        if pm and cm and -10 <= pm.start() - cm.end() <= 45:
            kind = "plan"
        else:
            horizon = None
    if PROTEST.search(t):
        hc = None  # "500 workers rally against layoffs" counts protesters
    return {
        "company": co, "headcount": hc, "pct": pct, "kind": kind,
        "speculative": bool(SPECULATIVE.search(t)), "country": country_from_text(full),
        "industry": industry_from_text(full), "method": method, "horizon": horizon if kind == "plan" else None,
    }


EDITION_COUNTRY = {"US": "United States", "GB": "United Kingdom", "IN": "India", "CA": "Canada", "AU": "Australia", "SG": "Singapore"}
TLD_COUNTRY = {"uk": "United Kingdom", "de": "Germany", "fr": "France", "it": "Italy", "es": "Spain", "nl": "Netherlands",
               "be": "Belgium", "at": "Austria", "ch": "Switzerland", "se": "Sweden", "no": "Norway", "dk": "Denmark",
               "fi": "Finland", "pl": "Poland", "cz": "Czechia", "hu": "Hungary", "ro": "Romania", "gr": "Greece",
               "pt": "Portugal", "ie": "Ireland", "tr": "Turkey", "ru": "Russia", "ua": "Ukraine", "jp": "Japan",
               "kr": "South Korea", "cn": "China", "tw": "Taiwan", "hk": "Hong Kong", "in": "India", "id": "Indonesia",
               "my": "Malaysia", "sg": "Singapore", "th": "Thailand", "vn": "Vietnam", "ph": "Philippines", "au": "Australia",
               "nz": "New Zealand", "za": "South Africa", "ng": "Nigeria", "ke": "Kenya", "eg": "Egypt", "sa": "Saudi Arabia",
               "ae": "United Arab Emirates", "il": "Israel", "br": "Brazil", "mx": "Mexico", "ar": "Argentina", "cl": "Chile",
               "co": "Colombia", "pe": "Peru", "ca": "Canada", "pk": "Pakistan", "bd": "Bangladesh", "lu": "Luxembourg"}


def source_country(it):
    """Where the outlet is: its country domain (.de, .co.uk), else the edition's country for non-English stories.
    An English story on a .com site found through the UK edition says nothing about where the cuts are."""
    meta = it["meta"]
    host = (meta.get("publisher_url") or meta.get("domain") or "").lower()
    host = re.sub(r"^https?://", "", host).split("/")[0]
    tld = host.rsplit(".", 1)[-1] if "." in host else ""
    if tld in TLD_COUNTRY:
        return TLD_COUNTRY[tld]
    if meta.get("lang") and meta["lang"] != "en":
        return meta.get("src_country")
    if it["source"] == "gdelt" and meta.get("src_country") and meta.get("lang") not in (None, "en"):
        return meta["src_country"]
    return None


def item_lang(it):
    meta = it["meta"]
    if meta.get("lang"):
        return meta["lang"]
    return "en"


# ------------------------------------------------------------------ cross-language rules (title of any language)
# The company denies the cuts ("Porsche dément vouloir en supprimer 4 000 de plus", "Soriana aclara ..."): no claim.
DENIAL = re.compile(r"(?i)\b(?:denies|denied|deny|refutes|niega|desmiente|aclara|dementiert|dementi\w*|dément\w*|démenti\w*|"
                    r"smentisc\w*|smentit\w*|desmente|nega|membantah|bantah|zaprzecza|dementuje|ontkent|yalanla\w*|"
                    r"опроверг\w*|отрица\w*|спростов\w*)\b|否认|否認|辟谣|闢謠")
# Workers WON protection from layoffs ("1900 salariés de Blizzard obtiennent de nouvelles garanties"): not a layoff.
PROTECTED = re.compile(r"(?i)job protections?|protections? (?:from|against)|won protections|\bgaranties\b|\bgarantías\b|\bgaranzie\b|"
                       r"защиту от увольн|захист від звільн|kündigungsschutz|beschäftigungsgarantie|jobgarantie")
# A voluntary-exit offer ("plan de départs volontaires pour 60 000", "6만명 희망퇴직"): kind buyout, shown nowhere, never counted.
VOLUNTARY = re.compile(r"(?i)\b(?:voluntar\w*|volontai\w*|volontari\w*|freiwillig\w*|vrijwillig\w*|dobrowoln\w*|önkéntes\w*|"
                       r"добровольн\w*|добровільн\w*|gönüllü\w*|sukarela|early retirement|buyouts?)\b|희망퇴직|希望退職|早期退職|自愿离职|自願離職")
# Cuts by a contractor/outsourcer of a named firm ("Meta外包商裁員", "empresa de moderadores vinculada a Meta"): not that firm.
CONTRACTOR = re.compile(r"(?i)empresa de moderador\w*|\bmoderadores\b|contratista|subcontrat\w*|sous-traitan\w*|subunternehm\w*|"
                        r"外包商|外包公司|下請け|협력업체|(?:contractor|subcontractor|vendor|outsourcer)\s+(?:for|of|to|linked to|working for)\b|"
                        r"['’]s\s+(?:contractor|vendor|outsourcer)")
# Somebody demands cuts ("Porsche y Piëch exigen cierres y 50.000 despidos"): a demand, not an announced figure.
DEMAND = re.compile(r"(?i)\b(?:exig\w+|demands?|demanding|fordern|fordert|réclam\w+|calls? for|urges?)\b")
# A staff count, not the cut ("despidos en España, donde cuenta con 2.000 trabajadores").
STAFF = re.compile(r"(?i)(?:cuenta con|donde (?:emplea|tiene|trabajan)|emplea a|conta com|qui emploie|which employs|that employs|"
                   r"where it employs|employs|has a workforce of|beschäftigt|impiega|plantilla de)\s+(?:a\s+|unos\s+|about\s+|rund\s+|más de\s+)?"
                   r"(\d{1,3}(?:[.,\s]\d{3})+|\d+)")


# The cuts were averted ("para evitar 150 demissões", "esuberi scongiurati"): no layoff.
AVERTED = re.compile(r"(?i)\b(?:evitar|avoid(?:ing|s)?|evitare|éviter|vermeiden)\s+(?:(?:as|os|the|i|les|los|las|die)\s+)?"
                     r"(?:\d|layoffs|job cuts|demiss|despid|licenzia|licenci|entlass)|\bscongiurat\w*|\babgewendet\b")
# News briefs list several firms; the subject parser grabs the wrong one ("En bref: Sunrise confirme ..., Google ...").
BRIEFS = re.compile(r"(?i)^\s*(?:en bref|in brief|news in brief|briefs?|kurz gemeldet|in breve)\s*[:\-–]")
# The firm is only the medium ("CEO que despidió a 900 empleados por Zoom").
MEDIUM = re.compile(r"(?i)\b(?:por|via|over|on a|by|en)\s+zoom\b|因zoom|透過zoom")


def cross_language_rules(title, ex):
    """Apply the rules above to an extraction; return the adjusted dict, or None to drop the claim."""
    t = title or ""
    if DENIAL.search(t) or PROTECTED.search(t) or CONTRACTOR.search(t) or AVERTED.search(t) or BRIEFS.search(t):
        return None
    if canonical_slug(ex["company"]) == "zoom" and MEDIUM.search(t):
        return None
    if VOLUNTARY.search(t):
        ex["kind"] = "buyout"
    if ex.get("headcount") and DEMAND.search(t):
        ex["headcount"] = None
    for m in STAFF.finditer(t):
        if ex.get("headcount") == int(re.sub(r"\D", "", m.group(1))):
            ex["headcount"] = None
    return ex


def claims_from_item(it, gazetteer=None, llm=None, intl_gaz=None):
    """Turn a stored item row (dict with parsed meta) into a claim dict or None."""
    meta = it["meta"]
    w = TIER_WEIGHT[it["tier"]]
    lang = item_lang(it)
    year = int(it["published"][:4]) if it.get("published") else None
    src_cty = source_country(it)
    if it["tier"] == "official":
        co = clean_company(meta.get("company") or "")
        if not co:
            return None
        if lang in ("ja", "zh", "ko"):
            from .intl import SCRIPT_NAMES
            co = SCRIPT_NAMES.get(co, co)
        return {"company": co, "headcount": meta.get("headcount"), "pct": meta.get("pct"), "kind": meta.get("kind", "layoff"),
                "date": it["published"], "country": meta.get("country"), "location": meta.get("location"),
                "industry": meta.get("industry"), "weight": w, "speculative": 0, "method": it["source"],
                "horizon": None, "lang": lang, "src_country": meta.get("country")}
    if lang == "en":
        ex = extract_headline(it["title"], it.get("text", ""), gazetteer, year)
    else:
        from .intl import extract as intl_extract
        ex = intl_extract(it["title"], lang, intl_gaz, year)
    if not ex and llm and (KEYWORD.search(it["title"] or "") or lang != "en"):
        ex = llm(it["title"], it.get("text", ""))
    if not ex:
        return None
    if canonical_slug(ex["company"]) in JUNK_NAMES or ex["company"].lower().strip() in JUNK_NAMES:
        return None  # a product, game or outlet label, not an employer ("GTA 6公司4700人", "Vídeo não mostra ...")
    ex = cross_language_rules(it["title"], dict(ex))
    if not ex:
        return None
    if ex.get("speculative"):
        w *= 0.6
    return {"company": ex["company"], "headcount": ex.get("headcount"), "pct": ex.get("pct"), "kind": ex.get("kind", "layoff"),
            "date": it["published"], "country": ex.get("country"), "location": None, "industry": ex.get("industry"),
            "weight": round(w, 3), "speculative": int(bool(ex.get("speculative"))), "method": ex.get("method", "llm"),
            "horizon": ex.get("horizon"), "lang": lang, "src_country": src_cty}
