"""X profile assets for @LayoffTracker: header 1500x500, avatar 400 + 1024.

python3 marketing/src/profile.py  ->  marketing/profile/*.png (+ review sims)
"""
import json, math, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from video import land_points, xyz, rotate  # noqa: E402

HERE = Path(__file__).resolve().parent.parent
OUT = HERE / "profile"
FONTS = HERE.parent / "assets/fonts"
N = json.loads((HERE / "data/numbers.json").read_text())
BG = (11, 11, 12)
INK = (242, 239, 233)
INK2 = (176, 172, 166)
MUTED = (112, 109, 105)
RED = (255, 64, 46)


def font(w, px):
    return ImageFont.truetype(str(FONTS / f"geist-{w}.ttf"), int(px))


def globe(im, cx, cy, R, lon0, lat0, spacing, dot_scale, pins, S, rim=True, disc=(17, 17, 19), bright=1.0):
    d = ImageDraw.Draw(im, "RGBA")
    d.ellipse([cx - R, cy - R, cx + R, cy + R], fill=disc)
    if rim:
        d.ellipse([cx - R, cy - R, cx + R, cy + R], outline=(44, 43, 42), width=max(1, S))
    lat, lon = land_points(spacing)
    p = rotate(xyz(lat, lon), lon0, lat0)
    p = p[p[:, 2] > 0.02]
    for x, y, z in p:
        r = dot_scale * (0.5 + 0.5 * z)
        g = int((62 + 110 * z ** 0.8) * bright)
        X, Y = cx + x * R, cy - y * R
        d.ellipse([X - r, Y - r, X + r, Y + r], fill=(g, g - 2, g - 4))
    for la, lo, size in pins:
        q = rotate(xyz(np.array([la]), np.array([lo])), lon0, lat0)[0]
        if q[2] <= 0.05:
            continue
        X, Y = cx + q[0] * R, cy - q[1] * R
        for k, a in ((3.2, 40), (2.2, 90)):
            rr = size * k
            d.ellipse([X - rr, Y - rr, X + rr, Y + rr], outline=RED + (a,), width=max(1, int(S * 1.5)))
        d.ellipse([X - size, Y - size, X + size, Y + size], fill=RED)


def header():
    S = 2
    W, H = 1500, 500
    im = Image.new("RGB", (W * S, H * S), BG)
    d = ImageDraw.Draw(im)
    for y in range(11 * S, H * S, 22 * S):          # faint dot grid
        for x in range(11 * S, W * S, 22 * S):
            d.ellipse([x - S, y - S, x + S, y + S], fill=(21, 21, 22))
    # globe as a horizon on the right, cropped top and bottom
    pins = [(40.7, -74.0, 7 * S), (51.5, -0.1, 9 * S), (50.6, 9.0, 6 * S), (47.6, -122.3, 5 * S), (52.3, 4.9, 5 * S), (45.0, 10.0, 5 * S)]
    globe(im, 1300 * S, 300 * S, 340 * S, -22, 30, 1.25, 1.9 * S, pins, S)
    # fade the globe's left edge into the background so the text reads
    fade = Image.new("L", (W * S, H * S), 0)
    fd = ImageDraw.Draw(fade)
    for i in range(0, 300 * S):
        fd.line([(900 * S + i, 0), (900 * S + i, H * S)], fill=int(255 * (i / (300 * S)) ** 1.4))
    fd.rectangle([1200 * S, 0, W * S, H * S], fill=255)
    base = Image.new("RGB", im.size, BG)
    bd = ImageDraw.Draw(base)
    for y in range(11 * S, H * S, 22 * S):
        for x in range(11 * S, W * S, 22 * S):
            bd.ellipse([x - S, y - S, x + S, y + S], fill=(21, 21, 22))
    im = Image.composite(im, base, fade)
    d = ImageDraw.Draw(im, "RGBA")
    # text block: right of centre, vertically centred, clear of the avatar (x<420, y>300)
    x0 = 545 * S
    d.text((x0, 196 * S), "Every layoff.", font=font(700, 64 * S), fill=INK, anchor="ls")
    d.text((x0, 270 * S), "One globe.", font=font(700, 64 * S), fill=RED, anchor="ls")
    d.text((x0 + 2 * S, 318 * S), "Verified layoffs worldwide, updated hourly.", font=font(500, 22 * S), fill=INK2, anchor="ls")
    n = N["totals"]["people_30d"]
    d.ellipse([x0 + 2 * S, 345 * S, x0 + 12 * S, 355 * S], fill=RED)
    d.text((x0 + 22 * S, 350 * S), f"{n:,} people in the last 30 days", font=font(600, 18 * S), fill=MUTED, anchor="lm")
    im = im.resize((W, H), Image.LANCZOS)
    im.save(OUT / "header-1500x500.png", optimize=True)
    # review sim: avatar overlay + crop guides
    sim = im.copy().convert("RGBA")
    sd = ImageDraw.Draw(sim)
    sd.ellipse([40, 300, 40 + 240, 300 + 240], fill=(60, 60, 60, 255), outline=(255, 255, 255, 255), width=4)
    sd.line([(0, 60), (W, 60)], fill=(0, 200, 255, 160), width=1)
    sd.line([(0, H - 60), (W, H - 60)], fill=(0, 200, 255, 160), width=1)
    sim.convert("RGB").save(OUT / "_review-header-sim.png")
    print("wrote header")


def avatar(size):
    S = 4 if size <= 400 else 2
    Z = size * S
    im = Image.new("RGB", (Z, Z), BG)
    c = Z / 2
    R = Z * 0.40
    # a single red pulse dot on Western Europe, with the Americas on the left limb
    globe(im, c, c, R, -25, 28, 4.2, Z * 0.0115, [], S, rim=False, disc=(20, 20, 22), bright=1.15)
    d = ImageDraw.Draw(im, "RGBA")
    d.ellipse([c - R, c - R, c + R, c + R], outline=(70, 68, 66), width=int(Z * 0.006))
    q = rotate(xyz(np.array([50.0]), np.array([6.0])), -25, 28)[0]
    X, Y = c + q[0] * R, c - q[1] * R
    r = Z * 0.055
    for k, a, w in ((2.6, 70, 0.012), (1.8, 150, 0.014)):
        d.ellipse([X - r * k, Y - r * k, X + r * k, Y + r * k], outline=RED + (a,), width=int(Z * w))
    d.ellipse([X - r, Y - r, X + r, Y + r], fill=RED)
    im = im.resize((size, size), Image.LANCZOS)
    im.save(OUT / f"avatar-{size}.png", optimize=True)
    return im


def review(av):
    # circle crop + 48px + 96px on a light and a dark strip
    sheet = Image.new("RGB", (400 + 20 + 96 + 20 + 48 + 20 + 96 + 20 + 48, 400), (245, 245, 245))
    mask = Image.new("L", (400, 400), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, 399, 399], fill=255)
    sheet.paste(av, (0, 0), mask)
    x = 420
    for s, bg in ((96, (245, 245, 245)), (48, (245, 245, 245)), (96, (0, 0, 0)), (48, (0, 0, 0))):
        small = av.resize((s, s), Image.LANCZOS)
        m = mask.resize((s, s), Image.LANCZOS)
        tile = Image.new("RGB", (s + 10, s + 10), bg)
        tile.paste(small, (5, 5), m)
        sheet.paste(tile, (x, 150))
        x += s + 20
    sheet.save(OUT / "_review-avatar-sim.png")


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    header()
    av = avatar(400)
    avatar(1024)
    review(av)
    print("wrote avatars")
