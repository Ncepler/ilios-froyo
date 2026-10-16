"""Soft-serve froyo pour: a yield-stress paste simulated with the material point method (MLS-MPM).

    DX=0.004 python mpm.py <out_dir>          # quick look
    DX=0.0025 SPF=0.55 python mpm.py <out_dir> # final

What froyo is (and what this models)
  Soft serve is a foam: roughly 40-60 % air by volume (overrun), so about 0.7 kg/L, held together by
  fat and ice crystals. At the machine's serving temperature it is a yield-stress, shear-thinning paste
  (Herschel-Bulkley-type): below a yield stress tau_y it behaves like a soft solid and holds its shape;
  above it, it flows like a thick fluid. That is why a server can build a coil on top of a coil, why the
  coils slump a little and fuse where they touch, and why the stream does not draw out like honey or
  rubber. The tallest column it can carry under its own weight is roughly tau_y / (rho g).

  Model: hyperelastic (Hencky) with a von Mises yield limit and viscous regularisation, the viscoplastic
  return map of Yue et al. 2015 (Continuum Foam). Elastic strain above the yield strain relaxes at a
  rate set by the viscosity:   delta = (|e| - e_y) / (1 + eta / (2 mu dt)),   e_y = tau_y / (2 mu).

The server's hand
  Everything is in the cup's frame: the cup is static and the nozzle circles over it, exactly as the
  cup circles under the nozzle in the shop. Paste is extruded from a star-section nozzle at a steady rate,
  the hand's speed over the surface matches the extrusion speed, and the nozzle height follows the pile
  (a server keeps the spout a finger-width above the swirl). Path: a spiral out to the wall, a few
  turns round the wall as the cup fills, then an inward spiral that builds the dome, and a flick at
  the end as the valve closes.

Output: frames.npy (float16 particle positions per frame), tag.npy (which half of the nozzle each
particle came from: the two flavours of a twist), meta.json.
"""
import json
import math
import os
import sys
import time

import numpy as np
import taichi as ti

ti.init(arch=ti.cpu, cpu_max_num_threads=int(os.environ.get("THREADS", 4)), default_fp=ti.f32, random_seed=3)

OUT = sys.argv[1] if len(sys.argv) > 1 else "mpm_out"
os.makedirs(OUT, exist_ok=True)


def E(name, default):
    return float(os.environ.get(name, default))


# ---------------------------------------------------------------- cup (matches build.py)
H_RIM, RB, RT, TW, ZB = 0.0620, 0.0340, 0.0455, 0.00055, 0.0068
SLOPE = (RT - RB) / (H_RIM - 0.0016 - 0.0015)
TWALL = TW * math.sqrt(1 + SLOPE * SLOPE)


def r_in(y):
    return RB + (y - 0.0015) * SLOPE - TWALL


# ---------------------------------------------------------------- material
RHO = E("RHO", 700.0)            # kg/m3: ~45 % overrun
TAU_Y = E("TAU_Y", 520.0)        # Pa: sized so a swirl can carry ~7-8 cm of its own weight (tau_y / rho g)
MU = E("MU", 15000.0)            # Pa: elastic shear modulus (yield strain = tau_y / 2 mu ~ 1.7 %)
LAM = E("LAM", 60000.0)          # Pa: Lame lambda (compressibility of the foam)
ETA = E("ETA", 14.0)             # Pa s: apparent viscosity at serving shear rates
G = 9.81

