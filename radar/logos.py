"""Company slug -> web domain (for favicon pins) and country name -> ISO code (for flags) and map name.

Curated on purpose: a guessed domain shows the wrong logo, which is worse than the monogram fallback.
"""

DOMAINS = {
    # big tech and software
    "amazon": "amazon.com", "amazon-fresh": "amazon.com", "google": "google.com", "microsoft": "microsoft.com",
    "meta": "meta.com", "apple": "apple.com", "netflix": "netflix.com", "oracle": "oracle.com", "intel": "intel.com",
    "ibm": "ibm.com", "salesforce": "salesforce.com", "cisco": "cisco.com", "qualcomm": "qualcomm.com", "dell": "dell.com",
    "hp": "hp.com", "hubspot": "hubspot.com", "workday": "workday.com", "ebay": "ebay.com", "paypal": "paypal.com",
    "adobe": "adobe.com", "amd": "amd.com", "nvidia": "nvidia.com", "micron": "micron.com", "autodesk": "autodesk.com",
    "atlassian": "atlassian.com", "automattic": "automattic.com", "cloudflare": "cloudflare.com", "crowdstrike": "crowdstrike.com",
    "intuit": "intuit.com", "servicenow": "servicenow.com", "snap": "snap.com", "snapchat": "snap.com", "spotify": "spotify.com",
    "pinterest": "pinterest.com", "linkedin": "linkedin.com", "zoom": "zoom.us", "x": "x.com", "tiktok": "tiktok.com",
    "bytedance": "bytedance.com", "openai": "openai.com", "uber": "uber.com", "uber-technologies": "uber.com", "lyft": "lyft.com",
    "block": "block.xyz", "coinbase": "coinbase.com", "coinbase-global": "coinbase.com", "robinhood": "robinhood.com",
    "chime-financial": "chime.com", "gitlab": "gitlab.com", "freshworks": "freshworks.com", "sprout-social": "sproutsocial.com",
    "zoominfo-technologies": "zoominfo.com", "ukg": "ukg.com", "airtable": "airtable.com", "etsy": "etsy.com", "groupon": "groupon.com",
    "expedia": "expedia.com", "angi": "angi.com", "chegg": "chegg.com", "headspace": "headspace.com", "patreon": "patreon.com",
    "elementor": "elementor.com", "flock-safety": "flocksafety.com", "magic-leap": "magicleap.com", "gopro": "gopro.com",
    "enphase-energy": "enphase.com", "fico": "fico.com", "fair-isaac": "fico.com", "innodata": "innodata.com", "amdocs": "amdocs.com",
    "wisetech": "wisetechglobal.com", "asml": "asml.com", "applied-materials": "appliedmaterials.com", "texas-instruments": "ti.com",
    "sap": "sap.com", "nokia": "nokia.com", "ericsson": "ericsson.com", "samsung": "samsung.com", "sony": "sony.com",
    "panasonic": "panasonic.com", "philips": "philips.com", "siemens": "siemens.com", "bosch": "bosch.com", "rivian": "rivian.com",
    "tesla": "tesla.com", "formfactor": "formfactor.com", "daktronics": "daktronics.com", "leidos": "leidos.com", "peraton": "peraton.com",
    "echostar": "echostar.com", "rtx": "rtx.com", "boeing": "boeing.com",
    # games and media
    "ea": "ea.com", "electronic-arts": "ea.com", "epic-games": "epicgames.com", "ubisoft": "ubisoft.com",
    "sucker-punch": "suckerpunch.com", "zenimax-media": "zenimax.com", "zenimax-online-studios": "zenimax.com",
    "bungie-inc-sony-interactive-entertainment": "bungie.net", "funcom": "funcom.com", "disney": "disney.com",
    "paramount": "paramount.com", "skydance": "skydance.com", "warner-bros-discovery": "wbd.com", "warner-music-group": "wmg.com",
    "universal-music-group": "universalmusic.com", "comcast": "comcast.com", "bbc": "bbc.co.uk", "channel-4": "channel4.com",
    "telegraph": "telegraph.co.uk", "washington-post": "washingtonpost.com", "pittsburgh-post-gazette": "post-gazette.com",
    "wpp": "wpp.com", "flutter-entertainment": "flutter.com", "arsenal": "arsenal.com", "beachbody": "beachbody.com",
    # consulting and services
    "accenture": "accenture.com", "cognizant": "cognizant.com", "capgemini": "capgemini.com", "deloitte": "deloitte.com",
    "ey": "ey.com", "kpmg": "kpmg.com", "pwc": "pwc.com", "mckinsey": "mckinsey.com", "infosys": "infosys.com", "tcs": "tcs.com",
    "wipro": "wipro.com", "hcltech": "hcltech.com", "tech-mahindra": "techmahindra.com", "sodexo": "sodexo.com",
    "aramark-campus": "aramark.com", "compass-group-usa": "compass-usa.com", "cbre-government-defense-services": "cbre.com",
    "amentum": "amentum.com", "battelle": "battelle.org", "general-dynamics-information-technology": "gdit.com",
    # finance
    "american-express": "americanexpress.com", "barclays": "barclays.com", "blackrock": "blackrock.com", "citigroup": "citi.com",
    "jpmorgan": "jpmorganchase.com", "morgan-stanley": "morganstanley.com", "goldman-sachs": "goldmansachs.com",
    "bank-of-america": "bankofamerica.com", "wells-fargo": "wellsfargo.com", "hsbc": "hsbc.com", "ubs": "ubs.com",
    "deutsche-bank": "db.com", "commerzbank": "commerzbank.com", "standard-chartered": "sc.com", "visa": "visa.com",
    "mastercard": "mastercard.com", "nab": "nab.com.au", "cba": "commbank.com.au", "westpac": "westpac.com.au",
    "legal-general": "legalandgeneral.com", "nationwide": "nationwide.com", "pnc": "pnc.com", "pnc-bank-na": "pnc.com",
    "fifth-third-bank": "53.com", "icici-bank": "icicibank.com", "city-national-bank": "cnb.com",
    # retail, consumer, food
    "walmart": "walmart.com", "target": "target.com", "kroger": "kroger.com", "starbucks": "starbucks.com", "nike": "nike.com",
    "mcdonalds": "mcdonalds.com", "pepsico": "pepsico.com", "nestle": "nestle.com", "unilever": "unilever.com",
    "procter-gamble": "pg.com", "heineken": "heineken.com", "diageo": "diageo.com", "british-american-tobacco": "bat.com",
    "morrisons": "morrisons.com", "ocado": "ocado.com", "saks": "saksfifthavenue.com", "saks-fifth-avenue": "saksfifthavenue.com",
    "walgreens": "walgreens.com", "safeway": "safeway.com", "co-op": "coop.co.uk", "whirlpool": "whirlpool.com",
    "church-dwight": "churchdwight.com", "tyson-foods-inc-updated": "tysonfoods.com", "jack-in-the-box": "jackinthebox.com",
    "true-food-kitchen": "truefoodkitchen.com", "blue-diamond-growers": "bluediamond.com", "amy-s-kitchen": "amys.com",
    "bumble-bee-foods": "bumblebee.com", "monterey-mushrooms": "montereymushrooms.com", "mission-produce": "missionproduce.com",
    "campbell-soup-supply": "campbellsoupcompany.com", "jacuzzi": "jacuzzi.com", "pep-boys-manny-moe-jack": "pepboys.com",
    "ashley-furniture-industries": "ashleyfurniture.com", "thriftbooks-global": "thriftbooks.com",
    # telecom
    "at-t": "att.com", "verizon": "verizon.com", "t-mobile": "t-mobile.com", "t-mobile-usa": "t-mobile.com", "bt": "bt.com",
    "vodafone": "vodafone.com", "telstra": "telstra.com.au", "telia": "telia.se",
    # auto, industry, energy
    "volkswagen": "volkswagen.com", "bmw": "bmw.com", "audi": "audi.com", "porsche": "porsche.com", "mercedes-benz": "mercedes-benz.com",
    "ford": "ford.com", "general-motors": "gm.com", "stellantis": "stellantis.com", "renault": "renault.com", "nissan": "nissan-global.com",
    "honda": "honda.com", "toyota": "toyota.com", "byd": "byd.com", "volvo-cars": "volvocars.com", "jaguar-land-rover": "jaguarlandrover.com",
    "continental": "continental.com", "aumovio": "aumovio.com", "zf": "zf.com", "autoliv": "autoliv.com",
    "goodyear-tire-rubber": "goodyear.com", "thyssenkrupp": "thyssenkrupp.com", "us-steel": "ussteel.com", "stelco": "stelco.com",
    "dow": "dow.com", "shell": "shell.com", "bp": "bp.com", "exxonmobil": "exxonmobil.com", "chevron": "chevron.com",
    "conocophillips": "conocophillips.com", "phillips-66": "phillips66.com", "baker-hughes": "bakerhughes.com", "mosaic": "mosaicco.com",
    "corteva-agriscience": "corteva.com", "enersys": "enersys.com", "eos-energy-storage": "eose.com", "woodward": "woodward.com",
    "cemex": "cemex.com", "vale-base-metals": "vale.com", "haas-automation": "haascnc.com",
    # transport and logistics
    "ups": "ups.com", "fedex": "fedex.com", "royal-mail": "royalmail.com", "db-cargo": "dbcargo.com", "lufthansa": "lufthansa.com",
    "air-canada": "aircanada.com", "southwest-airlines": "southwest.com", "spirit-airlines-may-2026": "spirit.com",
    "hawaiian-airlines": "hawaiianairlines.com", "menzies-aviation": "menziesaviation.com", "geodis-logistics": "geodis.com",
    "lineage-logistics": "onelineage.com", "dsv-contract-logistics": "dsv.com", "first-student": "firststudentinc.com",
    "expeditors-international-of-washington": "expeditors.com", "skyguide": "skyguide.ch",
    # health and pharma
    "pfizer": "pfizer.com", "merck": "merck.com", "novartis": "novartis.com", "novo-nordisk": "novonordisk.com", "sanofi": "sanofi.com",
    "gsk": "gsk.com", "bayer": "bayer.com", "bristol-myers-squibb": "bms.com", "johnson-johnson": "jnj.com",
    "takeda-pharmaceuticals": "takeda.com", "biomarin-pharmaceutical": "biomarin.com", "unitedhealth": "unitedhealthgroup.com",
    "cvs-health": "cvshealth.com", "cvs-health-aetna": "cvshealth.com", "kaiser-permanente": "kaiserpermanente.org",
    "kaiser-foundation-hospitals-and-kaiser-foundation-health": "kaiserpermanente.org", "mass-general-brigham": "massgeneralbrigham.org",
    "upmc": "upmc.com", "trinity-health": "trinity-health.org", "peacehealth": "peacehealth.org", "city-of-hope": "cityofhope.org",
    "providence-health-services": "providence.org", "unitypoint-health": "unitypoint.org", "becton-dickinson-and": "bd.com",
    "azenta": "azenta.com", "vertex": "vrtx.com",
    # education and public
    "chicago-public-schools": "cps.edu", "ulster-university": "ulster.ac.uk", "dundee-university": "dundee.ac.uk",
}

