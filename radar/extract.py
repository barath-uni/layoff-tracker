"""Heuristic extraction of (company, headcount, pct, kind, country, industry) from headlines.

Regex first. An optional LLM hook (radar/llm.py) can fill in items the rules miss; it is off by default.
"""
import re

from .ref import ALIASES, KNOWN, TIER_WEIGHT, US_STATES, country_from_text, industry_from_text
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
RX_COUNT = re.compile(rf"(?<![$€£\d.,])(?:(?i:about|around|roughly|nearly|almost|approximately|some|over|more\s+than|up\s+to|at\s+least|another|an?\s+additional)\s+)?{NUM}\s+(?:(?:more|additional|corporate|tech|office|full-time|global|white-collar|local|union|U\.S\.|US|UK|India|salaried|hourly|remote|plant|factory|retail|warehouse|store|frontline|[A-Z]\w+)\s+){{0,2}}{JOBNOUN}")
RX_COUNT2 = re.compile(rf"(?<![$€£\d.,]){NUM}\s+(?i:laid\s+off|layoffs|job\s+cuts|jobs\s+cut|jobs\s+lost)")
RX_PCT = re.compile(r"(\d+(?:\.\d+)?)\s*(?:%|percent|per\s+cent)\s+of\s+(?:its\s+|the\s+|their\s+|our\s+|global\s+|total\s+|corporate\s+|overall\s+)*(?:workforce|staff|employees|jobs|headcount|work\s+force|employee\s+base|team)", re.I)

KEYWORD = re.compile(r"(?i)lay(?:s|ing)?\s*off|laid off|layoff|job cuts|cut(?:s|ting)? .{0,30}(jobs|workforce|staff|employees|workers|positions|roles)|redundanc|workforce reduction|eliminat\w+ .{0,25}(jobs|positions|roles)|slash\w* .{0,20}(jobs|workforce|staff)|shed\w* .{0,20}jobs|axe\w* .{0,20}jobs|furlough")
ROUNDUP = re.compile(r"(?i)\b(tracking|tracker|list of|these companies|companies (?:that|which|cutting|laying)|and others|roundup|so far this year|all the (?:job|layoff)|biggest layoffs of|every company|here are|here's who|which companies|layoffs? this week|week in layoffs|hit this week|in history)\b")
NEGATIVE = re.compile(r"(?i)\b(block layoffs|blocks layoffs|no layoffs|without layoffs|rules? out|denies|won't lay|will not lay|avoid(?:s|ed)? layoffs|not planning|reverses?|rehir\w+|hiring spree|lawsuit|sued|sues|settlement)\b")
SPECULATIVE = re.compile(r"(?i)\b(reportedly|report says|sources say|sources said|considering|weighs|weighing|mulls|could|may|might|rumou?r|according to (?:a )?report|plans|planning|eyes|expected to)\b|\?|: report$")
# Numbers that describe the past or a multi-year target, not this event.
RETRO = re.compile(r"(?i)\b(in (?:the )?(?:past|last) (?:\w+ )?(?:years?|months?)|over (?:the )?(?:past|last)|in (?:two|three|four|five|six|seven|eight|ten|\d+) (?:years|months)|in (?:a|one|the) year|since 20\d\d|so far|last year|this year|in 20\d\d|in FY ?\d+|by (?:end of |the end of )?20\d\d|over (?:\w+ )?years|in total|total|cumulative|to date|years? of|over the years|end of (?:the )?decade|over the next (?:\w+ )?years|year-to-date|ytd)\b")
# Past tense without an auxiliary usually recaps an earlier round ("Amazon Laid Off 30,000 Workers While ...").
PAST_RECAP = re.compile(r"(?i)(?<!has )(?<!have )(?<!had )(?<!been )(?<!be )(?<!to )(?<!will )\b(laid off|slashed|eliminated|axed)\s+(?:about |around |roughly |nearly |over |more than )?\d")
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
u.s u.s. u.k u.k. newspaper newspapers publishers studios streaming hollywood mortgage xbox gaming contractors contractor district
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
                          r"holdings?|group|n\.a\.?|n\.v\.?|l\.p\.|lp|s\.a\.|ag|gmbh|se|nv|n\.v\.|bv|oyj|asa|pty|pte|/[a-z]{2}/?)$")


def clean_company(name):
    """Normalise a raw company string to a display name ('' if it is not a company)."""
    name = re.sub(r"&rsquo;|&#8217;", "’", name or "").strip(" ,.;:-–—'\"“”‘’")
    name = re.sub(r"\s+dba\s+.*$", "", name, flags=re.I)
    name = re.split(r"\s+[-–]\s+", name)[0]  # WARN site suffixes: "Intel Corporation - SC11"
    name = re.sub(r"^\S+-(?:owned|backed|based)\s+", "", name)
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
    while len(toks) > 1 and toks[-1].lower() in TRAIL_PLACE:
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


def refine(co, title_case, gazetteer):
    """Trim over-captured names: longest known prefix first, then break words in Title Case headlines."""
    toks = co.split()
    if len(toks) == 1:
        return co
    if gazetteer:
        for i in range(len(toks), 0, -1):
            if canonical_slug(" ".join(toks[:i])) in gazetteer:
                return " ".join(toks[:i])
    if title_case:
        for i, t in enumerate(toks[1:], 1):
            if t.lower().strip("'’") in BREAK:
                return " ".join(toks[:i])
    return co


def parse_count(s):
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
    if v < 3 or v > 500_000 or (1990 <= v <= 2035 and mult == 1 and "." not in s):
        return None
    return v


def numbers(text):
    m = NUM_CUTOFF.search(text)
    if m and m.start() > 15:
        text = text[: m.start()]
    if RETRO.search(text) or PAST_RECAP.search(text):
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


def extract_headline(title, text="", gazetteer=None):
    """Return dict(company, headcount, pct, kind, speculative, country, industry, method) or None."""
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
    hc, pct = numbers(t)
    full = f"{t} {text or ''}"
    kind = "buyout" if BUYOUT.search(t) and not re.search(VERB_STRICT, t) else "layoff"
    return {
        "company": co, "headcount": hc, "pct": pct, "kind": kind,
        "speculative": bool(SPECULATIVE.search(t)), "country": country_from_text(full),
        "industry": industry_from_text(full), "method": method,
    }


def claims_from_item(it, gazetteer=None, llm=None):
    """Turn a stored item row (dict with parsed meta) into a claim dict or None."""
    meta = it["meta"]
    w = TIER_WEIGHT[it["tier"]]
    if it["tier"] == "official":
        co = clean_company(meta.get("company", ""))
        if not co:
            return None
        return {"company": co, "headcount": meta.get("headcount"), "pct": meta.get("pct"), "kind": meta.get("kind", "layoff"),
                "date": it["published"], "country": meta.get("country"), "location": meta.get("location"),
                "industry": meta.get("industry"), "weight": w, "speculative": 0, "method": it["source"]}
    ex = extract_headline(it["title"], it.get("text", ""), gazetteer)
    if not ex and llm and KEYWORD.search(it["title"] or ""):
        ex = llm(it["title"], it.get("text", ""))
    if not ex:
        return None
    if ex.get("speculative"):
        w *= 0.6
    return {"company": ex["company"], "headcount": ex.get("headcount"), "pct": ex.get("pct"), "kind": ex.get("kind", "layoff"),
            "date": it["published"], "country": ex.get("country"), "location": None, "industry": ex.get("industry"),
            "weight": round(w, 3), "speculative": int(bool(ex.get("speculative"))), "method": ex.get("method", "llm")}