# ---------------------------------------------------------------- the pour
A_NOZ = E("A_NOZ", 0.0089)       # nozzle radius
VE = E("VE", 0.15)               # extrusion speed, m/s (about 20 mL/s, a cup in ~15 s... see RUN)
GAP = E("GAP", 0.013)            # nozzle height above the surface under it
RATIO = E("RATIO", 1.0)          # hand speed over the surface / extrusion speed
R0 = E("R0", 0.0335)             # outer ring radius of the hand
N_OUT = E("N_OUT", 1.6)          # turns round the wall
D_RHO = E("D_RHO", 0.0058)       # inward step per turn (m)
RHO_END = E("RHO_END", 0.0035)
OMEGA_MAX = E("OMEGA_MAX", 7.0)
LIFT_RATE = E("LIFT_RATE", 0.10)  # fastest the nozzle rises (the cup lowers)
FLICK_T = E("FLICK_T", 0.50)
FLICK_V = E("FLICK_V", 0.075)
SETTLE_T = E("SETTLE_T", 1.6)
FPS_OUT = int(E("FPS_OUT", 24))
MAX_TIME = E("MAX_TIME", 40.0)

# ---------------------------------------------------------------- grid and particles
DX = E("DX", 0.004)
SP = DX * E("SPF", 0.6)          # particle spacing (also slab thickness)
INV_DX = 1.0 / DX
ORG = np.array([-0.08, -0.012, -0.08])
NX = int(round(0.16 / DX))
NY = int(round(0.236 / DX))
NZ = NX
P_VOL = SP ** 3
P_MASS = RHO * P_VOL
C_WAVE = math.sqrt((LAM + 2 * MU) / RHO)
DT = E("DT", 0.22 * DX / (C_WAVE + 0.45))
YIELD_STRAIN = TAU_Y / (2 * MU)
VISC_DEN = 1.0 + ETA / (2 * MU * DT)

# slab lattice inside the nozzle disc (two halves = two flavours of a twist)
offs, tags = [], []
n_side = int(A_NOZ / SP) + 1
for i in range(-n_side, n_side + 1):
    for j in range(-n_side, n_side + 1):
        px, pz = i * SP, j * SP
        if px * px + pz * pz <= (A_NOZ - 0.4 * SP) ** 2:
            offs.append((px, pz))
            tags.append(1.0 if px > 0 else 0.0)
K = len(offs)
slab_vol = K * P_VOL
est_len = 1.7
NP = int(est_len / SP * K * 1.15) + 1000
print(f"dx={DX*1000:.2f}mm spacing={SP*1000:.2f}mm slab={K} particles, <= {NP} particles, dt={DT*1e6:.0f}us "
      f"c={C_WAVE:.1f}m/s yield strain={YIELD_STRAIN:.3f} visc den={VISC_DEN:.1f}", flush=True)

x = ti.Vector.field(3, ti.f32, NP)
v = ti.Vector.field(3, ti.f32, NP)
C = ti.Matrix.field(3, 3, ti.f32, NP)
F = ti.Matrix.field(3, 3, ti.f32, NP)
tag = ti.field(ti.f32, NP)
born = ti.field(ti.f32, NP)
grid_v = ti.Vector.field(3, ti.f32, (NX, NY, NZ))
grid_m = ti.field(ti.f32, (NX, NY, NZ))
slab_off = ti.Vector.field(2, ti.f32, K)
slab_tag = ti.field(ti.f32, K)
top = ti.field(ti.f32, ())
for i in range(K):
    slab_off[i] = ti.Vector([offs[i][0], offs[i][1]])
    slab_tag[i] = tags[i]


@ti.func
def is_solid(p):
    r = ti.sqrt(p[0] * p[0] + p[2] * p[2])
    s = False
    if p[1] <= ZB:
        s = True
    elif p[1] < H_RIM:
        if r >= RB + (p[1] - 0.0015) * SLOPE - TWALL:
            s = True
    return s


