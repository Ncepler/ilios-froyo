"""More baked and warm things: Biscoff, cookie dough, cinnamon rolls, coconut shreds, kataifi."""
import math

import numpy as np  # noqa: F401

from lib import MM, fbm, lin, mix, piece, rot_matrix, sd_box, sd_capsule, sd_cyl, sd_ellipsoid, sd_plane, sd_sphere, smax, smin, smoothstep, vnoise, worley  # noqa: F401

# key -> dict(fn=builder, n=variants, heap=dict(bowl=..., over=..., phi=...) or None)
PIECES = {}


def _unit(v):
    v = np.asarray(v, dtype=float)
    return v / np.linalg.norm(v)


# ------------------------------------------------------------------ Biscoff bits
# A whole Lotus biscuit is a thin rounded rectangle with a raised border, a bevel on the outer edge and a slightly
# recessed panel. A shard is that biscuit intersected with a few tilted break planes (a snapped edge is pale and
# crumbly, an original edge is dark toasted caramel). Every vertex knows which of the two surfaces it sits on.
_BIS_HX, _BIS_HZ, _BIS_RC = 31.0 * MM, 16.5 * MM, 3.4 * MM
_BIS_T = 3.5 * MM
_BIS_RIM = 2.5 * MM


def _biscuit(Pb, seed):
    """whole biscuit in its own frame (x long, z short, y thickness, centred): the field, and the depth below the outline"""
    x, y, z = Pb[:, 0], Pb[:, 1], Pb[:, 2]
    qx = np.abs(x) - (_BIS_HX - _BIS_RC)
    qz = np.abs(z) - (_BIS_HZ - _BIS_RC)
    d2 = np.hypot(np.maximum(qx, 0), np.maximum(qz, 0)) + np.minimum(np.maximum(qx, qz), 0) - _BIS_RC
    dE = -d2
    top = _BIS_T / 2 - 0.42 * MM * smoothstep(_BIS_RIM - 0.2 * MM, _BIS_RIM + 0.25 * MM, dE)
    top = top + 0.09 * MM * fbm(Pb / (2.2 * MM), 2, seed + 11)
    d = smax(d2, y - top, 1.7 * MM)
    d = smax(d, -(y + _BIS_T / 2), 1.2 * MM)
    return d, dE


