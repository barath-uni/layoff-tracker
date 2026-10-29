"""Launch video: dot-matrix globe, layoffs popping in chronologically. Pillow + numpy, piped to ffmpeg.

python3 marketing/src/video.py v   -> marketing/video/globe-1080x1920.mp4
python3 marketing/src/video.py h   -> marketing/video/globe-1920x1080.mp4
Frames stream straight into ffmpeg (no frames on disk, low RAM). FFMPEG env var overrides the binary.
"""
import json, math, os, re, subprocess, sys, zlib
from datetime import date, timedelta
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent.parent
ROOT = HERE.parent
N = json.loads((HERE / "data/numbers.json").read_text())
SNAP = json.loads((HERE / "data" / N["snapshot"]).read_text())
FFMPEG = os.environ.get("FFMPEG") or "/home/barath/codespace/shorts-factory/.venv/lib/python3.12/site-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2"
FONTS = ROOT / "assets/fonts"

FPS, DUR = 30, 18.0
T_HOOK, T_END = 1.6, 15.4          # timeline runs between these
BG = (9, 9, 10)
INK = (242, 239, 233)
INK2 = (176, 172, 166)
MUTED = (112, 109, 105)
RED = (255, 64, 46)
URL = "layoff-tracker.pages.dev"


def font(w, px):
    return ImageFont.truetype(str(FONTS / f"geist-{w}.ttf"), int(px))