@ti.func
def project(Fm):
    """Hencky strain + von Mises yield with viscous regularisation (Yue et al. 2015)."""
    U, sig, V = ti.svd(Fm)
    e0 = ti.log(ti.max(sig[0, 0], 0.05))
    e1 = ti.log(ti.max(sig[1, 1], 0.05))
    e2 = ti.log(ti.max(sig[2, 2], 0.05))
    tr = e0 + e1 + e2
    if tr > 0.012:               # the foam is cohesive but not a glue: limit tensile volume strain
        shift = (tr - 0.012) / 3.0
        e0 -= shift
        e1 -= shift
        e2 -= shift
        tr = 0.012
    d0 = e0 - tr / 3.0
    d1 = e1 - tr / 3.0
    d2 = e2 - tr / 3.0
    en = ti.sqrt(d0 * d0 + d1 * d1 + d2 * d2)
    if en > YIELD_STRAIN:
        delta = (en - YIELD_STRAIN) / VISC_DEN
        f = delta / en
        e0 -= f * d0
        e1 -= f * d1
        e2 -= f * d2
    S = ti.Matrix([[ti.exp(e0), 0.0, 0.0], [0.0, ti.exp(e1), 0.0], [0.0, 0.0, ti.exp(e2)]])
    return U @ S @ V.transpose()


@ti.kernel
def clear_grid():
    for I in ti.grouped(grid_m):
        grid_v[I] = ti.Vector([0.0, 0.0, 0.0])
        grid_m[I] = 0.0


@ti.kernel
def p2g(n: ti.i32, dt: ti.f32):
    for p in range(n):
        Xp = (x[p] - ti.Vector([ORG[0], ORG[1], ORG[2]])) * INV_DX
        base = (Xp - 0.5).cast(ti.i32)
        fx = Xp - base.cast(ti.f32)
        w = [0.5 * (1.5 - fx) ** 2, 0.75 - (fx - 1.0) ** 2, 0.5 * (fx - 0.5) ** 2]
        U, sig, V = ti.svd(F[p])
        e0 = ti.log(ti.max(sig[0, 0], 0.05))
        e1 = ti.log(ti.max(sig[1, 1], 0.05))
        e2 = ti.log(ti.max(sig[2, 2], 0.05))
        tr = e0 + e1 + e2
        Dm = ti.Matrix([[2 * MU * e0 + LAM * tr, 0.0, 0.0],
                        [0.0, 2 * MU * e1 + LAM * tr, 0.0],
                        [0.0, 0.0, 2 * MU * e2 + LAM * tr]])
        tau = U @ Dm @ U.transpose()
        affine = (-dt * P_VOL * 4.0 * INV_DX * INV_DX) * tau + P_MASS * C[p]
        for i, j, k in ti.static(ti.ndrange(3, 3, 3)):
            off = ti.Vector([i, j, k])
            dpos = (off.cast(ti.f32) - fx) * DX
            wt = w[i][0] * w[j][1] * w[k][2]
            grid_v[base + off] += wt * (P_MASS * v[p] + affine @ dpos)
            grid_m[base + off] += wt * P_MASS


@ti.kernel
def grid_op(dt: ti.f32):
    for I in ti.grouped(grid_m):
        if grid_m[I] > 0:
            vel = grid_v[I] / grid_m[I]
            vel[1] += dt * (-G)
            vel *= 0.9995
            pos = ti.Vector([ORG[0] + I[0] * DX, ORG[1] + I[1] * DX, ORG[2] + I[2] * DX])
            if is_solid(pos):
                vel = ti.Vector([0.0, 0.0, 0.0])      # froyo sticks to the paper
            if I[0] < 3 or I[0] > NX - 4 or I[1] < 3 or I[1] > NY - 4 or I[2] < 3 or I[2] > NZ - 4:
                vel = ti.Vector([0.0, 0.0, 0.0])
            grid_v[I] = vel