def biscoffbits(i):
    rng = np.random.default_rng(7000 + i)
    kind = ['edge', 'inner', 'corner', 'edge', 'inner', 'edge', 'corner', 'inner'][i % 8]
    planes = []                                  # (unit normal xyz, offset from the shard centre)

    def add_plane(theta, rho, tilt=0.2):
        n = _unit([math.cos(theta), rng.uniform(-tilt, tilt), math.sin(theta)])
        planes.append((n, rho))

    d2r = math.pi / 180
    if kind == 'edge':
        long_edge = rng.random() < 0.75
        sgn = rng.choice([-1, 1])
        depth = rng.uniform(6.5, 10.5) * MM
        e = depth * rng.uniform(0.45, 0.55)
        if long_edge:
            th_e = 90 * d2r if sgn > 0 else -90 * d2r
            c = np.array([rng.uniform(-14, 14) * MM, 0, sgn * (_BIS_HZ - e)])
        else:
            th_e = 0 if sgn > 0 else 180 * d2r
            c = np.array([sgn * (_BIS_HX - e), 0, rng.uniform(-6, 6) * MM])
        add_plane(th_e + 180 * d2r + rng.uniform(-18, 18) * d2r, depth - e)
        add_plane(th_e + 90 * d2r + rng.uniform(-22, 22) * d2r, rng.uniform(4.2, 7.6) * MM)
        add_plane(th_e - 90 * d2r + rng.uniform(-22, 22) * d2r, rng.uniform(4.2, 7.6) * MM)
        if rng.random() < 0.55:
            add_plane(th_e + 180 * d2r + rng.choice([-1, 1]) * rng.uniform(35, 55) * d2r, rng.uniform(5.0, 6.8) * MM)
    elif kind == 'corner':
        sx, sz = rng.choice([-1, 1]), rng.choice([-1, 1])
        e1, e2 = rng.uniform(3.2, 5.0) * MM, rng.uniform(3.2, 5.0) * MM
        D1, D2 = rng.uniform(7.5, 11.0) * MM, rng.uniform(6.5, 10.0) * MM
        c = np.array([sx * (_BIS_HX - e1), 0, sz * (_BIS_HZ - e2)])
        add_plane((180 if sx > 0 else 0) * d2r + rng.uniform(-14, 14) * d2r, D1 - e1)
        add_plane((270 if sz > 0 else 90) * d2r + rng.uniform(-14, 14) * d2r, D2 - e2)
        if rng.random() < 0.6:
            add_plane(math.atan2(-sz, -sx) + rng.uniform(-0.3, 0.3), rng.uniform(5.2, 7.0) * MM)
    else:
        c = np.array([rng.uniform(-17, 17) * MM, 0, rng.uniform(-8, 8) * MM])
        K = int(rng.integers(4, 7))
        r0 = rng.uniform(4.3, 6.4) * MM
        th0 = rng.uniform(0, 6.28)
        for j in range(K):
            th = th0 + j * 2 * math.pi / K + rng.uniform(-0.38, 0.38)
            add_plane(th, r0 * (1 + 0.32 * math.cos(2 * (th - th0))) * rng.uniform(0.85, 1.1))
    tone = rng.uniform(-1, 1)
    # a couple of crumbs that cling to the snapped edges, and loose ones near by
    crumbs = []
    for _ in range(int(rng.integers(2, 4))):
        n, rho = planes[int(rng.integers(0, len(planes)))]
        t = rng.uniform(-1, 1)
        tang = np.array([-n[2], 0, n[0]])
        rad = rng.uniform(0.45, 0.85) * MM
        pos = n * (rho + rad * rng.uniform(0.3, 1.8)) + tang * t * 4.0 * MM
        pos[1] = -_BIS_T / 2 + rad * 0.7
        crumbs.append((pos, rad * np.array([1.0, 0.7, rng.uniform(0.8, 1.2)])))
    seed = 40 + i

    def fracture(P):
        Pb = P + c
        fd = None
        for n, rho in planes:
            v = (P @ n) - rho
            fd = v if fd is None else smax(fd, v, 0.5 * MM)
        return fd + 0.26 * MM * fbm(Pb / (1.9 * MM), 2, seed) + 0.07 * MM * vnoise(Pb / (0.55 * MM), seed + 5)

    def body(P):
        Pb = P + c
        b, _ = _biscuit(Pb, seed)
        return smax(b, fracture(P), 0.28 * MM)

    def f(P):
        d = body(P)
        for pos, rad in crumbs:
            d = smin(d, sd_ellipsoid(P, pos, rad), 0.25 * MM)
        return d

    base_top, base_hi, base_lo = lin('#ac6a34'), lin('#bd7e44'), lin('#8e5530')
    base_rim, base_edge = lin('#8a4d24'), lin('#7c4a24')
    pale, pale_hi, pale_lo, under = lin('#d9a465'), lin('#ecc78d'), lin('#b9793a'), lin('#c98a46')

    def paint(V, N, field):
        Pb = V + c
        _, dE = _biscuit(Pb, seed)
        fd = fracture(V)
        wf = smoothstep(-0.55 * MM, -0.06 * MM, fd)                     # snapped surface (and the pale lip around it)
        loose = smoothstep(0.15 * MM, 0.5 * MM, body(V))                # a crumb standing off the piece
        wf = np.maximum(wf, loose)
        x, y, z = Pb[:, 0], Pb[:, 1], Pb[:, 2]
        # caramelised skin: mottled (baked brown here, golden there), darker toward the raised border and on the bevel
        blot = fbm(Pb / (3.4 * MM), 3, seed + 3)
        mott = fbm(Pb / (1.25 * MM), 2, seed + 21)
        col = mix(base_top, base_hi, smoothstep(0.1, 0.7, blot + 0.2 * tone))
        col = mix(col, base_lo, smoothstep(0.0, -0.6, blot + 0.2 * tone) * 0.8)
        col = col * (1 + 0.14 * mott)[:, None]
        rim = smoothstep(_BIS_RIM + 0.7 * MM, _BIS_RIM - 0.5 * MM, dE)
        col = mix(col, base_rim, rim * 0.5)
        col = mix(col, base_edge, smoothstep(1.0 * MM, 0.0, dE) * 0.35)
        # the embossed lattice of the panel, faint
        u, v = (x + z) / (1.35 * MM), (x - z) / (1.35 * MM)
        lat = (np.sin(u * math.tau) * np.sin(v * math.tau)) * smoothstep(_BIS_RIM, _BIS_RIM + 1.5 * MM, dE)
        col = col * (1 + 0.07 * lat)[:, None]
        # air bubbles of the bake: small dark pits; and a few pale flour flecks
        f1, _, _ = worley(Pb / (1.5 * MM), seed + 7)
        col = col * (1 - 0.3 * smoothstep(0.24, 0.1, f1))[:, None]
        h1, _, hc = worley(Pb / (1.1 * MM), seed + 29)
        col = mix(col, pale_hi, smoothstep(0.14, 0.05, h1) * (hc > 0.55) * 0.5)
        # underside is paler and drier; the wall is golden toward the foot
        bottom = smoothstep(-0.1, -0.7, N[:, 1])
        col = mix(col, mix(under, base_top, 0.3 + 0.25 * blot) * (1 + 0.1 * mott)[:, None], bottom * 0.85)
        side = smoothstep(0.65, 0.25, np.abs(N[:, 1])) * (1 - bottom)
        foot = smoothstep(0.4 * MM, -1.4 * MM, y)
        col = mix(col, mix(base_edge, under, foot * 0.7), side * 0.55)
        # snapped surface: pale crumb with flecks
        g1, _, _ = worley(Pb / (0.9 * MM), seed + 13)
        fl = fbm(Pb / (0.8 * MM), 2, seed + 17)
        crumb = mix(pale, pale_hi, smoothstep(0.0, 0.7, fl + 0.15 * tone))
        crumb = mix(crumb, pale_lo, smoothstep(-0.1, -0.6, fl) * 0.5 + smoothstep(0.1, 0.0, g1) * 0.15)
        col = mix(col, crumb, wf)
        rough = np.where(wf > 0.5, 0.97, 0.72 - 0.1 * smoothstep(0.0, 0.5, blot))
        sss = 0.08 + 0.06 * wf
        spec = 0.5 - 0.3 * wf
        return col, rough, sss, spec

    lo, hi = np.array([-11 * MM, -3 * MM, -11 * MM]), np.array([11 * MM, 3 * MM, 11 * MM])
    return piece(f'biscoffbits_{i}', f, lo, hi, 0.48 * MM, paint, smooth=2, cls='matte', flat=True, ao_strength=0.9)