# Event country names (as stored) -> (ISO 3166 alpha-2, name in world-atlas countries-110m)
COUNTRIES = {
    "United States": ("US", "United States of America"), "United Kingdom": ("GB", "United Kingdom"),
    "Germany": ("DE", "Germany"), "France": ("FR", "France"), "Netherlands": ("NL", "Netherlands"), "Sweden": ("SE", "Sweden"),
    "Finland": ("FI", "Finland"), "Denmark": ("DK", "Denmark"), "Norway": ("NO", "Norway"), "Belgium": ("BE", "Belgium"),
    "Switzerland": ("CH", "Switzerland"), "Austria": ("AT", "Austria"), "Italy": ("IT", "Italy"), "Spain": ("ES", "Spain"),
    "Portugal": ("PT", "Portugal"), "Ireland": ("IE", "Ireland"), "Poland": ("PL", "Poland"), "Czechia": ("CZ", "Czechia"),
    "Czech Republic": ("CZ", "Czechia"), "Hungary": ("HU", "Hungary"), "Romania": ("RO", "Romania"), "Greece": ("GR", "Greece"),
    "Turkey": ("TR", "Turkey"), "Israel": ("IL", "Israel"), "United Arab Emirates": ("AE", "United Arab Emirates"),
    "Saudi Arabia": ("SA", "Saudi Arabia"), "Egypt": ("EG", "Egypt"), "South Africa": ("ZA", "South Africa"),
    "Nigeria": ("NG", "Nigeria"), "Kenya": ("KE", "Kenya"), "India": ("IN", "India"), "Pakistan": ("PK", "Pakistan"),
    "China": ("CN", "China"), "Hong Kong": ("HK", "China"), "Taiwan": ("TW", "Taiwan"), "Japan": ("JP", "Japan"),
    "South Korea": ("KR", "South Korea"), "Singapore": ("SG", None), "Malaysia": ("MY", "Malaysia"), "Indonesia": ("ID", "Indonesia"),
    "Philippines": ("PH", "Philippines"), "Vietnam": ("VN", "Vietnam"), "Thailand": ("TH", "Thailand"),
    "Australia": ("AU", "Australia"), "New Zealand": ("NZ", "New Zealand"), "Canada": ("CA", "Canada"), "Mexico": ("MX", "Mexico"),
    "Brazil": ("BR", "Brazil"), "Argentina": ("AR", "Argentina"), "Chile": ("CL", "Chile"), "Colombia": ("CO", "Colombia"),
    "Luxembourg": ("LU", "Luxembourg"), "Estonia": ("EE", "Estonia"), "Ukraine": ("UA", "Ukraine"), "Russia": ("RU", "Russia"),
}


def domain(slug):
    return DOMAINS.get(slug)


def iso(country):
    return (COUNTRIES.get(country) or (None, None))[0]


def map_name(country):
    return (COUNTRIES.get(country) or (None, None))[1]