@ti.kernel
def g2p(n: ti.i32, dt: ti.f32):
    for p in range(n):
        Xp = (x[p] - ti.Vector([ORG[0], ORG[1], ORG[2]])) * INV_DX
        base = (Xp - 0.5).cast(ti.i32)
        fx = Xp - base.cast(ti.f32)
        w = [0.5 * (1.5 - fx) ** 2, 0.75 - (fx - 1.0) ** 2, 0.5 * (fx - 0.5) ** 2]
        nv = ti.Vector([0.0, 0.0, 0.0])
        nC = ti.Matrix.zero(ti.f32, 3, 3)
        for i, j, k in ti.static(ti.ndrange(3, 3, 3)):
            off = ti.Vector([i, j, k])
            dpos = off.cast(ti.f32) - fx
            gv = grid_v[base + off]
            wt = w[i][0] * w[j][1] * w[k][2]
            nv += wt * gv
            nC += 4.0 * INV_DX * wt * gv.outer_product(dpos)
        v[p] = nv
        C[p] = nC
        x[p] += dt * nv
        Fn = (ti.Matrix.identity(ti.f32, 3) + dt * nC) @ F[p]
        F[p] = project(Fn)


@ti.kernel
def emit(base: ti.i32, nx: ti.f32, ny: ti.f32, nz: ti.f32, vx: ti.f32, vy: ti.f32, vz: ti.f32, tnow: ti.f32):
    for i in range(K):
        p = base + i
        j = (ti.random() - 0.5) * 0.25 * SP
        k = (ti.random() - 0.5) * 0.25 * SP
        x[p] = ti.Vector([nx + slab_off[i][0] + j, ny, nz + slab_off[i][1] + k])
        v[p] = ti.Vector([vx, vy, vz])
        C[p] = ti.Matrix.zero(ti.f32, 3, 3)
        F[p] = ti.Matrix.identity(ti.f32, 3)
        tag[p] = slab_tag[i]
        born[p] = tnow


@ti.kernel
def probe(n: ti.i32, cx: ti.f32, cz: ti.f32, rr: ti.f32, ymax: ti.f32, vthr: ti.f32, tnow: ti.f32):
    top[None] = ZB
    for p in range(n):
        if tnow - born[p] > 0.28 and v[p].norm() < vthr and x[p][1] < ymax:
            dx = x[p][0] - cx
            dz = x[p][2] - cz
            if dx * dx + dz * dz < rr * rr:
                ti.atomic_max(top[None], x[p][1] + 0.5 * SP)


# ---------------------------------------------------------------- the hand
THA = 2 * math.pi * 0.9
THB = THA + 2 * math.pi * N_OUT
RING = {"c": None}


def ring_radius(ny):
    """The hand rides a ring that keeps the rope off the wall: the cup is a cone, so the ring widens as the pile rises."""
    y_dep = min(ny - GAP + 0.55 * A_NOZ, H_RIM)
    return max(0.014, min(R0, r_in(y_dep) - 0.92 * A_NOZ))


def rho_of(theta, ny):
    if theta < THA:
        return 0.018 + (ring_radius(ny) - 0.018) * (theta / THA)
    if theta < THB:
        RING["c"] = ring_radius(ny)
        return RING["c"]
    if RING["c"] is None:
        RING["c"] = ring_radius(ny)
    return max(RHO_END, RING["c"] - D_RHO * (theta - THB) / (2 * math.pi))


def valve(t, t_end):
    up = min(1.0, t / 0.18)
    dn = 1.0 if t_end is None else max(0.0, 1.0 - (t - t_end) / 0.25)
    s = up * dn
    return VE * s * s * (3 - 2 * s)