PIECES['biscoffbits'] = dict(fn=biscoffbits, n=8, heap=None)


# ------------------------------------------------------------------ cookie dough
def _surface_along(f, u, rmax):
    """distance from the origin to the (last) crossing of the solid f along direction u"""
    t = np.linspace(0, rmax, 400)
    ins = f(t[:, None] * u[None, :]) < 0
    return t[np.where(ins)[0][-1]] if ins.any() else 0.0


def dough(i):
    rng = np.random.default_rng(8000 + i)
    R = rng.uniform(10.6, 12.2) * MM
    squash = rng.uniform(0.9, 1.08, 3)
    blobs = [(np.zeros(3), 0.7 * R)]
    for _ in range(int(rng.integers(5, 8))):
        u = _unit(rng.normal(size=3))
        r = rng.uniform(0.40, 0.52) * R
        blobs.append((u * (R * rng.uniform(0.93, 1.0) - r), r))

    def base(P):
        Q = P / squash
        d = sd_sphere(Q, blobs[0][0], blobs[0][1])
        for c, r in blobs[1:]:
            d = smin(d, sd_sphere(Q, c, r), 4.0 * MM)
        return d * squash.min()

    def lumpy(P):
        f1, f2, _ = worley(P / (2.4 * MM), 30 + i)
        crease = smoothstep(0.0, 0.3, f2 - f1)
        return base(P) + 0.9 * MM * fbm(P / (6.0 * MM), 3, 50 + i) - 0.4 * MM * (1 - crease) + 0.2 * MM * vnoise(P / (1.3 * MM), 60 + i)

    # chocolate chips: little chunks sunk partway into the surface
    chips = []
    nchips = int(rng.integers(12, 18))
    tries = 0
    while len(chips) < nchips and tries < 300:
        tries += 1
        u = _unit(rng.normal(size=3))
        s = _surface_along(base, u, R * 1.3)
        half = rng.uniform(0.95, 2.0, 3) * MM * np.array([1.0, 0.7, 1.0])
        sink = rng.uniform(0.05, 0.95) * half[1]                      # how far the chip's mid-plane sits below the skin
        ctr = u * (s - sink + 0.2 * MM)
        if any(np.linalg.norm(ctr - c0) < (np.max(half) + np.max(h0)) * 1.15 for c0, h0, _ in chips):
            continue
        # chip's thin axis along the surface normal-ish (they lie in the dough), tilted a bit
        yax = _unit(u + rng.normal(size=3) * 0.35)
        a = _unit(np.cross(yax, rng.normal(size=3)))
        b = np.cross(yax, a)
        Rm = np.stack([a, yax, b], 1)                                  # columns: local x, y, z in world
        chips.append((ctr, half, Rm))

    def chip_field(P):
        d = np.full(len(P), 1.0)
        for ctr, half, Rm in chips:
            q = (P - ctr) @ Rm
            e = sd_box(q, 0, half, 0.55 * MM) + 0.12 * MM * vnoise(q / (0.8 * MM), 70 + i)
            d = np.minimum(d, e)
        return d

    def f(P):
        return smin(lumpy(P), chip_field(P), 0.3 * MM)

    dough_c, dough_lo, dough_hi = lin('#dcc08c'), lin('#cfab72'), lin('#e8d3a3')
    brown, choc, choc_hi, sugar = lin('#9b7442'), lin('#25130c'), lin('#4a2a1a'), lin('#f6efdc')

    def paint(V, N, field):
        dd = lumpy(V)
        cd = chip_field(V)
        wc = smoothstep(0.22 * MM, -0.22 * MM, cd - dd)
        blot = fbm(V / (5 * MM), 3, 80 + i)
        fine = fbm(V / (1.5 * MM), 2, 90 + i)
        col = mix(dough_c, dough_hi, smoothstep(0.1, 0.8, blot))
        col = mix(col, dough_lo, smoothstep(-0.05, -0.7, blot) * 0.55)
        col = col * (1 + 0.07 * fine)[:, None]
        # brown-sugar specks and flour dust
        f1, f2, cid = worley(V / (1.7 * MM), 100 + i)
        col = mix(col, brown, smoothstep(0.26, 0.1, f1) * (cid > 0.55) * 0.6)
        col = mix(col, dough_hi, smoothstep(0.3, 0.1, f1) * (cid < 0.2) * 0.5)
        # creases of the crumbly surface are darker
        crease = smoothstep(0.22, 0.0, f2 - f1)
        col = col * (1 - 0.14 * crease)[:, None]
        # sugar crystals: sparse, glinting
        s1, _, sid = worley(V / (1.15 * MM), 110 + i)
        sg = smoothstep(0.3, 0.12, s1) * (sid > 0.72)
        col = mix(col, sugar, sg * 0.9)
        # chocolate smear on the dough around each chip
        col = mix(col, brown, smoothstep(0.9 * MM, 0.0, cd) * 0.35 * (1 - wc))
        chipcol = mix(choc, choc_hi, smoothstep(0.0, 0.8, fbm(V / (1.2 * MM), 2, 120 + i)) * 0.8)
        col = mix(col, chipcol, wc)
        gl = 0.22 + 0.35 * smoothstep(0.0, 1.0, vnoise(V / (2.6 * MM), 130 + i) * 0.5 + 0.5)
        rough = (0.52 - 0.12 * smoothstep(-0.2, 0.7, blot) + 0.1 * fine) * (1 - wc) + gl * wc
        rough = np.where(sg > 0.4, 0.18, rough)
        sss = 0.16 * (1 - wc) + 0.04 * wc
        spec = 0.85 * (1 - wc) + 1.0 * wc
        spec = np.where(sg > 0.4, 1.0, spec)
        return col, rough, sss, spec

    ext = R * 1.15
    lo, hi = np.array([-ext] * 3), np.array([ext] * 3)
    return piece(f'dough_{i}', f, lo, hi, 1.08 * MM, paint, smooth=2, cls='matte', ao_strength=1.0)


