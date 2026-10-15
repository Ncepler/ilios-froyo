"""Soft-serve pour: a viscous rope simulated with position-based dynamics.

    python sim.py <out_dir>

What it models (cup-local frame, metres, Y up, the cup's inside floor near y = 0.0068):
  - extrusion: rope leaves the star spout at a steady speed (a kinematic section inside the spout)
  - gravity, with the falling column stretching and thinning (radius from volume conservation)
  - bending stiffness, so it folds in loops rather than kinks
  - collisions with the cup floor and conical wall and with the rope already laid down
  - yield stress: once a piece has landed and slowed down, it sets and stays put
  - the server's hand: the cup circles under the spout so the rope lays down as a swirl
  - the end: the valve closes, the tail detaches at the spout, falls, and folds over into the tip

Output (`pour-sim.bin` + `pour-sim.json`): per particle its emit frame, settle frame, and its
trajectory between them (int16, 20 µm steps), plus the cup offset for every frame. The website
scrubs through it; build.py turns the final frame into the static swirl.
"""
import json
import math
import os
import sys

import numpy as np
from scipy.spatial import cKDTree

OUT = sys.argv[1] if len(sys.argv) > 1 else "sim"
os.makedirs(OUT, exist_ok=True)

# ---------------------------------------------------------------- cup geometry (matches build.py)
H, RT, RB, T, ZB = 0.0620, 0.0455, 0.0340, 0.00055, 0.0068
SLOPE = (RT - RB) / (H - 0.0016 - 0.0015)


def r_in(y):
    return RB + (y - 0.0015) * SLOPE - T * math.sqrt(1 + SLOPE * SLOPE)


def r_in_v(y):
    return RB + (y - 0.0015) * SLOPE - T * math.sqrt(1 + SLOPE * SLOPE)


# ---------------------------------------------------------------- material + pour
A = 0.0089            # rope radius at the spout (6-point star, ~18 mm across)
D = 0.0030            # particle spacing along the rope at rest
VE = 0.20             # extrusion speed, m/s
LEN = 1.42            # rope length poured into one cup
G = np.array([0.0, -9.81, 0.0])
NOZ_Y = 0.362 - 0.0649          # spout exit height above the cup's base
SPOUT_LEN = 0.016               # kinematic length inside the spout
FPS = 60
SUB = 12                        # substeps per frame
ITER = 3                        # constraint iterations per substep
H_SUB = 1.0 / (FPS * SUB)
BEND = 0.012                    # bending stiffness (per iteration): a soft paste, not a rod
STRETCH = 0.9                   # elastic stiffness of a link toward its (plastic) rest length
PLASTIC_UP = 0.0035             # per substep: how fast stretch becomes permanent (viscous flow)
PLASTIC_DN = 0.006              # per substep: how fast squash becomes permanent (it fattens)
MAX_STRETCH = 1.4               # a link can draw out to this many times its length before it would break
OMEGA_MAX = 6.5                 # rad/s, the fastest the server's hand circles
CONTACT = 2 * A * 0.80          # rope-rope contact distance (some squash, so coils merge)
SETTLE_V = 0.05                 # m/s: slower than this while touching -> it sets
SETTLE_T = 0.22                 # s it has to stay slow and touching first (upright pieces)
SETTLE_FAST = 0.03              # s for pieces lying flat
TAIL_HOLD = 0.08                # s the spout keeps hold of the tail after the valve closes

T_EMIT = LEN / VE
T_END = T_EMIT + 1.1
NFRAMES = int(T_END * FPS) + 1


# ---------------------------------------------------------------- the server's hand
LAYER_L = 0.20          # rope per flat layer inside the cup (a spiral from the middle to the wall)
N_LAYERS = 4            # layers to fill the cup up to the rim
DOME_STEP = 0.0088      # how far each dome coil steps inward (m per turn)
L_IN = LAYER_L * N_LAYERS


def plan_radius(l):
    """Coil radius the server aims for, as a function of rope already laid (m).

    Inside the cup: flat spiral layers, out then back in, so the cup fills solid.
    Above the rim: one inward spiral with an even step per turn, which stacks into the dome.
    """
    rmin = 0.006
    if l < L_IN:
        k = int(l / LAYER_L)
        q = (l - k * LAYER_L) / LAYER_L
        y = ZB + A + (k + 0.5) * (H - ZB - A) / N_LAYERS
        wall = r_in(y) - 1.05 * A
        f = math.sqrt(q) if k % 2 == 0 else math.sqrt(1 - q)     # constant spacing: area grows linearly
        return rmin + (wall - rmin) * f
    rho0 = r_in(H) - 1.45 * A
    rr = rho0 * rho0 - DOME_STEP * (l - L_IN) / math.pi
    return max(0.0035, math.sqrt(max(rr, 0.0)))