def run():
    t0 = time.time()
    n = 0
    t = 0.0
    theta = 0.0
    ny = ZB + GAP + 0.002
    acc = 0.0
    hx, hz = 0.018, 0.0
    last_hand = np.array([hx, hz])
    t_end = None                  # when the valve closes
    t_flick = None
    flick_dir = np.zeros(2)
    flick_off = np.zeros(2)
    frames, hand_log = [], []
    next_frame = 0.0
    step = 0
    ny_target = ny
    surf = ZB
    done_at = None
    while True:
        # ---- hand
        vext = valve(t, t_end)
        if t_end is None:
            rho = rho_of(theta, ny)
            if theta > THB and rho <= RHO_END + 1e-6:
                if t_flick is None:
                    t_flick = t
                    t_end = t + 0.05
                    ang = theta
                    flick_dir = np.array([-math.sin(ang), math.cos(ang)])   # carry on along the circle's tangent
            omega = min(OMEGA_MAX, RATIO * max(vext, 0.02) / max(rho, 0.012))
            theta += omega * DT
            hx, hz = rho * math.cos(theta), rho * math.sin(theta)
        else:
            tf = t - t_flick
            sp = FLICK_V * min(1.0, tf / 0.15)
            flick_off += flick_dir * sp * DT
            hx, hz = rho * math.cos(theta) + flick_off[0], rho * math.sin(theta) + flick_off[1]
        hand = np.array([hx, hz])
        hv = (hand - last_hand) / DT
        last_hand = hand

        # ---- nozzle height follows the pile
        if step % 20 == 0 and n > 0:
            probe(n, hx, hz, 0.012, ny - 0.006, 0.06, t)
            surf = top[None]
            ny_target = surf + GAP
        if t_flick is not None:
            ny_target = max(ny_target, ny) + 0.02 + 0.5 * (t - t_flick)
        rate = LIFT_RATE if t_flick is None else 0.30
        dy = ny_target - ny
        ny += max(-0.05 * DT, min(rate * DT, dy)) if t_flick is None else max(0.0, min(rate * DT, dy))

        # ---- extrude: a slab each time the paste has travelled one particle spacing
        acc += vext * DT
        while acc >= SP and n + K <= NP:
            acc -= SP
            emit(n, hx, ny - 0.5 * SP - acc, hz, hv[0], -vext, hv[1], t)
            n += K

        # ---- MPM step
        clear_grid()
        p2g(n, DT)
        grid_op(DT)
        g2p(n, DT)
        t += DT
        step += 1

        if t >= next_frame:
            frames.append(x.to_numpy()[:n].astype(np.float16))
            hand_log.append((float(hx), float(ny), float(hz), float(vext)))
            next_frame += 1.0 / FPS_OUT
            if len(frames) % 12 == 0:
                print(f"t={t:5.2f}s  frame {len(frames):4d}  n={n:6d}  hand rho={math.hypot(hx, hz)*1000:5.1f}mm "
                      f"ny={ny*1000:5.1f}mm surf={surf*1000:5.1f}mm  {time.time()-t0:6.0f}s elapsed", flush=True)
        if t_end is not None and done_at is None and vext <= 0.0 and t - t_end > 0.25:
            done_at = t
        if done_at is not None and t - done_at > SETTLE_T:
            break
        if t > MAX_TIME or n + K > NP:
            print("stopped early", t, n, NP)
            break

    nframes = len(frames)
    n_max = n
    arr = np.zeros((nframes, n_max, 3), np.float16)
    for i, f in enumerate(frames):
        arr[i, :len(f)] = f
        if len(f) < n_max:
            arr[i, len(f):] = np.nan
    np.save(os.path.join(OUT, "frames.npy"), arr)
    np.save(os.path.join(OUT, "tag.npy"), tag.to_numpy()[:n_max].astype(np.uint8))
    emit_f = []
    # first frame at which each particle exists
    cnt = [len(f) for f in frames]
    meta = {
        "fps": FPS_OUT, "frames": nframes, "particles": int(n_max), "spacing": SP, "dx": DX, "slab": K,
        "counts": cnt, "hand": hand_log, "valve_close_frame": int((t_end or 0) * FPS_OUT) if t_end else None,
        "params": {k: globals()[k] for k in ["RHO", "TAU_Y", "MU", "LAM", "ETA", "VE", "GAP", "RATIO", "R0", "N_OUT",
                                              "D_RHO", "RHO_END", "FLICK_V", "A_NOZ"]},
        "taichi_dt": DT, "wall_seconds": time.time() - t0,
    }
    with open(os.path.join(OUT, "meta.json"), "w") as fh:
        json.dump(meta, fh)
    print(f"done: {nframes} frames, {n_max} particles, {time.time()-t0:.0f}s")


if __name__ == "__main__":
    run()
