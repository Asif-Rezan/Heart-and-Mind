#!/usr/bin/env python3
"""Low-poly satisfying soap cutting ASMR: PIL frames + numpy synthesized audio + ffmpeg mux."""
import math, random, subprocess, sys, os, hashlib, json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import signal
from scipy.io import wavfile

W, H = 720, 1280
S, FPS = int(os.getenv("ASMR_SUPERSAMPLE", "2")), 30
TAKES = int(os.getenv("ASMR_TAKES", "6"))
if not 1 <= TAKES <= 6 or S not in (1, 2):
    raise ValueError("Use 1-6 takes and supersample 1 or 2")
CUTS = 5
T0, CYC = 0.8, 1.56
X0, LEN, T = 30, 380, 38
X1 = X0 + LEN
YBOT, YTOP = 900, 700
OX, OY = 44, 26
PILE_X, SPACING = 410, 46
YREST = YTOP - 150
BLADE_H = 260
PALETTE = [(255, 140, 172), (255, 178, 112), (255, 226, 122), (128, 222, 162), (122, 190, 255), (184, 152, 242)]
LEAN = [-0.05, 0.04, -0.03, 0.05, -0.04]
TAKE_SECONDS = T0 + CUTS * CYC + 1.4
TOTAL = round(TAKE_SECONDS * TAKES, 6)
NFRAMES = int(TOTAL * FPS)
OUT = Path(os.getenv("ASMR_OUTPUT_DIR", str(Path(__file__).resolve().parent / "output"))).resolve()
os.makedirs(OUT, exist_ok=True)


def clamp(v, a=0.0, b=1.0): return max(a, min(b, v))
def lerp(a, b, t): return a + (b - a) * t
def ss(u): u = clamp(u); return u * u * (3 - 2 * u)
def eo3(u): u = clamp(u); return 1 - (1 - u) ** 3
def shade(c, f): return tuple(int(clamp(v * f, 0, 255)) for v in c)
def P(x, y, z=0.0): return (x + OX * z, y - OY * z)


# ------------------------------------------------------------------ timeline
def contact_u():
    target = (YTOP - YREST) / (YBOT - YREST)
    lo, hi = 0.0, 1.0
    for _ in range(40):
        mid = (lo + hi) / 2
        if ss(mid) < target: lo = mid
        else: hi = mid
    return lo
UC = contact_u()
def t_start(k): return T0 + k * CYC
def t_contact(k): return t_start(k) + 0.35 + 0.45 * UC
def t_bottom(k): return t_start(k) + 0.80
def t_detach(k): return t_start(k) + 0.88
def t_land(k): return t_detach(k) + 0.62
def xcut(k): return X1 - (k + 1) * T