PIECES['dough'] = dict(fn=dough, n=5, heap=dict(bowl='hobnail', over=0.012, phi=0.5))


# ------------------------------------------------------------------ mini cinnamon rolls
def cinnamon(i):
    rng = np.random.default_rng(9000 + i)
    R = rng.uniform(13.2, 14.6) * MM
    H = rng.uniform(12.0, 15.0) * MM
    pitch = rng.uniform(4.1, 4.6) * MM
    rho = 0.56 * pitch                                  # tube radius: neighbouring turns overlap, leaving a groove
    r0 = 1.3 * MM
    b = pitch / math.tau
    th_end = (R - rho - r0) / b                         # the outer arm stops here
    hand = rng.choice([-1.0, 1.0])
    phi_off = rng.uniform(0, 6.28)
    wob = rng.uniform(0, 100)
    drip = rng.uniform(0, 6.28)
    drip2 = drip + rng.choice([-1, 1]) * rng.uniform(0.9, 1.5)
    has2 = rng.random() < 0.6
    seed = 200 + i
    bake = rng.uniform(0.0, 0.2)                          # how well this one is baked

    def arm(P):
        """in-plane distance to the nearest arm of the spiral, and the position between arms (0 on a ridge, 1 in a groove)"""
        x, z = P[:, 0] * hand, P[:, 2]
        r = np.hypot(x, z)
        phi = np.mod(np.arctan2(z, x) + phi_off, math.tau)
        kmax = np.maximum(np.floor((th_end - phi) / math.tau), 0)
        u = (r - r0 - b * phi) / pitch
        k = np.clip(np.round(u), 0, kmax)
        rk = r0 + b * (phi + math.tau * k)
        dp = np.abs(r - rk) / np.sqrt(1 + (b / np.maximum(r, 1e-6)) ** 2)
        return dp, r, phi

    def top_c(r):
        return H - rho - 2.4 * MM * smoothstep(0.35 * R, 1.0 * R, r) - 0.6 * MM

    def dough_f(P):
        dp, r, phi = arm(P)
        y = P[:, 1]
        dy = np.maximum(np.maximum(y - top_c(r), rho * 0.5 - y), 0)
        d = np.hypot(dp, dy) - rho
        d = np.minimum(d, sd_cyl(P, (0, 0.5 * (H - 1.5 * MM), 0), 0.5 * (H - 1.5 * MM), 2.2 * MM) * 1.0)
        d = smax(d, -y, 0.8 * MM)
        d = smax(d, r - (R - 0.2 * MM), 0.6 * MM)
        return d + 0.3 * MM * fbm(P / (4.5 * MM), 2, seed) + 0.1 * MM * vnoise(P / (1.2 * MM), seed + 3)

    # icing: a pool on the top (off centre, toward the drip) that fills the grooves, and a rivulet running down the wall
    oc = np.array([math.cos(drip), math.sin(drip)]) * 0.27 * R
    drip_len = rng.uniform(6.5, 9.0) * MM
    drip2_len = rng.uniform(4.0, 6.0) * MM

    def pool(P):
        x, y, z = P[:, 0], P[:, 1], P[:, 2]
        r = np.hypot(x, z)
        qx, qz = x - oc[0], z - oc[1]
        rq = np.hypot(qx, qz)
        pq = np.arctan2(qz, qx)
        rp = 0.55 * R + 1.3 * MM * np.sin(2 * pq + wob) + 0.9 * MM * np.sin(3 * pq + 2 * wob)
        ypool = H + 0.1 * MM - 2.0 * MM * smoothstep(0.1 * R, 0.95 * R, r) + 0.25 * MM * np.sin(r / (2.6 * MM) + wob)
        d = smax(rq - rp, y - ypool, 1.5 * MM)
        return smax(d, (ypool - 3.4 * MM) - y, 0.8 * MM)

    def rivulet(P, dd, ph, L, w0):
        """icing coat on the wall of thickness ts(angle, height): narrow, with a fat bead at its end"""
        x, y, z = P[:, 0], P[:, 1], P[:, 2]
        phi = np.arctan2(z, x)
        dphi = np.angle(np.exp(1j * (phi - ph)))
        s = np.clip((H - y) / L, 0, 1.2)
        bead = smoothstep(0.5, 0.92, s)
        tt = (0.75 + 1.0 * bead) * MM * np.sqrt(np.clip(1 - (np.maximum(s - 0.86, 0) / 0.16) ** 2, 0, 1))
        w = w0 * (1 - 0.3 * s + 0.35 * bead)
        lat = np.exp(-((dphi * R) / w) ** 2)
        ts = tt * lat
        return dd - ts + 0.7 * MM * (1 - np.clip(ts / (0.45 * MM), 0, 1))

    def icing(P, dd=None):
        dd = dough_f(P) if dd is None else dd
        d = pool(P)
        d = smin(d, rivulet(P, dd, drip, drip_len, 2.6 * MM), 1.0 * MM)
        if has2:
            d = smin(d, rivulet(P, dd, drip2, drip2_len, 1.8 * MM), 1.0 * MM)
        return d

    def f(P):
        dd = dough_f(P)
        return smin(dd, icing(P, dd), 0.7 * MM)

    dough_c, dough_top, dough_pale, cin = lin('#d9a566'), lin('#b97b3a'), lin('#e4c08a'), lin('#6e3315')
    ice, ice_shadow = lin('#f5efe2'), lin('#ead9c0')

    def paint(V, N, field):
        dd = dough_f(V)
        di = icing(V, dd)
        wi = smoothstep(0.25 * MM, -0.25 * MM, di - dd)
        dp, r, phi = arm(V)
        y = V[:, 1]
        g = smoothstep(0.4, 0.74, dp / (pitch / 2)) * smoothstep(R - 0.9 * MM, R - 2.6 * MM, r)      # in the groove between turns
        blot = fbm(V / (4 * MM), 3, seed + 5)
        fine = fbm(V / (1.2 * MM), 2, seed + 9)
        up = np.clip(N[:, 1], 0, 1)
        # toasted on top and along the ridges; paler, doughy on the walls
        toast = smoothstep(0.3, 1.0, up * (0.55 + 0.45 * smoothstep(0.0, 0.6, 1 - g)) + 0.3 * blot + bake)
        col = mix(dough_pale, dough_c, 0.7 + 0.3 * blot + 2 * bake)
        col = mix(col, dough_top, toast * (0.7 + 0.25 * fine))
        col = mix(col, dough_top, smoothstep(2.0 * MM, 0.0, y) * 0.5)       # the foot browned by the pan
        # cinnamon-sugar swirl between the turns and at the spiral's cut ends
        swirl = np.maximum(g, smoothstep(1.0 * MM, 0.0, r - (R - 1.6 * MM)) * 0.0)
        cinc = mix(cin, lin('#8a4a22'), 0.4 * smoothstep(0.0, 0.8, fbm(V / (0.9 * MM), 2, seed + 13) + 0.4))
        col = mix(col, cinc, swirl * 0.92)
        # sugar glints in the swirl
        s1, _, sid = worley(V / (0.9 * MM), seed + 15)
        col = mix(col, lin('#c9894c'), smoothstep(0.3, 0.12, s1) * (sid > 0.6) * swirl * 0.7)
        # icing: cream, warmer where it is thin over the dough, with faint creases
        ic = mix(ice, ice_shadow, smoothstep(-0.1, 0.8, 0.5 - 0.5 * N[:, 1]) * 0.35 + 0.15 * smoothstep(0.0, 0.7, fbm(V / (3 * MM), 2, seed + 21)))
        ic = mix(ic, dough_pale, smoothstep(0.9 * MM, 0.1 * MM, dd) * 0.45)
        col = mix(col, ic, wi)
        rough = (0.78 - 0.1 * fine) * (1 - wi) + 0.2 * wi
        sss = 0.15 * (1 - wi) + 0.3 * wi
        spec = 0.5 * (1 - wi) + 1.0 * wi
        return col, rough, sss, spec

    ext = R + 4.0 * MM
    lo, hi = np.array([-ext, -1.0 * MM, -ext]), np.array([ext, H + 1.5 * MM, ext])
    return piece(f'cinnamon_{i}', f, lo, hi, 1.2 * MM, paint, smooth=2, cls='matte', flat=True, ao_strength=1.0)


