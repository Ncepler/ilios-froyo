"""Procedural textures for the Ilios froyo cup and machine.

Run with the Blender-venv python (numpy, pillow, scipy):
    python tex.py <out_dir>

Everything here is generated from code: the gold-foil sun emblem decal
(base colour + alpha, ORM, normal), the paper fibre tiles, the brushed
steel tile and the soft-serve micro-surface tile. All tiles are periodic
(FFT-filtered noise), so they repeat without seams.
"""
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy import ndimage

OUT = sys.argv[1] if len(sys.argv) > 1 else "tex"
os.makedirs(OUT, exist_ok=True)
RNG = np.random.default_rng(7)

FONT_DIRS = ["/mnt/skills/examples/canvas-design/canvas-fonts", "/usr/share/fonts"]


def find_font(name):
    for d in FONT_DIRS:
        for root, _, files in os.walk(d):
            if name in files:
                return os.path.join(root, name)
    raise FileNotFoundError(name)


# ---------------------------------------------------------------- helpers
def periodic_noise(n, sx, sy=None, seed=0):
    """Seamless gaussian-filtered noise in [0,1]. sx/sy = blur sigma in px."""
    sy = sx if sy is None else sy
    rng = np.random.default_rng(seed)
    w = rng.standard_normal((n, n))
    fy = np.fft.fftfreq(n)[:, None]
    fx = np.fft.fftfreq(n)[None, :]
    filt = np.exp(-2 * (math.pi ** 2) * ((fx * sx) ** 2 + (fy * sy) ** 2))
    out = np.real(np.fft.ifft2(np.fft.fft2(w) * filt))
    out -= out.min()
    out /= out.max()
    return out


def height_to_normal(h, strength, wrap=True):
    mode = "wrap" if wrap else "nearest"
    dx = ndimage.sobel(h, axis=1, mode=mode) / 8.0
    dy = ndimage.sobel(h, axis=0, mode=mode) / 8.0
    nx, ny, nz = -dx * strength, dy * strength, np.ones_like(h)
    ln = np.sqrt(nx * nx + ny * ny + nz * nz)
    rgb = np.stack([nx / ln, ny / ln, nz / ln], -1) * 0.5 + 0.5
    return Image.fromarray((rgb * 255).clip(0, 255).astype(np.uint8))


def to_img(a):
    return Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))


def srgb(hexs):
    hexs = hexs.lstrip("#")
    return np.array([int(hexs[i:i + 2], 16) for i in (0, 2, 4)], np.float32) / 255


# ---------------------------------------------------------------- paper
def paper_tiles(n=1024):
    # long thin fibres in random directions + fine tooth + soft clouding
    fib = np.zeros((n, n), np.float32)
    img = Image.new("L", (n * 2, n * 2), 0)
    d = ImageDraw.Draw(img)
    for _ in range(5200):
        x, y = RNG.uniform(0, n * 2, 2)
        a = RNG.uniform(0, math.pi)
        L = RNG.uniform(10, 60)
        x2, y2 = x + math.cos(a) * L, y + math.sin(a) * L
        d.line([(x, y), (x2, y2)], fill=int(RNG.uniform(40, 120)), width=1)
    big = np.asarray(img.filter(ImageFilter.GaussianBlur(0.8)), np.float32) / 255
    big = big.reshape(2, n, 2, n).sum(axis=(0, 2))  # fold 2x2 -> periodic
    fib = big / big.max()
    tooth = periodic_noise(n, 1.1, seed=11)
    cloud = periodic_noise(n, 60, seed=12)
    h = 0.55 * fib + 0.35 * tooth + 0.10 * cloud
    height_to_normal(h, 2.2).save(f"{OUT}/paper_normal.png")
    # albedo variation: cream with faint mottle, packed as a multiplier
    alb = 0.965 + 0.035 * (cloud - 0.5) * 2 - 0.02 * fib
    base = srgb("#ece2cb")
    rgb = np.clip(base[None, None, :] * alb[..., None], 0, 1)
    to_img(rgb).save(f"{OUT}/paper_color.png")
    # roughness (G) only; occlusion R=1, metal B=0
    r = 0.62 + 0.10 * (tooth - 0.5) + 0.06 * (cloud - 0.5)
    orm = np.stack([np.ones_like(r), r, np.zeros_like(r)], -1)
    to_img(orm).save(f"{OUT}/paper_orm.png")