def build_plan():
    """Nozzle position over the cup (cup-local x,z) for every substep, by integrating
    the angle so the cup's surface speed under the spout matches the laying speed."""
    n = int(T_END / H_SUB) + 2
    xz = np.zeros((n, 2))
    th = math.radians(200)
    t_land = 0.62                       # first rope reaches the cup floor (from a test run)
    for k in range(n):
        t = k * H_SUB
        l = max(0.0, VE * (t - t_land))
        rho = plan_radius(min(l, LEN)) * min(1.0, max(0.0, (t - t_land) / 0.4))
        if t > t_land:
            th += min(OMEGA_MAX, VE * 1.2 / max(rho, 0.010)) * H_SUB

        if t > T_EMIT + 0.25:
            # after the valve closes the hand drifts back to centre and stops
            f = min(1.0, (t - T_EMIT - 0.25) / 0.5)
            rho *= 1 - f
        xz[k] = (rho * math.cos(th), rho * math.sin(th))
    # smooth the hand a little (no robot jerks)
    from scipy.ndimage import gaussian_filter1d
    xz[:, 0] = gaussian_filter1d(xz[:, 0], 40)
    xz[:, 1] = gaussian_filter1d(xz[:, 1], 40)
    return xz


PLAN = build_plan()

# ---------------------------------------------------------------- state
NMAX = int(LEN / D) + int(SPOUT_LEN / D) + 8
X = np.zeros((NMAX, 3))
V = np.zeros((NMAX, 3))
alive = np.zeros(NMAX, bool)
kin = np.zeros(NMAX, bool)          # inside the spout, moved by extrusion
frozen = np.zeros(NMAX, bool)
slow_t = np.zeros(NMAX)
emit_frame = np.full(NMAX, -1, np.int32)
freeze_frame = np.full(NMAX, -1, np.int32)
emit_t = np.zeros(NMAX)
REST = np.full(NMAX, D)             # rest length of link i -> i+1 (grows with plastic stretch)
traj = [[] for _ in range(NMAX)]
n = 0
detached = False
t = 0.0
cup_off = []                        # cup offset (x, z) per frame = -nozzle xz


CTRL = np.zeros(2)                  # the server's correction, from watching where the rope lands
KP = 0.9                             # how hard they steer toward the target
CTRL_TAU = 0.12                      # s, how quickly the hand reacts
CTRL_MAX = 0.03                      # m, the most they'll offset from the plan


def plan_xz(t):
    k = min(len(PLAN) - 1, int(t / H_SUB))
    return PLAN[k]


def nozzle_xz(t):
    return plan_xz(t) + CTRL


def landing_point():
    """Where the rope is touching down now: the first piece of the falling column near the pile."""
    fz = np.nonzero(frozen[:n])[0]
    start = (fz.max() - 6) if len(fz) else 0
    col = np.arange(max(start, 0), n)
    col = col[alive[col] & ~kin[col] & ~frozen[col]]
    if len(col) == 0:
        return None
    i = col[np.argmin(X[col, 1])]          # the lowest point of the falling column
    if X[i, 1] > 0.17:
        return None
    return X[i, [0, 2]]


def emit(t):
    global n
    nx, nz = nozzle_xz(t)
    X[n] = (nx, NOZ_Y + SPOUT_LEN, nz)
    V[n] = (0, -VE, 0)
    alive[n] = True
    kin[n] = True
    emit_t[n] = t
    n += 1


def radii():
    """Rope radius per particle from volume conservation: stretched -> thinner, squashed -> fatter."""
    if n < 2:
        return np.full(max(n, 1), A)
    rr = A * np.sqrt(D / REST[:n - 1])
    r = np.empty(n)
    r[0] = rr[0]
    r[-1] = rr[-1]
    r[1:-1] = 0.5 * (rr[:-1] + rr[1:])
    return r


def solve_links(Xp, w, k):
    """Distance constraints between neighbours (alternating even/odd for Gauss-Seidel speed)."""
    for par in (0, 1):
        i = np.arange(par, n - 1, 2)
        if len(i) == 0:
            continue
        j = i + 1
        d = Xp[j] - Xp[i]
        L = np.linalg.norm(d, axis=1) + 1e-12
        ws = w[i] + w[j]
        ok = ws > 0
        c = (L - REST[i]) / L
        corr = (k * c / np.where(ok, ws, 1))[:, None] * d
        Xp[i] += (w[i] * ok)[:, None] * corr
        Xp[j] -= (w[j] * ok)[:, None] * corr