PIECES['cinnamon'] = dict(fn=cinnamon, n=4, heap=None)


# ------------------------------------------------------------------ swept strips and tubes, built directly (coconut shreds, kataifi)
def _frames(path):
    """parallel-transport frames along a polyline: tangents T, and two perpendiculars N, B (n,3 each)"""
    n = len(path)
    T = np.gradient(path, axis=0)
    T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-12)
    a = np.array([0.0, 1.0, 0.0]) if abs(T[0, 1]) < 0.9 else np.array([1.0, 0.0, 0.0])
    N0 = _unit(np.cross(T[0], a))
    Ns = [N0]
    for i in range(1, n):
        v = Ns[-1] - T[i] * (Ns[-1] @ T[i])
        Ns.append(_unit(v) if np.linalg.norm(v) > 1e-9 else Ns[-1])
    N = np.array(Ns)
    B = np.cross(T, N)
    return T, N, B


def _sweep(path, a, t, theta, sides, blunt=False):
    """a flat/oval section (semi-axes a, t; turned by theta about the path) swept along `path` (n rings).
    The two end rings collapse to a point each. Returns V, N, F, and per-vertex (s along the path, angle around it)."""
    n = len(path)
    T, Nf, Bf = _frames(path)
    if blunt:       # full rings at both ends, closed by a short cap each (a snapped-off end rather than a point)
        path = np.concatenate([(path[0] - T[0] * a[0] * 0.8)[None], path, (path[-1] + T[-1] * a[-1] * 0.8)[None]])
        T = np.concatenate([T[:1], T, T[-1:]])
        Nf = np.concatenate([Nf[:1], Nf, Nf[-1:]])
        Bf = np.concatenate([Bf[:1], Bf, Bf[-1:]])
        a, t, theta = (np.concatenate([x[:1], x, x[-1:]]) for x in (a, t, theta))
        n += 2
    ang = np.linspace(0, math.tau, sides, endpoint=False)
    V, Nn, S, A = [], [], [], []
    V.append(path[0])
    Nn.append(-T[0])
    S.append(0.0)
    A.append(0.0)
    for i in range(1, n - 1):
        c, s_ = math.cos(theta[i]), math.sin(theta[i])
        U = c * Nf[i] + s_ * Bf[i]          # thin direction
        W = -s_ * Nf[i] + c * Bf[i]         # wide direction
        for al in ang:
            ca, sa = math.cos(al), math.sin(al)
            V.append(path[i] + a[i] * ca * W + t[i] * sa * U)
            nn = (ca / max(a[i], 1e-9)) * W + (sa / max(t[i], 1e-9)) * U
            Nn.append(_unit(nn))
            S.append(i / (n - 1))
            A.append(al)
    V.append(path[-1])
    Nn.append(T[-1])
    S.append(1.0)
    A.append(0.0)
    V, Nn, S, A = np.array(V), np.array(Nn), np.array(S), np.array(A)
    F = []
    first_ring = 1
    for k in range(sides):
        F.append((0, first_ring + k, first_ring + (k + 1) % sides))
    for i in range(1, n - 2):
        r0 = 1 + (i - 1) * sides
        r1 = r0 + sides
        for k in range(sides):
            k1 = (k + 1) % sides
            F.append((r0 + k, r1 + k, r1 + k1))
            F.append((r0 + k, r1 + k1, r0 + k1))
    last = 1 + (n - 3) * sides
    end = len(V) - 1
    for k in range(sides):
        F.append((end, last + (k + 1) % sides, last + k))
    F = np.array(F, dtype=np.int64)
    # wind outward: compare face normals with the vertex normals
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    if (np.einsum('ij,ij->i', fn, Nn[F].mean(1)) < 0).mean() > 0.5:
        F = F[:, ::-1].copy()
    return V, Nn, F, S, A