# ---------------------------------------------------------------- brushed steel
def brushed_tiles(n=1024):
    streak = periodic_noise(n, 900, 0.7, seed=21)  # very long horizontal streaks
    streak2 = periodic_noise(n, 200, 1.5, seed=22)
    blot = periodic_noise(n, 90, seed=23)
    h = 0.6 * streak + 0.4 * streak2
    height_to_normal(h, 0.9).save(f"{OUT}/brushed_normal.png")
    r = 0.30 + 0.16 * (h - 0.5) + 0.08 * (blot - 0.5)
    orm = np.stack([np.ones_like(r), r, np.ones_like(r)], -1)
    to_img(orm).save(f"{OUT}/brushed_orm.png")


# ---------------------------------------------------------------- powder-coat (machine body)
def powder_tiles(n=512):
    orange = periodic_noise(n, 2.2, seed=31)
    height_to_normal(orange, 1.4).save(f"{OUT}/powder_normal.png")


# ---------------------------------------------------------------- soft serve micro surface
def froyo_tiles(n=1024):
    # tiny air pockets + creamy undulation; tiled along the extruded rope
    pores = periodic_noise(n, 1.4, seed=41)
    pores = np.clip((pores - 0.62) * 6, 0, 1)
    pores = ndimage.gaussian_filter(pores, 0.8, mode="wrap")
    wave = periodic_noise(n, 30, 8, seed=42)
    h = 0.7 * wave - 0.5 * pores
    height_to_normal(h, 2.4).save(f"{OUT}/froyo_normal.png")
    r = 0.36 + 0.10 * (wave - 0.5) + 0.25 * pores
    orm = np.stack([np.ones_like(r), r, np.zeros_like(r)], -1)
    to_img(orm).save(f"{OUT}/froyo_orm.png")


