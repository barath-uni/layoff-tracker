"""Share cards (1200x630 PNG) rendered with Pillow at build time."""
from PIL import Image, ImageDraw, ImageFont

from .config import BRAND
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
    pts = [(x, y + 19), (x + 8, y + 19), (x + 12, y + 7), (x + 19, y + 31), (x + 23, y + 17), (x + 27, y + 17)]
    draw.line(pts, fill=INK2, width=3, joint="curve")
    draw.ellipse((x + 26, y + 12, x + 36, y + 22), fill=ACCENT)
    draw.text((x + 46, y + 2), BRAND, font=font(600, 28), fill=INK)


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


def _wrap(text, f, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if f.getlength(t) <= max_w or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    return lines + ([cur] if cur else [])


def statement(path, lead, big, tail, meta, foot, story=False, rows=None, spark=None):
    """Post-ready card: "<lead>" / BIG / "<tail>". 1200x630 or a 1080x1920 story."""
    w, h = (1080, 1920) if story else (W, H)
    pad = 88 if story else 64
    im = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(im)
    brand(d, pad, 72 if story else 56)
    fr = font(500, 26 if story else 22)
    d.text((w - pad - fr.getlength(foot), (78 if story else 62)), foot, font=fr, fill=MUTED)
    y = 420 if story else 140
    fl = font(500, 64 if story else 40)
    for line in _wrap(lead, fl, w - 2 * pad)[:3]:
        d.text((pad, y), line, font=fl, fill=INK2)
        y += int(fl.size * 1.2)
    fb = fit(big, 600, 360 if story else 190, w - 2 * pad, tracking=-0.05)
    y += 10 if story else 0
    tracked(d, pad - 6, y, big, fb, ACCENT if not rows else INK, tracking=-0.05)
    y += int(fb.size * 1.08)
    ft = font(500, 64 if story else 40)
    for line in _wrap(tail, ft, w - 2 * pad)[:2]:
        d.text((pad, y), line, font=ft, fill=INK)
        y += int(ft.size * 1.2)
    y += 60 if story else 8
    if rows:
        fr2, fv = font(500, 44 if story else 26), font(600, 44 if story else 26)
        for name, val in rows[: (8 if story else 3)]:
            name = ellipsize(name, fr2, w - 2 * pad - 260)
            d.text((pad, y), name, font=fr2, fill=INK2)
            d.text((w - pad - fv.getlength(val), y), val, font=fv, fill=INK)
            y += int(fr2.size * 1.55)
            d.line((pad, y - 14, w - pad, y - 14), fill=GRID, width=1)
    elif spark and story:
        columns(d, (pad, y + 80, w - pad, y + 380), spark)
    fm = font(400, 32 if story else 22)
    d.text((pad, h - (150 if story else 44) - (0 if story else 0)), ellipsize(meta, fm, w - 2 * pad), font=fm, fill=MUTED)
    if story:
        d.text((pad, h - 96), "Every number links to its sources", font=font(400, 28), fill=MUTED)
    im.save(path, "PNG", optimize=True)
