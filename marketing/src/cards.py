"""Marketing cards (PNG) from marketing/data/numbers.json. Pillow only.

python3 marketing/src/cards.py [a b c d e f]   ->  marketing/images/*.png
Rendered at 2x and downsampled for crisp dots and text.
"""
import json, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = Path(__file__).resolve().parent.parent
FONTS = HERE.parent / "assets/fonts"
OUT = HERE / "images"
N = json.loads((HERE / "data/numbers.json").read_text())
T = N["totals"]
SS = 2  # supersample

BG = (11, 11, 12)
INK = (242, 239, 233)
INK2 = (176, 172, 166)
MUTED = (112, 109, 105)
LINE = (38, 37, 36)
RED = (255, 64, 46)
URL = "layoff-tracker.pages.dev"


def font(w, px):
    return ImageFont.truetype(str(FONTS / f"geist-{w}.ttf"), int(px * SS))


def fmt(n):
    return f"{n:,}"


def daterange():
    from datetime import date
    a, b = date.fromisoformat(N["window_from"]), date.fromisoformat(N["window_to"])
    return f"{a:%-d %b} – {b:%-d %b %Y}".upper()


class Card:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.im = Image.new("RGB", (w * SS, h * SS), BG)
        self.d = ImageDraw.Draw(self.im)
        self._texture()

    def _texture(self):
        # faint dot grid + soft vignette: editorial, not flat
        g = 22 * SS
        for y in range(g // 2, self.h * SS, g):
            for x in range(g // 2, self.w * SS, g):
                self.d.ellipse([x - SS, y - SS, x + SS, y + SS], fill=(22, 22, 23))
        v = Image.new("L", (self.w // 8, self.h // 8), 0)
        vd = ImageDraw.Draw(v)
        vd.ellipse([-self.w // 16, -self.h // 16, self.w // 8 + self.w // 16, self.h // 8 + self.h // 16], fill=255)
        v = v.filter(ImageFilter.GaussianBlur(self.w // 60)).resize(self.im.size)
        dark = Image.new("RGB", self.im.size, (6, 6, 7))
        self.im = Image.composite(self.im, dark, v)
        self.d = ImageDraw.Draw(self.im)

    def text(self, xy, s, f, fill=INK, anchor="la", track=0):
        x, y = xy[0] * SS, xy[1] * SS
        if not track:
            self.d.text((x, y), s, font=f, fill=fill, anchor=anchor)
            return self.d.textlength(s, font=f) / SS
        total = sum(self.d.textlength(c, font=f) for c in s) + track * SS * (len(s) - 1)
        if anchor[0] == "r":
            x -= total
        elif anchor[0] == "m":
            x -= total / 2
        asc, desc = f.getmetrics()
        y = {"t": y + asc, "m": y + (asc - desc) / 2, "s": y, "b": y - desc}[anchor[1]] if anchor[1] in "tmsb" else y
        for c in s:
            self.d.text((x, y), c, font=f, fill=fill, anchor="ls")
            x += self.d.textlength(c, font=f) + track * SS
        return total / SS

    def tl(self, s, f):
        return self.d.textlength(s, font=f) / SS

    def rect(self, box, fill, r=0):
        b = [v * SS for v in box]
        if r:
            self.d.rounded_rectangle(b, r * SS, fill=fill)
        else:
            self.d.rectangle(b, fill=fill)

    def dot(self, x, y, r, fill):
        self.d.ellipse([(x - r) * SS, (y - r) * SS, (x + r) * SS, (y + r) * SS], fill=fill)

    def glow(self, x, y, r, color=RED, alpha=70):
        layer = Image.new("RGB", self.im.size, (0, 0, 0))
        ld = ImageDraw.Draw(layer)
        ld.ellipse([(x - r) * SS, (y - r) * SS, (x + r) * SS, (y + r) * SS], fill=tuple(int(c * alpha / 255) for c in color))
        layer = layer.filter(ImageFilter.GaussianBlur(r * SS / 2))
        from PIL import ImageChops
        self.im = ImageChops.add(self.im, layer)
        self.d = ImageDraw.Draw(self.im)

    def header(self, m, kicker):
        s = 15 if self.w >= 1600 else 14
        self.dot(m + 5, m + 9, 5, RED)
        self.text((m + 20, m + 9), "LAYOFF TRACKER", font(700, s), INK, "lm", track=2.2)
        self.text((self.w - m, m + 9), kicker, font(500, s), MUTED, "rm", track=1.8)

    def footer(self, m, note):
        y = self.h - m
        self.rect((m, y - 34, self.w - m, y - 33), LINE)
        self.text((m, y), note, font(400, 14 if self.w >= 1080 else 13), MUTED, "ls")
        self.text((self.w - m, y), URL, font(600, 17), INK, "rs", track=0.5)

    def save(self, name):
        OUT.mkdir(parents=True, exist_ok=True)
        self.im.resize((self.w, self.h), Image.LANCZOS).save(OUT / name, optimize=True)
        print("wrote", OUT / name)


SRC_NOTE = "Verified = official filing / WARN notice, or 2+ independent reports. Snapshot " + N["today"]


def fit(c, s, w, maxpx, minpx=40):
    px = maxpx
    while px > minpx and c.tl(s, font(700, px)) > w:
        px -= 4
    return px


def dot_grid(c, dots, gx0, gx1, gy0, gy1, nred, red_name, align="l"):
    """One dot = 100 people. The last nred dots are red (the biggest single layoff)."""
    import math
    W, H = gx1 - gx0, gy1 - gy0
    cols = max(8, round(math.sqrt(dots * W / H)))
    rows = -(-dots // cols)
    cell = min(W / cols, H / rows)
    ox = gx1 - cols * cell if align == "r" else gx0 if align == "l" else gx0 + (W - cols * cell) / 2
    oy = gy0
    for i in range(dots):
        rr, cc = divmod(i, cols)
        red = i >= dots - nred
        c.dot(ox + cc * cell + cell / 2, oy + rr * cell + cell / 2, cell * 0.27, RED if red else (150, 146, 140))
    ly = oy + rows * cell + 26
    c.dot(ox + cell / 2, ly, cell * 0.27, (150, 146, 140))
    x = ox + cell + 8
    x += c.text((x, ly), "= 100 people", font(500, 16), MUTED, "lm") + 26
    c.dot(x, ly, cell * 0.27, RED)
    c.text((x + cell / 2 + 8, ly), red_name + ", the biggest", font(500, 16), MUTED, "lm")


# ---------- (a) 30-day number card ----------
def card_a(w, h):
    c = Card(w, h)
    m = 64 if w >= 1600 else 60
    c.header(m, "LAST 30 DAYS · VERIFIED")
    n = T["people_30d"]
    dots = round(n / 100)
    tall = h > w
    big = fmt(n)
    top = N["companies_top10_30d"][0]
    if not tall:
        px = fit(c, big, 800, 236)
        y0 = 370
        c.text((m - 8, y0), big, font(700, px), INK, "ls")
        c.text((m, y0 + 82), "people laid off in the last 30 days.", font(500, 40), INK, "ls")
        c.text((m, y0 + 134), "That's ", font(500, 40), INK2, "ls")
        x = m + c.tl("That's ", font(500, 40))
        c.text((x, y0 + 134), f"{T['per_hour_30d']} an hour.", font(700, 40), RED, "ls")
        stats_y, gx0, gx1, gy0, gy1 = h - m - 170, 1000, w - m, 190, h - m - 120
    else:
        px = fit(c, big, w - 2 * m, 260)
        y0 = 330
        c.text((m - 8, y0), big, font(700, px), INK, "ls")
        c.text((m, y0 + 96), "people laid off in the last 30 days.", font(500, 42), INK, "ls")
        c.text((m, y0 + 152), "That's ", font(500, 42), INK2, "ls")
        x = m + c.tl("That's ", font(500, 42))
        c.text((x, y0 + 152), f"{T['per_hour_30d']} an hour.", font(700, 42), RED, "ls")
        stats_y, gx0, gx1, gy0, gy1 = h - m - 160, m, w - m, y0 + 230, h - m - 300
    dot_grid(c, dots, gx0, gx1, gy0, gy1, round(top["people"] / 100), top["name"], align="r" if not tall else "l")
    # stat row
    if not tall:
        stats = [(fmt(T["events_30d"]), "verified layoffs"), (fmt(top["people"]), "biggest: " + top["name"]),
                 ("hourly", "updates")]
        sx = m
        c.rect((m, stats_y - 34, 900, stats_y - 33), LINE)
        for v, l in stats:
            c.text((sx, stats_y + 28), v, font(700, 44), INK, "ls")
            c.text((sx, stats_y + 62), l, font(500, 17), MUTED, "ls")
            sx += 280
    else:
        stats = [(fmt(T["events_30d"]), "verified layoffs"), (fmt(top["people"]), "biggest: AmEx"), ("hourly", "updates")]
        sx = m
        c.rect((m, stats_y - 36, w - m, stats_y - 35), LINE)
        for v, l in stats:
            c.text((sx, stats_y + 30), v, font(700, 48), INK, "ls")
            c.text((sx, stats_y + 66), l, font(500, 18), MUTED, "ls")
            sx += (w - 2 * m) / 3
    c.footer(m, SRC_NOTE if not tall else "Verified events only · snapshot " + N["today"])
    return c


# ---------- bar list helper ----------
def bars(c, rows, x0, x1, y0, y1, hl=None, label_w=None, numfmt=fmt, sub=None):
    n = len(rows)
    step = (y1 - y0) / n
    vmax = max(v for _, v in rows)
    fs = min(30, step * 0.42)
    lw = label_w or max(c.tl(l, font(500, fs)) for l, _ in rows) + 28
    numw = c.tl(numfmt(vmax), font(700, fs)) + 24
    bx0, bx1 = x0 + lw, x1 - numw
    bh = max(6, min(14, step * 0.22))
    for i, (l, v) in enumerate(rows):
        cy = y0 + step * i + step / 2
        on = (hl is not None and (l == hl or i == hl))
        c.text((x0, cy), l, font(600 if on else 500, fs), INK if on else INK2, "lm")
        if sub and sub[i]:
            pass
        c.rect((bx0, cy - bh / 2, bx1, cy + bh / 2), (26, 26, 27), r=bh / 2)
        bw = max(bh, (bx1 - bx0) * v / vmax)
        c.rect((bx0, cy - bh / 2, bx0 + bw, cy + bh / 2), RED if on else (214, 210, 204), r=bh / 2)
        c.text((x1, cy), numfmt(v), font(700, fs), RED if on else INK, "rm")
    return lw


# ---------- (b) industries ----------
def card_b(w, h):
    c = Card(w, h)
    tall = h > w
    m = 64 if not tall else 60
    c.header(m, "LAST 3 MONTHS · " + daterange())
    tech = N["tech"]
    rows = [(r["name"].replace("Media & Entertainment", "Media & Entertainment"), r["people"]) for r in N["industries_named"]]
    other = next(r for r in N["industries"] if r["name"] == "Other")["people"]
    if not tall:
        c.text((m, 180), "Not a tech story", font(700, 74), INK, "ls")
        c.text((m, 262), "anymore.", font(700, 74), INK, "ls")
        c.text((m - 6, 560), f"{tech['share']}%", font(700, 230), RED, "ls")
        c.text((m, 616), "of people laid off worked in tech.", font(500, 34), INK, "ls")
        c.text((m, 662), f"Finance cut more: {fmt(T['finance_people'])} vs {fmt(tech['people'])}.", font(500, 34), INK2, "ls")
        c.text((880, 150), "PEOPLE LAID OFF, BY INDUSTRY", font(600, 15), MUTED, "lt", track=1.8)
        bars(c, rows, 880, w - m, 190, 620, hl="Technology")
        c.text((880, 668), f"+ {fmt(other)} more in sectors not tagged to one industry:", font(500, 19), MUTED, "ls")
        c.text((880, 696), "farms, chemicals, steel, supermarkets.", font(500, 19), MUTED, "ls")
    else:
        c.text((m, 205), "Not a tech story", font(700, 76), INK, "ls")
        c.text((m, 290), "anymore.", font(700, 76), INK, "ls")
        c.text((m - 6, 560), f"{tech['share']}%", font(700, 250), RED, "ls")
        c.text((m, 620), "of people laid off worked in tech.", font(500, 36), INK, "ls")
        c.text((m, 668), f"Finance cut more: {fmt(T['finance_people'])} vs {fmt(tech['people'])}.", font(500, 36), INK2, "ls")
        c.text((m, 760), "PEOPLE LAID OFF, BY INDUSTRY", font(600, 15), MUTED, "lt", track=1.8)
        bars(c, rows, m, w - m, 790, 1130, hl="Technology")
        c.text((m, 1180), f"+ {fmt(other)} more not tagged to one industry", font(500, 20), MUTED, "ls")
        c.text((m, 1208), "(farms, chemicals, steel, supermarkets).", font(500, 20), MUTED, "ls")
    c.footer(m, SRC_NOTE if not tall else "Verified events only · snapshot " + N["today"])
    return c


# ---------- (c) top 10 companies ----------
def card_c(w, h):
    c = Card(w, h)
    tall = h > w
    m = 64 if not tall else 60
    c.header(m, "LAST 3 MONTHS · " + daterange())
    rows = [(r["name"], r["people"]) for r in N["companies_top10"]]
    top = N["companies_top10"][0]
    if not tall:
        c.text((m, 190), "Who cut", font(700, 84), INK, "ls")
        c.text((m, 280), "the most people.", font(700, 84), INK, "ls")
        c.text((m - 4, 560), fmt(top["people"]), font(700, 190), RED, "ls")
        c.text((m, 636), f"{top['name']}, #1. A bank, not a tech giant.", font(500, 30), INK, "ls")
        c.text((m, 678), "Top 10 by people, verified events only.", font(500, 24), MUTED, "ls")
        bars(c, rows, 820, w - m, 140, h - m - 70, hl=0)
    else:
        c.text((m, 200), "Who cut the", font(700, 80), INK, "ls")
        c.text((m, 288), "most people.", font(700, 80), INK, "ls")
        c.text((m, 340), "Top 10 companies by people laid off, verified only.", font(500, 26), MUTED, "ls")
        bars(c, rows, m, w - m, 400, 1060, hl=0)
        c.rect((m, 1110, w - m, 1111), LINE)
        c.text((m - 4, 1225), fmt(top["people"]), font(700, 120), RED, "ls")
        c.text((m + c.tl(fmt(top['people']), font(700, 120)) + 24, 1180), f"at {top['name']}.", font(600, 32), INK, "ls")
        c.text((m + c.tl(fmt(top['people']), font(700, 120)) + 24, 1220), "A bank. Not a tech giant.", font(500, 28), INK2, "ls")
    c.footer(m, SRC_NOTE if not tall else "Verified events only · snapshot " + N["today"])
    return c


# ---------- (d) countries ----------
def card_d(w, h):
    c = Card(w, h)
    tall = h > w
    m = 64 if not tall else 60
    c.header(m, "LAST 3 MONTHS · " + daterange())
    rows = [(r["name"], r["people"]) for r in N["countries_top10"]]
    share = round(T["non_us_share"])
    if not tall:
        c.text((m - 8, 380), f"{share}%", font(700, 300), RED, "ls")
        c.text((m, 446), "of people laid off are", font(600, 44), INK, "ls")
        c.text((m, 500), "outside the United States.", font(600, 44), INK, "ls")
        c.text((m, 580), f"{T['countries']} countries. {fmt(T['people'])} people.", font(500, 28), INK2, "ls")
        c.text((m, 618), "Most trackers only watch the US.", font(500, 28), MUTED, "ls")
        c.text((900, 140), "PEOPLE LAID OFF, TOP 10 COUNTRIES", font(600, 15), MUTED, "lt", track=1.8)
        bars(c, rows, 900, w - m, 175, h - m - 70)
    else:
        c.text((m - 8, 420), f"{share}%", font(700, 330), RED, "ls")
        c.text((m, 490), "of people laid off are", font(600, 46), INK, "ls")
        c.text((m, 546), "outside the United States.", font(600, 46), INK, "ls")
        c.text((m, 610), f"{T['countries']} countries · {fmt(T['people'])} people · 3 months", font(500, 26), INK2, "ls")
        c.text((m, 690), "PEOPLE LAID OFF, TOP 10 COUNTRIES", font(600, 15), MUTED, "lt", track=1.8)
        bars(c, rows, m, w - m, 720, h - m - 80)
    c.footer(m, SRC_NOTE if not tall else "Verified events only · snapshot " + N["today"])
    return c


# ---------- (e) "massive" ----------
PICK = [("Ninja Theory", "despidos masivos"), ("BMW", "Massiver Stellenabbau"), ("Halo Studios", "despidos masivos"),
        ("Adidas", "Massive Layoffs"), ("NAB", "massive restructure"), ("Uber", "despidos masivos")]


def massive_rows():
    by = {r["company"]: r for r in N["massive_headlines"]}
    out = []
    for comp, phrase in PICK:
        r = by[comp]
        assert phrase.lower() in r["title"].lower(), (comp, phrase)
        out.append((f"“{phrase}”", r["publisher"], comp, r["headcount"]))
    return out


def card_e(w, h):
    c = Card(w, h)
    tall = h > w
    m = 64 if not tall else 60
    c.header(m, "LAST 3 MONTHS · " + daterange())
    rows = massive_rows()
    med = T["median_layoff"]
    if not tall:
        c.text((m, 180), "Headlines say ‘massive’.", font(700, 58), INK, "ls")
        c.text((m, 250), "Here’s the number.", font(700, 58), INK2, "ls")
        c.text((m - 8, 600), str(med), font(700, 300), RED, "ls")
        c.text((m, 660), "people: the median verified layoff.", font(600, 34), INK, "ls")
        c.text((m, 702), f"Across {T['events_with_headcount']} layoffs with a disclosed headcount.", font(500, 24), MUTED, "ls")
        x0, x1, y0, y1 = 860, w - m, 150, h - m - 80
    else:
        c.text((m, 185), "Headlines say ‘massive’.", font(700, 62), INK, "ls")
        c.text((m, 257), "Here’s the number.", font(700, 62), INK2, "ls")
        x0, x1, y0, y1 = m, w - m, 320, 850
    c.text((x0, y0), "THE HEADLINE SAID", font(600, 14), MUTED, "lt", track=1.8)
    c.text((x1, y0), "PEOPLE", font(600, 14), MUTED, "rt", track=1.8)
    step = (y1 - y0 - 30) / len(rows)
    for i, (q, pub, comp, n) in enumerate(rows):
        cy = y0 + 30 + step * i + step / 2
        c.rect((x0, cy - step / 2, x1, cy - step / 2 + 1), LINE)
        c.text((x0, cy - 4), q, font(600, 28), INK, "ls")
        c.text((x0, cy + 26), f"{pub} on {comp}", font(500, 17), MUTED, "ls")
        c.text((x1, cy + 10), fmt(n), font(700, 46), INK, "rm")
    if tall:
        c.rect((m, 880, w - m, 881), LINE)
        c.text((m - 8, 1120), str(med), font(700, 250), RED, "ls")
        c.text((m, 1172), "people: the median verified layoff.", font(600, 34), INK, "ls")
        c.text((m, 1212), f"Across {T['events_with_headcount']} layoffs with a disclosed headcount.", font(500, 24), MUTED, "ls")
    c.footer(m, SRC_NOTE if not tall else "Verified events only · snapshot " + N["today"])
    return c


# ---------- (f) 9:16 story of (a) ----------
def card_f(w=1080, h=1920):
    c = Card(w, h)
    m = 72
    c.header(m, "LAST 30 DAYS")
    n = T["people_30d"]
    c.text((m, 300), "In the last 30 days,", font(600, 54), INK2, "ls")
    px = fit(c, fmt(n), w - 2 * m, 300)
    c.glow(w / 2, 470, 260, alpha=40)
    c.text((m - 8, 560), fmt(n), font(700, px), INK, "ls")
    c.text((m, 664), "people were laid off.", font(600, 54), INK, "ls")
    c.text((m, 740), "That's ", font(600, 54), INK2, "ls")
    c.text((m + c.tl("That's ", font(600, 54)), 740), f"{T['per_hour_30d']} every hour.", font(700, 54), RED, "ls")
    dots = round(n / 100)
    top = N["companies_top10_30d"][0]
    dot_grid(c, dots, m, w - m, 790, 1400, round(top["people"] / 100), top["name"], align="c")
    y = 1500
    c.rect((m, y, w - m, y + 1), LINE)
    for i, (v, l) in enumerate([(fmt(T["events_30d"]), "verified layoffs"), (fmt(T["countries"]), "countries (3 mo)"), ("hourly", "updates")]):
        x = m + i * (w - 2 * m) / 3
        c.text((x, y + 80), v, font(700, 56), INK, "ls")
        c.text((x, y + 116), l, font(500, 22), MUTED, "ls")
    c.text((w / 2, h - 110), "Every layoff. One globe.", font(600, 30), INK2, "ms")
    c.text((w / 2, h - 64), URL, font(700, 36), INK, "ms", track=0.5)
    return c


JOBS = {
    "a": [("a-30day-1600x900.png", card_a, (1600, 900)), ("a-30day-1080x1350.png", card_a, (1080, 1350))],
    "b": [("b-industries-1600x900.png", card_b, (1600, 900)), ("b-industries-1080x1350.png", card_b, (1080, 1350))],
    "c": [("c-companies-1600x900.png", card_c, (1600, 900)), ("c-companies-1080x1350.png", card_c, (1080, 1350))],
    "d": [("d-countries-1600x900.png", card_d, (1600, 900)), ("d-countries-1080x1350.png", card_d, (1080, 1350))],
    "e": [("e-massive-1600x900.png", card_e, (1600, 900)), ("e-massive-1080x1350.png", card_e, (1080, 1350))],
    "f": [("f-30day-story-1080x1920.png", card_f, (1080, 1920))],
}

if __name__ == "__main__":
    for k in (sys.argv[1:] or JOBS):
        for name, fn, size in JOBS[k]:
            fn(*size).save(name)