def _finish(name, V, N, F, rgb, rough, ao, sss, spec, cls='matte', flat=False):
    lo, hi = V.min(0), V.max(0)
    Vc = V - (lo + hi) / 2
    return dict(name=name, V=Vc.astype(np.float32), N=N.astype(np.float32), F=F.astype(np.uint32),
                COLOR_0=np.concatenate([rgb, np.asarray(rough)[:, None]], 1).astype(np.float32),
                _DATA=np.stack([ao, sss, spec], 1).astype(np.float32),
                extras=dict(cls=cls, flat=bool(flat), jelly=False, r=float(np.linalg.norm(Vc, axis=-1).max()),
                            size=[float(x) for x in (hi - lo)]))


# ------------------------------------------------------------------ shredded coconut
def coconut(i):
    rng = np.random.default_rng(10000 + i)
    L = rng.uniform(9.0, 16.0) * MM
    M = 240
    ds = L / M
    # a curl: the tangent turns with a smoothly varying curvature in two directions
    f1, f2 = rng.uniform(0.6, 1.8, 2)
    p1, p2 = rng.uniform(0, 6.28, 2)
    k1 = rng.uniform(-0.28, 0.28) / MM
    k2 = rng.uniform(-0.18, 0.18) / MM
    a1, a2 = rng.uniform(0.05, 0.2) / MM, rng.uniform(0.04, 0.16) / MM
    T = np.array([1.0, 0.0, 0.0])
    Nn = np.array([0.0, 1.0, 0.0])
    Bn = np.cross(T, Nn)
    pts = [np.zeros(3)]
    for j in range(M):
        s = j / M
        c1 = k1 + a1 * math.sin(math.tau * f1 * s + p1)
        c2 = k2 + a2 * math.sin(math.tau * f2 * s + p2)
        T = _unit(T + ds * (c1 * Nn + c2 * Bn))
        Nn = _unit(Nn - T * (Nn @ T))
        Bn = np.cross(T, Nn)
        pts.append(pts[-1] + T * ds)
    pts = np.array(pts)
    # resample to 10 rings by arc length
    n = 10
    idx = np.linspace(0, M, n)
    path = np.array([np.interp(idx, np.arange(M + 1), pts[:, k]) for k in range(3)]).T
    s = np.linspace(0, 1, n)
    w0 = rng.uniform(1.2, 2.0) * MM / 2
    a = w0 * (0.8 + 0.25 * np.sin(math.tau * rng.uniform(0.5, 1.5) * s + rng.uniform(0, 6.28)) + 0.12 * rng.normal(size=n)) * (0.55 + 0.45 * np.sin(np.pi * np.clip(s, 0.02, 0.98)) ** 0.6)
    t = np.full(n, 0.5 * MM / 2) * (0.85 + 0.3 * rng.random(n))
    theta = rng.uniform(0, 6.28) + rng.choice([-1, 1]) * rng.uniform(0.35, 1.3) * math.tau * s
    V, N, F, S, A = _sweep(path, a, t, theta, 5)
    cream = rng.uniform(0, 1)
    white, warm, cut = lin('#f6f2e8'), lin('#efe5cc'), lin('#e8dbb8')
    col = mix(white, warm, 0.25 * cream + 0.15 * np.sin(S * 7 + 1.3 * cream) * 0.5 + 0.1)
    col = mix(col, cut, smoothstep(0.12, 0.0, np.minimum(S, 1 - S)) * 0.6)
    edge = np.abs(np.cos(A))                  # 1 at the thin edges of the ribbon
    sss = 0.35 + 0.4 * edge
    sss[0] = sss[-1] = 0.7
    rough = np.full(len(V), 0.7)
    spec = np.full(len(V), 0.6)
    ao = np.full(len(V), 0.95)
    return _finish(f'coconut_{i}', V, N, F, col, rough, ao, sss, spec)