def solve_bend(Xp, w):
    i = np.arange(0, n - 2)
    if len(i) == 0:
        return
    mid = 0.5 * (Xp[i] + Xp[i + 2])
    delta = mid - Xp[i + 1]
    wm = w[i + 1]
    Xp[i + 1] += (BEND * wm)[:, None] * delta
    # equal and opposite share on the ends keeps momentum
    Xp[i] -= (0.5 * BEND * w[i])[:, None] * delta * 0.5
    Xp[i + 2] -= (0.5 * BEND * w[i + 2])[:, None] * delta * 0.5


def collide_cup(Xp, touch, support, rad):
    idx = np.nonzero(alive[:n] & ~kin[:n] & ~frozen[:n])[0]
    if len(idx) == 0:
        return
    P = Xp[idx]
    ri = rad[idx] * 0.92
    # floor
    fl = P[:, 1] < ZB + ri
    P[fl, 1] = (ZB + ri)[fl]
    touch[idx[fl]] = True
    support[idx[fl]] = True
    # conical wall (only inside the cup's height)
    r = np.hypot(P[:, 0], P[:, 2]) + 1e-12
    lim = r_in_v(np.clip(P[:, 1], 0, H)) - ri * np.where(P[:, 1] < H, 1.0, 0.35)
    # inside the cup, and nothing slips over the rim and down the outside
    inside = (P[:, 1] < H + 0.008) & (r > lim)
    s = np.where(inside, lim / r, 1.0)
    P[:, 0] *= s
    P[:, 2] *= s
    touch[idx[inside]] = True
    support[idx[inside & (P[:, 1] < 0.035)]] = True
    Xp[idx] = P


def collide_self(Xp, w, touch, support, rad):
    act = np.nonzero(alive[:n] & ~kin[:n])[0]
    if len(act) < 4:
        return
    tree = cKDTree(Xp[act])
    pairs = tree.query_pairs(CONTACT * 1.25, output_type="ndarray")
    if len(pairs) == 0:
        return
    a, b = act[pairs[:, 0]], act[pairs[:, 1]]
    far = np.abs(a - b) > 3
    a, b = a[far], b[far]
    if len(a) == 0:
        return
    d = Xp[b] - Xp[a]
    L = np.linalg.norm(d, axis=1) + 1e-12
    cd = (rad[a] + rad[b]) * 0.80
    hitm = L < cd
    a, b, d, L, cd = a[hitm], b[hitm], d[hitm], L[hitm], cd[hitm]
    if len(a) == 0:
        return
    ws = w[a] + w[b]
    ok = ws > 0
    c = (L - cd) / L
    corr = (c / np.where(ok, ws, 1))[:, None] * d * 0.8
    np.add.at(Xp, a, (w[a] * ok)[:, None] * corr)
    np.add.at(Xp, b, -(w[b] * ok)[:, None] * corr)
    nrm = d / L[:, None]
    touch[a[frozen[b]]] = True
    touch[b[frozen[a]]] = True
    support[a[frozen[b] & (nrm[:, 1] < -0.35)]] = True
    support[b[frozen[a] & (nrm[:, 1] > 0.35)]] = True


