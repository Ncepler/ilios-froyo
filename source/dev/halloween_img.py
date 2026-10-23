"""Night-grade the /2/ photos for the Halloween page:  python3 source/dev/halloween_img.py

Reads site/2/img/, writes site/2/halloween/img/. Each photo goes from a bright cream studio to a dark
room with one spotlight on the cup, a pumpkin glow from low left, and the gold sun print turned pumpkin.
The white swirls (tart, vanilla, the hero) get a small ghost face."""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

here = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(here, '..', '..', 'site', '2', 'img')
DST = os.path.join(here, '..', '..', 'site', '2', 'halloween', 'img')


def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def blur(a, r):
    """Three box passes along each axis, close enough to a gaussian."""
    r = int(r)
    for _ in range(3):
        for ax in (0, 1):
            c = np.cumsum(np.pad(a, [(r + 1, r) if i == ax else (0, 0) for i in range(2)], mode='edge'), axis=ax)
            a = (np.take(c, range(2 * r + 1, c.shape[ax]), axis=ax) - np.take(c, range(0, c.shape[ax] - 2 * r - 1), axis=ax)) / (2 * r + 1)
    return a


def ghost(im, ex1, ex2, ey, mx, my):
    """Two eyes and an 'oo' mouth, drawn 4x and scaled down so the edges stay soft."""
    w, h = im.size
    k = 4
    erx, ery = .0115 * w, .0175 * w
    ov = Image.new('L', (w * k, h * k), 0)
    d = ImageDraw.Draw(ov)
    ell = lambda cx, cy, rx, ry: d.ellipse([(cx * w - rx) * k, (cy * h - ry) * k, (cx * w + rx) * k, (cy * h + ry) * k], fill=255)
    ell(ex1, ey, erx, ery)
    ell(ex2, ey, erx, ery)
    ell(mx, my, .0075 * w, .0105 * w)
    ov = ov.resize((w, h), Image.LANCZOS).filter(ImageFilter.GaussianBlur(.6))
    im = Image.composite(Image.new('RGB', (w, h), (34, 22, 30)), im, ov)
    hl = Image.new('L', (w * k, h * k), 0)
    d = ImageDraw.Draw(hl)
    for ex in (ex1, ex2):  # catch-lights, so they read as eyes and not holes
        r, cx, cy = .0032 * w, ex * w - erx * .35, ey * h - ery * .45
        d.ellipse([(cx - r) * k, (cy - r) * k, (cx + r) * k, (cy + r) * k], fill=230)
    return Image.composite(Image.new('RGB', (w, h), (255, 255, 255)), im, hl.resize((w, h), Image.LANCZOS))


def grade(im, cx=.5, cy=.45, rx=.42, ry=.42, glow=(.18, .9), lo=.5, br=1):
    im = np.asarray(im).astype(np.float32) / 255
    h, w, _ = im.shape
    y, x = np.mgrid[0:h, 0:w]
    x, y = x / w, y / h
    L = im @ np.array([.2126, .7152, .0722], np.float32)
    # crush the mids: the wall (~.86) falls away while white froyo and cup (~.95) hold.
    # L is softened first so the curve doesn't stretch the source's banding.
    Ls = blur(L, br)
    Ln = smooth(lo, .99, Ls) ** 1.35
    sat = (im.max(-1) - im.min(-1)) / np.maximum(im.max(-1), 1e-3)
    # coloured swirls (pink, latte) and the gold print keep their value, highlights included
    keep = np.clip(blur(smooth(.13, .32, sat), w / 60) * 1.6, 0, 1) * smooth(.07, .12, blur(sat, 2))
    Ln = Ln * (1 - keep) + np.clip(Ls * 1.05, 0, 1) * keep
    spot = 1 - smooth(.55, 1.25, np.sqrt(((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2))
    lum = Ln * (.12 + .88 * spot)
    out = im * (lum / np.maximum(Ls, 1e-3))[..., None]
    out += smooth(.42, .55, sat)[..., None] * spot[..., None] * np.array([.09, -.01, -.06])  # gold print turns pumpkin
    out *= np.array([.97, .98, 1.03])                                                       # moonlit highlights
    out += (1 - lum[..., None]) * np.array([.06, .04, .075])                                 # plum shadows
    g = np.exp(-(((x - glow[0]) / .35) ** 2 + ((y - glow[1]) / .3) ** 2))
    out += g[..., None] * np.array([.55, .22, .04]) * (.35 + .65 * Ln[..., None]) * .55       # pumpkin glow, low left
    out += np.random.default_rng(7).normal(0, .01, out.shape[:2])[..., None]                # grain
    return Image.fromarray((np.clip(out, 0, 1) * 255 + .5).astype(np.uint8))


JOBS = {
    # name: (grade kwargs, ghost face (eye x, eye x, eye y, mouth x, mouth y) or None)
    'hero.webp': ({}, (.395, .475, .382, .437, .404)),
    'cup-tart.webp': ({}, (.45, .53, .372, .49, .396)),
    'cup-vanilla.webp': ({}, (.42, .50, .345, .46, .368)),
    'cup-raspberry.webp': ({}, None),
    'cup-raspberry-twist.webp': ({}, None),
    'cup-coffee.webp': ({}, None),
    'cup-coffee-twist.webp': ({}, None),
    'cup-top.webp': ({'cx': .55}, None),
    'station.webp': ({'cy': .45, 'rx': .5, 'ry': .55, 'glow': (.3, .85), 'lo': .5, 'br': 3}, None),
    'sun-macro.webp': ({'cx': .45, 'cy': .4, 'rx': .5, 'ry': .6}, None),
    'og.jpg': ({'rx': .5, 'ry': .7}, None),
}

if __name__ == '__main__':
    os.makedirs(DST, exist_ok=True)
    for name, (kw, face) in JOBS.items():
        im = Image.open(os.path.join(SRC, name)).convert('RGB')
        if face:
            im = ghost(im, *face)
        out = grade(im, **kw)
        dst = os.path.join(DST, name)
        out.save(dst, quality=76, method=6) if name.endswith('.webp') else out.save(dst, quality=84, optimize=True, progressive=True)
        print(name, os.path.getsize(dst) // 1024, 'KB')