def knife_state(t):
    if t < T0:
        return xcut(0), lerp(YTOP - 700, YREST, eo3(t / 0.6))
    k = min(CUTS - 1, int((t - T0) // CYC))
    tau = t - t_start(k)
    xc = xcut(k)
    if tau < 0.35:
        xp = xcut(k - 1) if k > 0 else xcut(0)
        x = lerp(xp, xc, ss(tau / 0.35))
    else:
        x = xc
    if tau < 0.35: y = YREST
    elif tau < 0.80: y = lerp(YREST, YBOT, ss((tau - 0.35) / 0.45))
    elif tau < 0.88: y = YBOT
    else:
        if k == CUTS - 1:
            y = lerp(YBOT, YTOP - 700, ss((tau - 0.88) / 0.9))
        else:
            y = lerp(YBOT, YREST, ss((tau - 0.88) / 0.42))
    return x, y


def slice_state(k, t):
    td = t_detach(k)
    if t < td: return None
    p = clamp((t - td) / 0.62)
    e = eo3(p)
    xs = xcut(k)
    slot = PILE_X + (CUTS - 1 - k) * SPACING
    dx = (slot - xs) * e
    hop = -math.sin(math.pi * p) * (50 + 0.15 * (slot - xs))
    ang = LEAN[k] * e + 0.2 * math.sin(math.pi * p)
    return dx, hop, ang


# ------------------------------------------------------------------ geometry
def tri_split(a, b, c, d, flip):
    return [(a, b, c), (a, c, d)] if flip else [(a, b, d), (b, c, d)]


_cache = {}
def box_polys(xa, xb, key, right):
    ck = (xa, xb, key, right, tuple(PALETTE))
    if ck in _cache: return _cache[ck]
    col = PALETTE[key] if isinstance(key, int) else PALETTE[5]
    rnd = random.Random(int.from_bytes(hashlib.sha256(str(key).encode()).digest()[:4], "big"))
    polys = []
    rows, nz = 6, 3
    nx = max(1, round((xb - xa) / 26))
    for j in range(rows):
        for i in range(nx):
            xl, xr = lerp(xa, xb, i / nx), lerp(xa, xb, (i + 1) / nx)
            ya, yb = lerp(YTOP, YBOT, j / rows), lerp(YTOP, YBOT, (j + 1) / rows)
            for tr in tri_split((xl, ya), (xr, ya), (xr, yb), (xl, yb), (i + j) % 2 == 0):
                polys.append((list(tr), shade(col, 1.0 + rnd.uniform(-.06, .06) + .07 * (1 - j / rows))))
    for j in range(nz):
        for i in range(nx):
            xl, xr = lerp(xa, xb, i / nx), lerp(xa, xb, (i + 1) / nx)
            za, zb = j / nz, (j + 1) / nz
            for tr in tri_split(P(xl, YTOP, za), P(xr, YTOP, za), P(xr, YTOP, zb), P(xl, YTOP, zb), (i + j) % 2 == 0):
                polys.append((list(tr), shade(col, 1.16 + rnd.uniform(-.06, .06))))
    if right:
        for j in range(rows):
            for i in range(nz):
                ya, yb = lerp(YTOP, YBOT, j / rows), lerp(YTOP, YBOT, (j + 1) / rows)
                za, zb = i / nz, (i + 1) / nz
                for tr in tri_split(P(xb, ya, za), P(xb, ya, zb), P(xb, yb, zb), P(xb, yb, za), (i + j) % 2 == 0):
                    polys.append((list(tr), shade(col, .80 + rnd.uniform(-.06, .06))))
    _cache[ck] = polys
    return polys


def xform(polys, dx, dy, ang, pivot):
    c, s = math.cos(ang), math.sin(ang)
    px, py = pivot
    out = []
    for pts, col in polys:
        out.append(([(px + (x - px) * c - (y - py) * s + dx, py + (x - px) * s + (y - py) * c + dy) for x, y in pts], col))
    return out


def draw_polys(d, polys):
    for pts, col in polys:
        sp = [(x * S, y * S) for x, y in pts]
        d.polygon(sp, fill=col, outline=col)


# ------------------------------------------------------------------ background
def make_bg():
    rnd = random.Random(7)
    img = Image.new("RGB", (W * S, H * S))
    d = ImageDraw.Draw(img)
    hor = 640
    def wall(y): return tuple(lerp(a, b, y / hor) for a, b in zip((255, 226, 214), (228, 212, 250)))
    def table(y): return tuple(lerp(a, b, (y - hor) / (H - hor)) for a, b in zip((246, 230, 216), (224, 202, 198)))
    def grid(y0, y1, nrows, colf):
        cols = 9
        ys = [lerp(y0, y1, r / nrows) for r in range(nrows + 1)]
        pts = []
        for r, y in enumerate(ys):
            row = []
            for c in range(cols + 1):
                x = c * W / cols
                jx = 0 if c in (0, cols) else rnd.uniform(-26, 26)
                jy = 0 if r in (0, nrows) else rnd.uniform(-22, 22)
                row.append((x + jx, y + jy))
            pts.append(row)
        for r in range(nrows):
            for c in range(cols):
                a, b, cc, dd = pts[r][c], pts[r][c + 1], pts[r + 1][c + 1], pts[r + 1][c]
                for tr in tri_split(a, b, cc, dd, (r + c) % 2 == 0):
                    cy = sum(p[1] for p in tr) / 3
                    col = shade(colf(cy), 1 + rnd.uniform(-.035, .035))
                    d.polygon([(x * S, y * S) for x, y in tr], fill=col, outline=col)
    grid(0, hor, 8, wall)
    grid(hor, H, 8, table)
    def font(size, bold=False):
        paths = (["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                  "/System/Library/Fonts/Supplemental/Arial Bold.ttf"] if bold else
                 ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                  "/System/Library/Fonts/Supplemental/Arial.ttf"])
        for path in paths:
            if Path(path).exists(): return ImageFont.truetype(path, size*S)
        return ImageFont.load_default(size=size*S)
    fb, fb2, fs = font(40,True), font(70,True), font(28)
    def ctext(txt, y, f, fill):
        w = d.textlength(txt, font=f)
        d.text(((W * S - w) / 2, y * S), txt, font=f, fill=fill)
    ctext("SATISFYING SOAP CUTTING", 62, fb, (120, 96, 142))
    ctext("ASMR", 112, fb2, (255, 140, 172))
    ctext("best with headphones", 1190, fs, (140, 112, 150))
    return img.convert("RGBA")


# ------------------------------------------------------------------ knife
def draw_knife(d, xc, yk):
    zs = [-0.3 + 0.15 * i for i in range(12)]
    ytb = yk - BLADE_H
    rnd = random.Random(99)
    nrow = 5
    for j in range(nrow):
        ya, yb = lerp(ytb, yk, j / nrow), lerp(ytb, yk, (j + 1) / nrow)
        for i in range(11):
            za, zb = zs[i], zs[i + 1]
            parts = []
            if ya < YTOP: parts.append((za, zb, ya, min(yb, YTOP)))
            if yb > YTOP and zb <= 1e-9: parts.append((za, zb, max(ya, YTOP), yb))
            for (pza, pzb, pya, pyb) in parts:
                if pyb - pya < 0.01: continue
                for tr in tri_split(P(xc, pya, pza), P(xc, pya, pzb), P(xc, pyb, pzb), P(xc, pyb, pza), (i + j) % 2 == 0):
                    f = .90 + .13 * (j / nrow) + rnd.uniform(-.05, .05) + (.08 if (i + j) % 4 == 0 else 0)
                    draw_polys(d, [(list(tr), shade((196, 208, 224), f))])
    # handle bar (right face + top face)
    hy0, hy1 = ytb - 46, ytb
    hz = [-0.15 + 0.2 * i for i in range(8)]
    for i in range(7):
        for tr in tri_split(P(xc + 9, hy0, hz[i]), P(xc + 9, hy0, hz[i + 1]), P(xc + 9, hy1, hz[i + 1]), P(xc + 9, hy1, hz[i]), i % 2 == 0):
            draw_polys(d, [(list(tr), shade((150, 98, 78), .85 + rnd.uniform(-.05, .05)))])
        for tr in tri_split(P(xc - 9, hy0, hz[i]), P(xc + 9, hy0, hz[i]), P(xc + 9, hy0, hz[i + 1]), P(xc - 9, hy0, hz[i + 1]), i % 2 == 0):
            draw_polys(d, [(list(tr), shade((150, 98, 78), 1.12 + rnd.uniform(-.05, .05)))])


# ------------------------------------------------------------------ crumbs
def build_crumbs():
    rnd = random.Random(21)
    cr = []
    def add(t, x, y, col, big=1.0):
        cr.append(dict(t=t, x=x, y=y, vx=rnd.uniform(-170, 170), vy=rnd.uniform(-260, -60),
                       size=rnd.uniform(5, 10) * big, col=shade(col, rnd.uniform(.95, 1.2)), rot=rnd.uniform(0, 6.28)))
    for k in range(CUTS):
        xc = xcut(k)
        tc, tb = t_contact(k), t_bottom(k)
        for _ in range(6): add(tc, *P(xc, YTOP, rnd.uniform(0, 1)), PALETTE[k])
        t = tc
        while t < tb:
            kx, ky = knife_state(t)
            for _ in range(2): add(t, xc + rnd.uniform(-5, 5), ky, PALETTE[k])
            t += 1 / FPS
        slot = PILE_X + (CUTS - 1 - k) * SPACING
        for _ in range(8): add(t_land(k), slot + rnd.uniform(0, T) + OX * .3, YBOT - 6, PALETTE[k], .7)
    return cr


CRUMBS = build_crumbs()
LIFE, G = 0.7, 900


def draw_crumbs(d, t):
    for c in CRUMBS:
        a = t - c["t"]
        if a < 0 or a > LIFE: continue
        x = c["x"] + c["vx"] * a
        y = c["y"] + c["vy"] * a + .5 * G * a * a
        if y > YBOT + 4: y = YBOT + 4
        sz = c["size"] * (1 - a / LIFE)
        r = c["rot"] + a * 6
        pts = [(x + sz * math.cos(r + m * 2.094), y + sz * math.sin(r + m * 2.094)) for m in range(3)]
        draw_polys(d, [(pts, c["col"])])


# ------------------------------------------------------------------ frame
def shadow(layer, cx, cy, rx, ry, alpha):
    dd = ImageDraw.Draw(layer)
    for i in range(6):
        f = 1 - i * .12
        dd.ellipse([(cx - rx * f) * S, (cy - ry * f) * S, (cx + rx * f) * S, (cy + ry * f) * S], fill=(70, 40, 70, int(alpha)))


BG = make_bg()
SEGS = [("rem", X0, X1 - CUTS * T)] + [(k, xcut(k), X1 - k * T) for k in reversed(range(CUTS))]


def render_scene(t):
    ndet = sum(1 for k in range(CUTS) if t >= t_detach(k))
    layer = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
    xend = X1 - ndet * T
    shadow(layer, (X0 + xend) / 2 + OX / 2, YBOT - OY / 2 + 8, (xend - X0) / 2 + OX / 2 + 16, OY / 2 + 20, 11)
    states = {}
    for k in range(CUTS):
        st = slice_state(k, t)
        if st is None: continue
        states[k] = st
        dx, hop, ang = st
        xs = xcut(k)
        shadow(layer, xs + T / 2 + dx + OX / 2, YBOT - OY / 2 + 8, T / 2 + OX / 2 + 10, OY / 2 + 14, max(4, 11 + hop * .08))
    img = Image.alpha_composite(BG, layer).convert("RGB")
    d = ImageDraw.Draw(img)

    present = [s for s in SEGS if s[0] == "rem" or s[0] >= ndet]
    for idx, (key, xa, xb) in enumerate(present):
        draw_polys(d, box_polys(xa, xb, key, idx == len(present) - 1))

    # seam while knife is inside the block
    kx, ky = knife_state(t)
    k_now = min(CUTS - 1, max(0, int((t - T0) // CYC))) if t >= T0 else 0
    if t >= T0 and t_contact(k_now) <= t < t_detach(k_now) and ndet == k_now:
        a = P(kx, YTOP, 0); b = P(kx, YTOP, 1)
        d.line([(a[0] * S, a[1] * S), (b[0] * S, b[1] * S)], fill=(80, 46, 88), width=3 * S)
        d.line([(kx * S, YTOP * S), (kx * S, min(ky, YBOT) * S)], fill=(80, 46, 88), width=3 * S)

    # detached slices (sorted by x)
    for k in sorted(states, key=lambda k: xcut(k) + states[k][0]):
        dx, hop, ang = states[k]
        xs = xcut(k)
        polys = box_polys(xs, xs + T, k, True)
        draw_polys(d, xform(polys, dx, hop, ang, (xs + T / 2, YBOT)))

    draw_crumbs(d, t)
    draw_knife(d, kx, ky)
    return img.resize((W, H), Image.LANCZOS)


# Six palette variations of the supplied geometric cutting sequence, ten seconds each.
BASE_PALETTE = list(PALETTE)
CURRENT_TAKE = -1


def configure_take(take):
    global CURRENT_TAKE, PALETTE, CRUMBS
    if CURRENT_TAKE == take: return
    PALETTE = BASE_PALETTE[take:] + BASE_PALETTE[:take]
    _cache.clear()
    CRUMBS = build_crumbs()
    CURRENT_TAKE = take


def render(t):
    take = min(TAKES-1, int(t / TAKE_SECONDS))
    configure_take(take)
    local = t - take * TAKE_SECONDS
    image = render_scene(local)
    # Brief dip conceals the intentional material reset between color variations.
    fade = min(ss(local/.16), ss((TAKE_SECONDS-local)/.18))
    if fade < 1:
        image = Image.fromarray((np.asarray(image)*fade).astype(np.uint8))
    return image


# ------------------------------------------------------------------ audio
SR = 44100
rng = np.random.default_rng(5)
N = int((TOTAL + 0.3) * SR)
AL, AR = np.zeros(N), np.zeros(N)
AUDIO_OFFSET = 0.0


def add(sig, t, pan):
    i = int((t + AUDIO_OFFSET) * SR)
    n = min(len(sig), N - i)
    if n <= 0: return
    AL[i:i + n] += sig[:n] * math.cos(pan * math.pi / 2)
    AR[i:i + n] += sig[:n] * math.sin(pan * math.pi / 2)


def bp(x, lo, hi):
    return signal.sosfilt(signal.butter(3, [lo, hi], btype="band", fs=SR, output="sos"), x)
def lp(x, f):
    return signal.sosfilt(signal.butter(3, f, btype="low", fs=SR, output="sos"), x)
def hp(x, f):
    return signal.sosfilt(signal.butter(3, f, btype="high", fs=SR, output="sos"), x)


def kernel(tau, ms=10):
    n = int(ms / 1000 * SR)
    tt = np.arange(n) / SR
    return np.exp(-tt / tau) * rng.standard_normal(n)


def crunch(dur, amp, rate=1100):
    n = int(dur * SR)
    u = np.linspace(0, 1, n)
    env = np.sin(np.pi * u) ** 0.6
    p = rate * env / SR
    imp = (rng.random(n) < p) * rng.exponential(1, n) * rng.choice([-1, 1], n)
    s = signal.fftconvolve(imp, kernel(0.0007), mode="same") + .6 * signal.fftconvolve(imp, kernel(0.002), mode="same")
    s = bp(s, 1200, 9000)
    body = lp(rng.standard_normal(n), 450) * env * .0
    s = s / (np.abs(s).max() + 1e-9)
    body = lp(rng.standard_normal(n), 500) * env
    body = body / (np.abs(body).max() + 1e-9) * .25
    return (s * env ** .5 + body) * amp


def whoosh(dur, amp):
    n = int(dur * SR)
    u = np.linspace(0, 1, n)
    s = bp(rng.standard_normal(n), 500, 3500) * np.sin(np.pi * u) ** 2
    return s / (np.abs(s).max() + 1e-9) * amp


def thud(f0, decay, amp):
    n = int(0.2 * SR)
    tt = np.arange(n) / SR
    ph = 2 * np.pi * np.cumsum(f0 * np.exp(-tt * 8) + f0 * .5) / SR
    s = np.sin(ph) * np.exp(-tt / decay)
    c = lp(rng.standard_normal(n), 3000) * np.exp(-tt / 0.004) * .6
    return (s + c) * amp


def squish(dur, amp):
    n = int(dur * SR)
    tt = np.arange(n) / SR
    u = tt / dur
    env = u ** .5 * (1 - u) ** 1.5
    env /= env.max()
    s = bp(rng.standard_normal(n), 250, 1400) * env * (.6 + .4 * np.sin(2 * np.pi * 9 * tt))
    return s / (np.abs(s).max() + 1e-9) * amp


def tick(amp):
    n = int(0.012 * SR)
    tt = np.arange(n) / SR
    return hp(rng.standard_normal(n), 2500) * np.exp(-tt / 0.0025) * amp


def build_audio():
    global AL, AR, rng, AUDIO_OFFSET
    AL, AR = np.zeros(N), np.zeros(N)
    rng = np.random.default_rng(5)
    for take in range(TAKES):
        AUDIO_OFFSET = take * TAKE_SECONDS
        for k in range(CUTS):
            xc = xcut(k)
            pan = .25 + .5 * xc / W
            if k > 0: add(whoosh(.35, .07), t_start(k), pan)
            add(whoosh(.25, .06), t_start(k) + .35, pan)
            dur = t_bottom(k) - t_contact(k)
            add(crunch(dur, .55), t_contact(k), pan)
            add(thud(150, .03, .32), t_bottom(k), pan)
            add(crunch(.09, .35, 1800), t_detach(k), pan)
            add(squish(.5, .14), t_detach(k), pan + .1)
            slot = PILE_X + (CUTS - 1 - k) * SPACING
            lp_pan = .25 + .5 * slot / W
            add(thud(190, .02, .2), t_land(k), lp_pan)
            for _ in range(5): add(tick(rng.uniform(.08, .22)), t_land(k) + rng.uniform(.0, .25), lp_pan)
            for _ in range(4): add(tick(rng.uniform(.06, .16)), t_contact(k) + rng.uniform(0, .5), pan)
    n = len(AL)
    tone = lp(rng.standard_normal(n), 900) * .003
    L, R = AL + tone, AR + tone
    L, R = lp(L, 15000), lp(R, 15000)
    pk = max(np.abs(L).max(), np.abs(R).max())
    L, R = L / pk * .85, R / pk * .85
    fade = int(.02 * SR)
    for ch in (L, R):
        ch[:fade] *= np.linspace(0, 1, fade); ch[-fade:] *= np.linspace(1, 0, fade)
    st = np.stack([L, R], 1)
    wavfile.write(str(OUT/"soap-cutting-sound-design.wav"), SR, (st * 32767).astype(np.int16))


# ------------------------------------------------------------------ main
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "debug":
        for tt in [float(x) for x in sys.argv[2:]]:
            render(tt).save(OUT/f"debug-{tt:.2f}.png")
        sys.exit()
    build_audio()
    target = OUT/"soap-cutting-asmr-preview.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", str(OUT/"soap-cutting-sound-design.wav"), "-t", str(TOTAL),
           "-c:v", "libx264", "-threads", "2", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
           "-af", "loudnorm=I=-19:TP=-2:LRA=6", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(target)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        for f in range(NFRAMES):
            p.stdin.write(render(f / FPS).tobytes())
            if f % (FPS*5) == 0: print(f"Rendered {f/FPS:.0f}/{TOTAL:.0f}s", flush=True)
    finally:
        p.stdin.close()
    if p.wait() != 0: raise RuntimeError("FFmpeg render failed")
    info = json.loads(subprocess.check_output(["ffprobe","-v","error","-show_format","-show_streams","-of","json",str(target)]))
    video = next(x for x in info["streams"] if x["codec_type"] == "video")
    assert abs(float(info["format"]["duration"])-TOTAL) < .08
    assert video["width"] == W and video["height"] == H and video["r_frame_rate"] == "30/1"
    assert any(x["codec_type"] == "audio" and x["channels"] == 2 for x in info["streams"])
    subprocess.run(["ffmpeg","-v","error","-i",str(target),"-f","null","-"],check=True)
    (OUT/"soap-media-probe.json").write_text(json.dumps(info,indent=2))
    print(f"Verified {TOTAL:.0f}s, {NFRAMES} frames: {target}",flush=True)
