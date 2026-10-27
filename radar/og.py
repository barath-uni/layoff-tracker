"""Share cards (1200x630 PNG) rendered with Pillow at build time."""
from PIL import Image, ImageDraw, ImageFont

from .util import ASSETS

W, H = 1200, 630
BG, INK, INK2, MUTED, GRID, ACCENT = "#0d0d0d", "#f0efec", "#c3c2b7", "#898781", "#2c2c2a", "#e66767"
_fonts = {}


def font(weight, size):
    k = (weight, size)
    if k not in _fonts:
        _fonts[k] = ImageFont.truetype(str(ASSETS / "fonts" / f"geist-{weight}.ttf"), size)
    return _fonts[k]


def tracked(draw, x, y, text, f, fill, tracking=0.0):
    for ch in text:
        draw.text((x, y), ch, font=f, fill=fill)
        x += f.getlength(ch) + tracking * f.size
    return x


def tracked_len(text, f, tracking=0.0):
    return sum(f.getlength(ch) + tracking * f.size for ch in text)


def fit(text, weight, size, max_w, tracking=0.0, min_size=60):
    while size > min_size and tracked_len(text, font(weight, size), tracking) > max_w:
        size -= 4
    return font(weight, size)


def ellipsize(text, f, max_w):
    if f.getlength(text) <= max_w:
        return text
    while text and f.getlength(text + "…") > max_w:
        text = text[:-1]
    return text.rstrip(" ,.;:") + "…"


def brand(draw, x, y):
    draw.arc((x, y, x + 34, y + 34), 200, 340, fill=INK2, width=3)
    draw.arc((x + 7, y + 7, x + 27, y + 27), 200, 340, fill=INK2, width=3)
    draw.ellipse((x + 13, y + 13, x + 21, y + 21), fill=ACCENT)
    draw.text((x + 46, y + 2), "layoff-radar", font=font(600, 28), fill=INK)


def columns(draw, box, values):
    x0, y0, x1, y1 = box
    vmax = max(values or [1]) or 1
    slot = (x1 - x0) / max(len(values), 1)
    bw = max(3, min(18, slot * 0.62))
    draw.line((x0, y1, x1, y1), fill=GRID, width=1)
    for i, v in enumerate(values):
        h = (y1 - y0) * v / vmax
        if h >= 2:
            cx = x0 + slot * i + (slot - bw) / 2
            draw.rounded_rectangle((cx, y1 - h, cx + bw, y1), radius=int(min(4, bw / 2, h / 2)),
                                   fill=ACCENT if i >= len(values) - 4 else "#7a3b3b", corners=(True, True, False, False))


def card(path, eyebrow, number, subline, footer_right, spark=None, quote=None):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    brand(d, 64, 56)
    fr = font(500, 22)
    d.text((W - 64 - fr.getlength(footer_right), 62), footer_right, font=fr, fill=MUTED)
    d.text((64, 150), ellipsize(eyebrow, font(500, 34), W - 128), font=font(500, 34), fill=INK2)
    fnum = fit(number, 600, 200, W - 128, tracking=-0.05)
    tracked(d, 58, 196 + (200 - fnum.size) * 0.55, number, fnum, INK, tracking=-0.05)
    d.text((64, 428), ellipsize(subline, font(400, 28), W - 128), font=font(400, 28), fill=INK2)
    if quote:
        fq = font(400, 24)
        d.text((64, 500), ellipsize(f"“{quote}”", fq, W - 128), font=fq, fill=MUTED)
    elif spark:
        columns(d, (64, 490, W - 64, 560), spark)
    d.text((64, H - 44), "Every number links to its sources", font=font(400, 19), fill=MUTED)
    im.save(path, "PNG", optimize=True)