# ---------- land points ----------
def land_mask(W=1440, H=720):
    t = json.loads((ROOT / "site/static/vendor/countries-110m.json").read_text())
    sx, sy = t["transform"]["scale"]
    tx, ty = t["transform"]["translate"]
    arcs = []
    for a in t["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in a:
            x += dx; y += dy
            pts.append((x * sx + tx, y * sy + ty))
        arcs.append(pts)

    def ring(idx):
        out = []
        for i in idx:
            pts = arcs[i] if i >= 0 else arcs[~i][::-1]
            out.extend(pts[1:] if out else pts)
        return out

    im = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(im)
    for g in t["objects"]["land"]["geometries"]:
        polys = g["arcs"] if g["type"] == "MultiPolygon" else [g["arcs"]]
        for poly in polys:
            r = ring(poly[0])
            if min(p[1] for p in r) < -60:      # drop Antarctica: cleaner silhouette
                continue
            d.polygon([((lon + 180) / 360 * W, (90 - lat) / 180 * H) for lon, lat in r], fill=255)
    return np.array(im) > 0


def land_points(spacing_deg=1.55):
    mask = land_mask()
    H, W = mask.shape
    n = int(4 * math.pi / math.radians(spacing_deg) ** 2)
    i = np.arange(n) + 0.5
    lat = np.degrees(np.arcsin(1 - 2 * i / n))
    lon = (np.degrees(np.pi * (1 + 5 ** 0.5) * i) % 360) - 180
    px = ((lon + 180) / 360 * W).astype(int).clip(0, W - 1)
    py = ((90 - lat) / 180 * H).astype(int).clip(0, H - 1)
    keep = mask[py, px]
    return lat[keep], lon[keep]


def xyz(lat, lon):
    la, lo = np.radians(lat), np.radians(lon)
    return np.stack([np.cos(la) * np.sin(lo), np.sin(la), np.cos(la) * np.cos(lo)], -1)


def rotate(v, lon0, lat0):
    a, b = math.radians(-lon0), math.radians(lat0)
    ry = np.array([[math.cos(a), 0, math.sin(a)], [0, 1, 0], [-math.sin(a), 0, math.cos(a)]])
    rx = np.array([[1, 0, 0], [0, math.cos(b), -math.sin(b)], [0, math.sin(b), math.cos(b)]])
    return v @ ry.T @ rx.T


# ---------- events with coordinates ----------
HUB = {  # business hubs per country (lat, lon); events jitter around them
    "United Kingdom": (52.0, -1.2), "Germany": (50.6, 9.0), "Italy": (44.0, 10.5), "Netherlands": (52.2, 5.2),
    "Australia": (-33.0, 147.0), "France": (47.0, 2.4), "Sweden": (59.0, 16.0), "Finland": (61.5, 25.0),
    "Argentina": (-34.6, -60.0), "Belgium": (50.7, 4.6), "Indonesia": (-6.5, 107.0), "Spain": (40.4, -3.7),
    "Switzerland": (47.0, 8.0), "Japan": (35.5, 138.5), "India": (19.0, 76.0), "Brazil": (-23.0, -46.8),
    "Canada": (44.5, -78.0), "Mexico": (20.5, -100.0), "South Korea": (37.0, 127.2), "China": (31.0, 118.0),
    "Hong Kong": (22.3, 114.2), "Singapore": (1.35, 103.8), "Israel": (32.0, 34.9), "Norway": (60.5, 9.5),
    "Russia": (55.7, 37.6), "Turkey": (40.5, 31.0), "Chile": (-33.4, -70.6),
}
US_STATE = {"CA": (36.0, -120.0), "WA": (47.3, -120.8), "MD": (39.1, -76.7), "PA": (40.6, -77.5), "CO": (39.4, -105.3), "TX": (31.5, -98.0)}
US_METRO = [(40.7, -74.0), (37.6, -122.2), (47.6, -122.3), (41.9, -87.7), (30.3, -97.7), (42.4, -71.1),
            (34.0, -118.2), (33.7, -84.4), (38.9, -77.0), (39.0, -94.6), (35.2, -80.8), (44.9, -93.2)]


def h01(s, k):
    return (zlib.crc32(f"{s}:{k}".encode()) & 0xFFFFFF) / 0xFFFFFF


def events():
    keep = {(x["slug"], x["start"], x["headcount"]) for x in N["events_kept"]}
    out = []
    for x in SNAP["events"]:
        if (x["slug"], x["start"], x["headcount"]) not in keep:
            continue
        key = x["slug"] + x["start"]
        if x["country"] == "United States":
            m = re.search(r", ([A-Z]{2})\b", x.get("headline", ""))
            base = US_STATE.get(m.group(1)) if m else None
            base = base or US_METRO[int(h01(key, "m") * len(US_METRO))]
            jit = 1.6
        elif x["country"] in HUB:
            base, jit = HUB[x["country"]], 1.4
        else:
            continue  # "Unknown": counted in the counter, not placed on the map
        lat = base[0] + (h01(key, "a") - 0.5) * 2 * jit
        lon = base[1] + (h01(key, "o") - 0.5) * 2 * jit * 1.4
        out.append({"company": x["company"], "n": x["headcount"] or 0, "start": x["start"], "lat": lat, "lon": lon, "key": key})
    return out


# ---------- timeline ----------
D0 = date.fromisoformat(N["window_from"])
D1 = date.fromisoformat(N["window_to"]) + timedelta(days=1)
SPAN = (D1 - D0).days


def ev_time(e):
    day = (date.fromisoformat(e["start"]) - D0).days + h01(e["key"], "t") * 0.9
    return T_HOOK + (T_END - T_HOOK) * day / SPAN


def t_to_date(t):
    f = min(1, max(0, (t - T_HOOK) / (T_END - T_HOOK)))
    return D0 + timedelta(days=min(SPAN - 1, int(f * SPAN)))


def ease(x):
    x = min(1, max(0, x))
    return x * x * (3 - 2 * x)


# ---------- frame renderer ----------
class Video:
    def __init__(self, W, H):
        self.W, self.H = W, H
        self.tall = H > W
        if self.tall:
            self.cx, self.cy, self.R = W // 2, 800, 450
        else:
            self.cx, self.cy, self.R = 600, 560, 440
        self.SS = 2
        lat, lon = land_points()
        self.land = xyz(lat, lon)
        self.ev = events()
        for e in self.ev:
            e["t"] = ev_time(e)
            e["v"] = xyz(np.array([e["lat"]]), np.array([e["lon"]]))[0]
        self.ev.sort(key=lambda e: e["t"])
        # counter: every kept event with a headcount (Unknown-country ones included)
        self.cnt = sorted((ev_time({"start": x["start"], "key": x["slug"] + x["start"]}), x["headcount"])
                          for x in N["events_kept"] if x["headcount"])
        self.total = N["totals"]["people"]
        assert sum(n for _, n in self.cnt) == self.total
        self.flash = [e for e in self.ev if e["n"] >= 2400]
        self.shown = 0.0
        self.f = {k: font(*k) for k in [(700, 240 if self.tall else 190), (700, 58), (600, 30), (500, 26), (700, 30), (600, 22), (500, 22),
                                         (700, 120), (700, 96), (600, 40), (700, 44), (500, 30), (600, 18)]}

    def lon0(self, t):
        return -118 + 250 * (t / DUR)

    def globe(self, t, alpha):
        S = self.SS
        size = (2 * self.R + 80) * S
        im = Image.new("RGB", (size, size), BG)
        d = ImageDraw.Draw(im, "RGBA")
        c = size / 2
        R = self.R * S
        d.ellipse([c - R, c - R, c + R, c + R], fill=(17, 17, 19))
        d.ellipse([c - R, c - R, c + R, c + R], outline=(40, 39, 38), width=S)
        lon0, lat0 = self.lon0(t), 22
        p = rotate(self.land, lon0, lat0)
        vis = p[:, 2] > 0.02
        p = p[vis]
        xs, ys, zs = c + p[:, 0] * R, c - p[:, 1] * R, p[:, 2]
        r = 1.9 * S * (0.55 + 0.45 * zs)
        shade = (70 + 120 * zs ** 0.8).astype(int)
        for x, y, rr, g in zip(xs, ys, r, shade):
            d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=(g, g - 2, g - 4))
        # events
        for e in self.ev:
            if e["t"] > t:
                break
            q = rotate(e["v"][None, :], lon0, lat0)[0]
            if q[2] <= 0.02:
                continue
            x, y = c + q[0] * R, c - q[1] * R
            age = t - e["t"]
            base = (2.2 + 0.11 * math.sqrt(max(e["n"], 40))) * S
            pop = 1 + 0.9 * math.exp(-age * 7) if age < 0.6 else 1
            rr = base * pop * (0.6 + 0.4 * q[2])
            a = int(200 + 55 * math.exp(-age * 3))
            d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=RED + (a,))
            if age < 1.1:   # red pulse ring
                k = age / 1.1
                pr = rr + (8 + 0.5 * math.sqrt(max(e["n"], 40))) * S * k * 2.2
                pa = int(220 * (1 - k) ** 1.5)
                d.ellipse([x - pr, y - pr, x + pr, y + pr], outline=RED + (pa,), width=max(1, int(2.2 * S * (1 - k) + 1)))
        im = im.resize((size // S, size // S), Image.LANCZOS)
        if alpha < 1:
            im = Image.blend(Image.new("RGB", im.size, BG), im, alpha)
        return im

    def counter(self, t):
        target = sum(n for tt, n in self.cnt if tt <= t)
        self.shown += (target - self.shown) * 0.28
        if t >= T_END:
            self.shown = target
        return int(round(self.shown))

    def frame(self, t):
        W, H = self.W, self.H
        im = Image.new("RGB", (W, H), BG)
        hook = 1 - ease((t - (T_HOOK - 0.35)) / 0.35)          # hook text fades by T_HOOK
        end = ease((t - T_END) / 0.5)                          # end card fades in
        g = self.globe(t, alpha=0.35 + 0.65 * ease(t / T_HOOK) if t < T_HOOK else 1 - 0.75 * end)
        im.paste(g, (self.cx - g.width // 2, self.cy - g.height // 2))
        d = ImageDraw.Draw(im, "RGBA")
        m = 72 if self.tall else 90
        # brand
        d.ellipse([m, m - 6, m + 12, m + 6], fill=RED)
        d.text((m + 24, m), "LAYOFF TRACKER", font=self.f[(600, 22)], fill=INK, anchor="lm")
        if hook > 0:
            self.hook_text(d, hook)
        if 0 < t < T_END + 0.5 and hook < 1:
            self.hud(d, t, 1 - hook - end)
        if end > 0:
            self.end_card(d, end)
        return im

    def hook_text(self, d, a):
        W, H = self.W, self.H
        f = self.f[(700, 120)] if self.tall else self.f[(700, 120)]
        col = tuple(int(c * a + BG[i] * (1 - a)) for i, c in enumerate(INK))
        cy = self.cy if self.tall else H // 2
        d.text((W // 2, cy - 70), "Every layoff.", font=f, fill=col, anchor="ms")
        red = tuple(int(c * a + BG[i] * (1 - a)) for i, c in enumerate(RED))
        d.text((W // 2, cy + 80), "One globe.", font=f, fill=red, anchor="ms")

    def hud(self, d, t, a):
        W, H = self.W, self.H
        A = int(255 * max(0, min(1, a)))
        day = t_to_date(t)
        n = self.counter(t)
        if self.tall:
            d.text((W - 72, 72), f"{day:%-d %b %Y}".upper(), font=self.f[(600, 30)], fill=INK2 + (A,), anchor="rm")
            y = 1620
            d.text((72, y), f"{n:,}", font=self.f[(700, 240)], fill=INK + (A,), anchor="ls")
            d.text((76, y + 56), "people laid off · verified layoffs only", font=self.f[(500, 30)], fill=MUTED + (A,), anchor="ls")
            fx, fy, fa = 72, 1390, "ls"
        else:
            x = 1150
            d.text((W - 90, 90), f"{day:%-d %b %Y}".upper(), font=self.f[(600, 30)], fill=INK2 + (A,), anchor="rm")
            d.text((x, 640), f"{n:,}", font=self.f[(700, 190)], fill=INK + (A,), anchor="ls")
            d.text((x + 4, 696), "people laid off", font=self.f[(500, 30)], fill=INK2 + (A,), anchor="ls")
            d.text((x + 4, 736), "verified layoffs only", font=self.f[(500, 26)], fill=MUTED + (A,), anchor="ls")
            fx, fy, fa = x, 400, "ls"
        # flashing company names
        cur = [e for e in self.flash if 0 <= t - e["t"] < 0.85]
        if cur:
            e = cur[-1]
            age = t - e["t"]
            k = min(1, age / 0.08) * (1 if age < 0.65 else max(0, 1 - (age - 0.65) / 0.2))
            ka = int(A * k)
            d.text((fx, fy), e["company"].upper(), font=self.f[(700, 58)], fill=INK + (ka,), anchor=fa)
            d.text((fx, fy + 52), f"−{e['n']:,} jobs", font=self.f[(700, 44)], fill=RED + (ka,), anchor=fa)

    def end_card(self, d, a):
        W, H = self.W, self.H
        A = int(255 * a)
        T = N["totals"]
        cy = self.cy if self.tall else H // 2
        d.text((W // 2, cy - 150), f"{T['people']:,}", font=self.f[(700, 240 if self.tall else 190)], fill=INK + (A,), anchor="ms")
        d.text((W // 2, cy - 80), f"people · {T['companies']} companies · {T['countries']} countries · 3 months",
               font=self.f[(500, 30)], fill=INK2 + (A,), anchor="ms")
        d.rounded_rectangle([W // 2 - 300, cy + 10, W // 2 + 300, cy + 100], 45, fill=RED + (A,))
        d.text((W // 2, cy + 56), URL, font=self.f[(700, 44)], fill=(255, 255, 255, A), anchor="mm")
        d.text((W // 2, cy + 160), "Free · updated hourly · every number sourced", font=self.f[(500, 26)], fill=MUTED + (A,), anchor="ms")


def free_mb():
    for line in open("/proc/meminfo"):
        if line.startswith("MemAvailable"):
            return int(line.split()[1]) // 1024
    return 0


def render(kind, frames_only=None):
    W, H = (1080, 1920) if kind == "v" else (1920, 1080)
    if free_mb() < 1500:
        sys.exit(f"only {free_mb()} MB free; backing off")
    v = Video(W, H)
    if frames_only:                      # stills for review
        for t in frames_only:
            v.shown = sum(n for tt, n in v.cnt if tt <= t)
            v.frame(t).save(HERE / f"video/frame-{kind}-{t:04.1f}s.png")
        return
    out = HERE / f"video/globe-{W}x{H}.mp4"
    cmd = [FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-c:v", "libx264", "-preset", "medium", "-crf", "22", "-pix_fmt", "yuv420p", "-threads", "2",
           "-movflags", "+faststart", str(out)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    nf = int(DUR * FPS)
    for i in range(nf):
        if i % 90 == 0:
            mb = free_mb()
            print(f"frame {i}/{nf}  free {mb} MB", flush=True)
            if mb < 1500:
                import time
                time.sleep(5)       # back off; RAM is tight
        p.stdin.write(v.frame(i / FPS).tobytes())
    p.stdin.close()
    p.wait()
    print("wrote", out, out.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    kind = sys.argv[1] if len(sys.argv) > 1 else "v"
    if len(sys.argv) > 2 and sys.argv[2] == "stills":
        render(kind, [0.8, 6.0, 10.5, 17.0])
    else:
        render(kind)