# ---------------------------------------------------------------- the Ilios sun emblem
def sun_emblem(S=4096, out_px=2048):
    """Gold-foil Helios sun face + ILIOS / FROYO wordmark, as an alpha decal.

    Layers drawn at S then downsampled (4x4 supersampling at 2048 out):
      foil   - where gold foil is laid (alpha)
      etch   - engraved lines inside the foil (darker, rougher, recessed)
    """
    cx, cy = S * 0.5, S * 0.395
    R0 = S * 0.175            # face disk radius
    R1 = S * 0.355            # longest ray tip
    foil = Image.new("L", (S, S), 0)
    etch = Image.new("L", (S, S), 0)
    df, de = ImageDraw.Draw(foil), ImageDraw.Draw(etch)

    def P(r, a, off=0.0):
        # polar -> xy, with a sideways offset perpendicular to the ray
        x = cx + math.cos(a) * r - math.sin(a) * off
        y = cy + math.sin(a) * r + math.cos(a) * off
        return (x, y)

    # flame rays: 16 long wavy, 16 short pointed, interleaved
    n = 16
    for i in range(n):
        a = -math.pi / 2 + i * 2 * math.pi / n
        left, right = [], []
        steps = 90
        for s in range(steps + 1):
            t = s / steps
            r = R0 * 0.92 + t * (R1 - R0 * 0.92)
            half = S * 0.026 * (1 - t) ** 0.85 + S * 0.0012
            wob = S * 0.017 * math.sin(t * math.pi * 2.35 + 0.4) * min(1, t * 3)
            left.append(P(r, a, wob - half))
            right.append(P(r, a, wob + half))
        df.polygon(left + right[::-1], fill=255)
        # engraved centre vein on each long ray
        vein = [P(R0 * 1.06 + (t / 40) * (R1 - R0 * 1.06) * 0.8, a,
                  S * 0.017 * math.sin((t / 40) * 0.8 * math.pi * 2.35 + 0.4) * min(1, (t / 40) * 2.4))
                for t in range(41)]
        de.line(vein, fill=255, width=int(S * 0.0035))
        # short pointed ray in between
        b = a + math.pi / n
        r2 = R0 + (R1 - R0) * 0.55
        df.polygon([P(R0 * 0.95, b, -S * 0.02), P(r2, b, 0), P(R0 * 0.95, b, S * 0.02)], fill=255)

    # face disk + engraved double ring
    df.ellipse([cx - R0, cy - R0, cx + R0, cy + R0], fill=255)
    w = int(S * 0.0042)
    for rr in (R0 * 0.985, R0 * 0.90):
        de.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=255, width=w)

    R = R0 * 0.86
    lw = int(S * 0.0048)

    def Q(x, y):
        return (cx + x * R, cy + y * R)

    def curve(pts, width=lw):
        # Catmull-Rom through pts for smooth engraved strokes
        out = []
        p = [pts[0]] + pts + [pts[-1]]
        for i in range(1, len(p) - 2):
            for k in range(16):
                t = k / 16
                t2, t3 = t * t, t * t * t
                x = 0.5 * ((2 * p[i][0]) + (-p[i - 1][0] + p[i + 1][0]) * t +
                           (2 * p[i - 1][0] - 5 * p[i][0] + 4 * p[i + 1][0] - p[i + 2][0]) * t2 +
                           (-p[i - 1][0] + 3 * p[i][0] - 3 * p[i + 1][0] + p[i + 2][0]) * t3)
                y = 0.5 * ((2 * p[i][1]) + (-p[i - 1][1] + p[i + 1][1]) * t +
                           (2 * p[i - 1][1] - 5 * p[i][1] + 4 * p[i + 1][1] - p[i + 2][1]) * t2 +
                           (-p[i - 1][1] + 3 * p[i][1] - 3 * p[i + 1][1] + p[i + 2][1]) * t3)
                out.append(Q(x, y))
        out.append(Q(*pts[-1]))
        de.line(out, fill=255, width=width, joint="curve")

    for sgn in (-1, 1):
        # brow: long arch flowing into the nose bridge
        curve([(sgn * 0.70, -0.20), (sgn * 0.52, -0.36), (sgn * 0.28, -0.38), (sgn * 0.10, -0.27),
               (sgn * 0.07, -0.05), (sgn * 0.09, 0.18)])
        # upper lid
        curve([(sgn * 0.58, -0.10), (sgn * 0.44, -0.20), (sgn * 0.28, -0.20), (sgn * 0.16, -0.12)])
        # lower lid
        curve([(sgn * 0.56, -0.10), (sgn * 0.42, -0.04), (sgn * 0.27, -0.05), (sgn * 0.16, -0.12)],
              width=int(lw * 0.8))
        # iris
        ix, iy, ir = sgn * 0.36 * R, -0.115 * R, 0.062 * R
        de.ellipse([cx + ix - ir, cy + iy - ir, cx + ix + ir, cy + iy + ir], fill=255)
        # nostril wing
        curve([(sgn * 0.02, 0.27), (sgn * 0.12, 0.29), (sgn * 0.17, 0.22), (sgn * 0.12, 0.16)])
        # cheek contour
        curve([(sgn * 0.62, 0.05), (sgn * 0.60, 0.28), (sgn * 0.48, 0.52)], width=int(lw * 0.7))
    # lips: cupid's bow, mouth line, lower lip
    curve([(-0.26, 0.47), (-0.12, 0.40), (0.0, 0.44), (0.12, 0.40), (0.26, 0.47)])
    curve([(-0.27, 0.48), (-0.10, 0.51), (0.10, 0.51), (0.27, 0.48)])
    curve([(-0.20, 0.52), (0.0, 0.62), (0.20, 0.52)])
    # chin
    curve([(-0.14, 0.76), (0.0, 0.80), (0.14, 0.76)], width=int(lw * 0.8))

    # wordmark under the sun: ILIOS large-tracked, FROYO smaller
    def tracked(text, font, y, track):
        widths = [df.textlength(ch, font=font) for ch in text]
        total = sum(widths) + track * (len(text) - 1)
        x = cx - total / 2
        for ch, wch in zip(text, widths):
            df.text((x, y), ch, font=font, fill=255, anchor="ls")
            x += wch + track

    serif = ImageFont.truetype(find_font("Italiana-Regular.ttf"), int(S * 0.066))
    small = ImageFont.truetype(find_font("Italiana-Regular.ttf"), int(S * 0.042))
    tracked("ILIOS", serif, S * 0.865, S * 0.020)
    tracked("FROYO", small, S * 0.935, S * 0.018)

    foil_a = np.asarray(foil, np.float32) / 255
    etch_a = np.asarray(etch, np.float32) / 255 * foil_a
    # tiny foil grain so the gold breaks up under light like real hot-stamp foil
    grain = periodic_noise(S // 4, 1.2, seed=51)
    grain = np.kron(grain, np.ones((4, 4)))[:S, :S]

    def down(a):
        return np.asarray(to_img(a).resize((out_px, out_px), Image.LANCZOS), np.float32) / 255

    fa, ea, gr = down(foil_a), down(etch_a), down(grain)
    gold = srgb("#b48a44")
    deep = srgb("#6e4e1d")
    col = gold[None, None] * (1 - ea[..., None]) + deep[None, None] * ea[..., None]
    col *= (0.94 + 0.12 * gr)[..., None]
    rgba = np.concatenate([col, fa[..., None]], -1)
    to_img(rgba).save(f"{OUT}/emblem_color.png")
    rough = 0.24 + 0.30 * ea + 0.08 * (gr - 0.5)
    metal = np.clip(1.0 - 0.35 * ea, 0, 1)
    to_img(np.stack([np.ones_like(rough), rough, metal], -1)).save(f"{OUT}/emblem_orm.png")
    hgt = ndimage.gaussian_filter(fa - 0.7 * ea, 1.4)
    height_to_normal(hgt, 3.5, wrap=False).save(f"{OUT}/emblem_normal.png")
    # flat preview on paper for review
    paper = srgb("#f1e9d6")
    prev = paper[None, None] * (1 - fa[..., None]) + col * fa[..., None]
    to_img(prev).save(f"{OUT}/_emblem_preview.png")


# ---------------------------------------------------------------- machine badge
def badge(S=1024):
    """Small round sun badge for the machine front: reuse the emblem art."""
    em = Image.open(f"{OUT}/emblem_color.png")
    w = em.size[0]
    crop = em.crop((int(w * 0.13), int(w * 0.04), int(w * 0.87), int(w * 0.78))).resize((S, S), Image.LANCZOS)
    crop.save(f"{OUT}/badge_color.png")
    Image.open(f"{OUT}/emblem_orm.png").crop((int(w * 0.13), int(w * 0.04), int(w * 0.87), int(w * 0.78))) \
        .resize((S, S), Image.LANCZOS).save(f"{OUT}/badge_orm.png")
    Image.open(f"{OUT}/emblem_normal.png").crop((int(w * 0.13), int(w * 0.04), int(w * 0.87), int(w * 0.78))) \
        .resize((S, S), Image.LANCZOS).save(f"{OUT}/badge_normal.png")


# ---------------------------------------------------------------- marble counter
def marble(n=2048):
    """Warm white Greek marble: soft grey-taupe veins from turbulent bands."""
    t1 = periodic_noise(n, 140, seed=61)
    t2 = periodic_noise(n, 40, seed=62)
    t3 = periodic_noise(n, 10, seed=63)
    turb = 0.55 * t1 + 0.3 * t2 + 0.15 * t3
    yy, xx = np.mgrid[0:n, 0:n] / n
    # bands run diagonally; integer frequencies keep the tile seamless
    # thin, sparse veins: a narrow gaussian around the zero-crossings of a warped band
    phase = 2 * math.pi * (1 * xx + 1 * yy) + 2.2 * (0.85 * t1 + 0.15 * t2)
    vein = np.exp(-(np.sin(phase) / 0.045) ** 2)
    phase2 = 2 * math.pi * (3 * xx - 1 * yy) + 2.6 * (0.3 * t2 + 0.7 * t1)
    vein2 = np.exp(-(np.sin(phase2) / 0.03) ** 2) * 0.45
    v = 1 - np.clip(vein * (0.55 + 0.45 * t2) + vein2 * t3, 0, 1)
    base = srgb("#efebe4")
    veinc = srgb("#8f877c")
    cloud = periodic_noise(n, 220, seed=64)
    col = base[None, None] * (0.97 + 0.04 * cloud[..., None])
    col = col * v[..., None] + veinc[None, None] * (1 - v[..., None])
    to_img(col).save(f"{OUT}/marble_color.jpg", quality=92)
    r = 0.16 + 0.10 * (1 - v) + 0.05 * t3
    to_img(np.stack([np.ones_like(r), r, np.zeros_like(r)], -1)).save(f"{OUT}/marble_orm.png")


if __name__ == "__main__":
    paper_tiles()
    brushed_tiles()
    powder_tiles()
    froyo_tiles()
    sun_emblem()
    badge()
    marble()
    print("textures ->", OUT)