# shreds are 3.6 mm3 each: a full mound is thousands, so it is deposited (fast=True), not simulated
PIECES['coconut'] = dict(fn=coconut, n=8, heap=dict(bowl='hobnail', over=0.004, phi=0.04, fast=True, min_n=5500, max_n=8000, tries=1))      # tries=1: shreds stick where they land, they do not roll downhill


# ------------------------------------------------------------------ kataifi nests
def kataifi(i):
    rng = np.random.default_rng(11000 + i)
    Rn = rng.uniform(7.0, 10.0) * MM                  # nest radius: 14-20 mm across
    Hn = rng.uniform(5.5, 8.0) * MM
    nstr = int(rng.integers(26, 34))
    n = 11
    verts, norms, faces, cols, roughs, aos, ssss, specs = [], [], [], [], [], [], [], []
    base_gold, base_dark, tip_dark, glint = lin('#e2b055'), lin('#a8671f'), lin('#7a4513'), lin('#f4d58a')
    off = 0
    ell = np.array([Rn, Hn, Rn])
    for k in range(nstr):
        # a strand: a persistent random walk with a loop-y wave, kept inside the mound; resampled to n rings
        L = rng.uniform(15.0, 24.0) * MM
        steps = 60
        ds = L / steps
        u = rng.normal(size=3)
        p0 = _unit(rng.normal(size=3)) * rng.uniform(0.0, 0.95, 1) * ell
        p0[1] = abs(p0[1]) + 0.3 * MM
        T = _unit(u)
        side = _unit(np.cross(T, rng.normal(size=3)))
        wl = rng.uniform(2.6, 4.6) * MM
        ph = rng.uniform(0, math.tau)
        turn = rng.uniform(0.022, 0.04)
        om = np.zeros(3)
        pts = [p0]
        for j in range(steps):
            # wave: the heading swings from side to side; plus a smoothly wandering drift (no kinks)
            wob = math.sin(math.tau * (j * ds) / wl + ph) * 0.2
            om = 0.9 * om + rng.normal(size=3) * turn
            T = _unit(T + side * wob * 0.5 + om)
            q = pts[-1]
            e = np.linalg.norm(q / (ell * 1.04))
            if e > 0.92:                                   # steer back into the mound
                T = _unit(T - _unit(q / ell ** 2) * (e - 0.8) * 0.5)
            if q[1] < 0.35 * MM and T[1] < 0:              # the floor
                T = _unit(np.array([T[0], -T[1] * 0.6, T[2]]))
            side = _unit(side - T * (side @ T))
            pts.append(q + T * ds)
        pts = np.array(pts)
        # squeeze whatever sprawled outside the mound back onto its skin (a smooth map, so no kinks)
        e = np.linalg.norm(pts / ell, axis=1)
        e2 = np.where(e < 0.78, e, 0.78 + 0.27 * np.tanh((e - 0.78) / 0.27))
        pts = pts * (e2 / np.maximum(e, 1e-9))[:, None]
        idx = np.linspace(0, steps, n)
        path = np.array([np.interp(idx, np.arange(steps + 1), pts[:, c]) for c in range(3)]).T
        path[:, 1] = np.maximum(path[:, 1], 0.22 * MM)
        rad = rng.uniform(0.17, 0.24) * MM
        a = np.full(n, rad)
        V, N, F, S, A = _sweep(path, a, a.copy(), np.zeros(n), 3, blunt=True)
        verts.append(V)
        norms.append(N)
        faces.append(F + off)
        off += len(V)
        # colour: one tone per strand, toasted darker toward the ends and deeper in the nest, glints on the crest
        tone = rng.uniform(0, 1)
        gold = mix(base_gold, base_dark, 0.02 + 0.8 * tone ** 1.3)
        gold = gold * (0.9 + 0.2 * rng.random())
        col = np.repeat(gold[None, :], len(V), 0)
        col = mix(col, tip_dark, smoothstep(0.16, 0.0, np.minimum(S, 1 - S)) * 0.85)
        e = np.linalg.norm(V / (ell * 1.0), axis=1)
        ao = np.clip(1.08 - 0.62 * (1 - np.clip(e, 0, 1)) ** 1.2 - 0.25 * (1 - np.clip(V[:, 1] / Hn, 0, 1)), 0.4, 1.0)
        crest = np.clip((V[:, 1] / Hn - 0.45) * 1.8, 0, 1)
        col = mix(col, glint, crest * (0.5 if rng.random() < 0.4 else 0.15))
        cols.append(col)
        aos.append(ao)
        roughs.append(np.full(len(V), 0.36) + 0.2 * (1 - tone))
        ssss.append(np.full(len(V), 0.12))
        specs.append(np.full(len(V), 0.95))
    V = np.concatenate(verts)
    return _finish(f'kataifi_{i}', V, np.concatenate(norms), np.concatenate(faces), np.concatenate(cols), np.concatenate(roughs),
                   np.concatenate(aos), np.concatenate(ssss), np.concatenate(specs))


PIECES['kataifi'] = dict(fn=kataifi, n=4, heap=None)