frame = 0
next_emit = 0.0
emitted_len = 0.0
step = 0
while frame < NFRAMES:
    for s in range(SUB):
        # extrusion
        while t >= next_emit and t < T_EMIT and n < NMAX:
            emit(t)
            next_emit += D / VE
        # the server's eye: steer so the touchdown point follows the plan (until the valve closes)
        lp = landing_point()
        if lp is not None and t < T_EMIT:
            err = plan_xz(t) - lp
            want = np.clip(KP * err, -CTRL_MAX, CTRL_MAX)
            CTRL[:] += (want - CTRL) * min(1.0, H_SUB / CTRL_TAU)
        elif t >= T_EMIT:
            CTRL[:] *= 1 - min(1.0, H_SUB / 0.4)
        nx, nz = nozzle_xz(t)
        # kinematic section: pushed down the spout, follows the cup's motion
        k_idx = np.nonzero(kin[:n])[0]
        for i in k_idx:
            y = NOZ_Y + SPOUT_LEN - VE * (t - emit_t[i])
            if t >= T_EMIT + TAIL_HOLD and not detached:
                kin[i] = False
                V[i] = (0, -VE, 0)
                continue
            if y < NOZ_Y and t < T_EMIT:
                kin[i] = False
                V[i] = (0, -VE, 0)
                X[i] = (nx, y, nz)
                continue
            X[i] = (nx, max(y, NOZ_Y - 0.0005), nz) if t < T_EMIT else X[i]
        if t >= T_EMIT + TAIL_HOLD:
            detached = True
            kin[:n] = False

        live = alive[:n]
        w = np.where(live & ~kin[:n] & ~frozen[:n], 1.0, 0.0)
        # predict
        Vn = V[:n]
        Vn[w > 0] += G * H_SUB
        Xp = X[:n].copy()
        Xp[w > 0] += Vn[w > 0] * H_SUB
        touch = np.zeros(n, bool)
        support = np.zeros(n, bool)
        rad = radii()
        for it in range(ITER):
            solve_links(Xp, w, STRETCH)
            solve_bend(Xp, w)
            collide_cup(Xp, touch, support, rad)
            collide_self(Xp, w, touch, support, rad)
        # viscous-plastic flow: links held stretched or squashed keep that shape
        if n > 1:
            L = np.linalg.norm(Xp[1:n] - Xp[:n - 1], axis=1)
            movable = (w[:n - 1] + w[1:n]) > 0
            up = movable & (L > REST[:n - 1] * 1.02)
            dn = movable & (L < REST[:n - 1] * 0.97)
            REST[:n - 1] = np.where(up, REST[:n - 1] + (L - REST[:n - 1]) * PLASTIC_UP, REST[:n - 1])
            REST[:n - 1] = np.where(dn, REST[:n - 1] + (L - REST[:n - 1]) * PLASTIC_DN, REST[:n - 1])
            REST[:n - 1] = np.clip(REST[:n - 1], D * 0.72, D * MAX_STRETCH)
        newV = (Xp - X[:n]) / H_SUB
        # sticky contact: soft serve grabs what it lands on
        newV[touch] *= 0.62
        V[:n] = np.where((w > 0)[:, None], newV * 0.9995, V[:n])
        X[:n] = np.where((w > 0)[:, None], Xp, X[:n])
        # yield stress: slow + touching for a moment -> set
        spd = np.linalg.norm(V[:n], axis=1)
        cand = (w > 0) & touch & support & (spd < SETTLE_V)
        slow_t[:n] = np.where(cand, slow_t[:n] + H_SUB, 0.0)
        # a piece lying flat sets almost at once; one standing up has to topple first
        if n > 2:
            tg = np.zeros((n, 3))
            tg[1:-1] = X[2:n] - X[:n - 2]
            tg[0], tg[-1] = X[1] - X[0], X[n - 1] - X[n - 2]
            tg /= np.linalg.norm(tg, axis=1)[:, None] + 1e-12
            flat = 1.0 - np.abs(tg[:, 1])
            need = np.where(flat > 0.75, SETTLE_FAST, SETTLE_T)
        else:
            need = np.full(n, SETTLE_T)
        newly = cand & (slow_t[:n] >= need)
        if newly.any():
            frozen[:n] |= newly
            V[:n][newly] = 0
            freeze_frame[:n][newly & (freeze_frame[:n] < 0)] = frame
        t += H_SUB
        step += 1
    # record this frame
    for i in range(n):
        if emit_frame[i] < 0:
            emit_frame[i] = frame
        if freeze_frame[i] < 0 or freeze_frame[i] == frame:
            traj[i].append(X[i].copy())
    nx, nz = nozzle_xz(t)
    cup_off.append((-nx, -nz))
    if frame % 60 == 0:
        print(f"frame {frame}/{NFRAMES} particles {n} frozen {int(frozen[:n].sum())}", flush=True)
    frame += 1

# anything still moving at the end sets where it is
for i in range(n):
    if freeze_frame[i] < 0:
        freeze_frame[i] = NFRAMES - 1

# ---------------------------------------------------------------- write
SCALE = 50000.0     # int16 at 20 µm per step (+-0.65 m range)
offsets, lens, data = [], [], []
pos = 0
for i in range(n):
    tr = np.array(traj[i])
    offsets.append(pos)
    lens.append(len(tr))
    data.append(np.round(tr * SCALE).astype(np.int16))
    pos += len(tr)
blob = np.concatenate(data).ravel()
blob.tofile(os.path.join(OUT, "pour-sim.bin"))
final = np.array([traj[i][-1] for i in range(n)])
np.save(os.path.join(OUT, "pour-final.npy"), final)
meta = {
    "note": "Viscous-rope soft-serve pour (PBD). Cup-local metres, Y up. Positions int16 / scale.",
    "fps": FPS, "frames": NFRAMES, "count": int(n), "scale": SCALE, "spacing": D, "radius": A,
    "rest": [round(float(x), 6) for x in REST[:max(n - 1, 1)]],
    "extrusion": VE, "emitEnd": T_EMIT, "spoutY": NOZ_Y,
    "emit": emit_frame[:n].tolist(), "settle": freeze_frame[:n].tolist(),
    "offset": offsets, "length": lens,
    "cupOffset": [[round(a, 6), round(b, 6)] for a, b in cup_off],
}
with open(os.path.join(OUT, "pour-sim.json"), "w") as f:
    json.dump(meta, f)
print("particles", n, "frames", NFRAMES, "samples", pos, "bytes", blob.nbytes)
print("final top y", final[:, 1].max(), "rim", H)
