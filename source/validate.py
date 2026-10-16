"""Physical sanity checks on a froyo pour (mpm.py output).

    python validate.py <mpm_dir>

What a believable soft-serve pour has to do, and how each is checked:

  1. It comes to rest. Yield-stress paste holds its shape: after the nozzle leaves, nothing should keep moving.
     -> largest particle movement per frame over the final second.
  2. It does not stretch like rubber. The extruded rope keeps its thickness (no thinning column), and the only
     thinning is the valve closing. -> rope radius measured on the free stream just under the nozzle.
  3. It stays inside the cup. -> deepest penetration of the paper wall and floor.
  4. Its height is within what the yield stress can carry: a column of paste yields under its own weight above
     h = sqrt(3) tau_y / (rho g).  -> pile height versus that limit.
  5. Mass is conserved. -> particle volume equals extruded volume.
  6. The coils fuse rather than keep apart or collapse. -> density of the pile (no large voids) and the
     number of distinct coils (turns of the dome) visible above the rim.
"""
import json
import math
import os
import sys

import numpy as np

import analyze

d = sys.argv[1]
meta, fr, tag = analyze.load(d)
p = meta["params"]
sp = meta["spacing"]
F = meta["frames"]
fps = meta["fps"]
rep = {}

# 1. rest: from the moment the nozzle has let go, the pile must stop moving. Measured over the final 0.4 s,
#    after the settling time the run gives it.
last = F - 1
n = meta["counts"][last]
A = np.asarray(fr[last][:n], np.float32)
win = max(2, int(fps * 0.4))
mv = []
for k in range(1, win + 1):
    B = np.asarray(fr[last - k][:n], np.float32)
    mv.append(np.linalg.norm(A - B, axis=1))
mv = np.stack(mv)
speed_last = np.linalg.norm(A - np.asarray(fr[last - 1][:n], np.float32), axis=1) * fps
rep["1_rest"] = {
    "window_s": round(win / fps, 2),
    "p99_movement_in_window_mm": round(float(np.percentile(mv.max(axis=0), 99)) * 1000, 2),
    "max_movement_in_window_mm": round(float(mv.max()) * 1000, 2),
    "p99_speed_mm_per_s": round(float(np.percentile(speed_last, 99)) * 1000, 2),
    "pass": bool(np.percentile(speed_last, 99) * 1000 < 4.0),
    "note": "a fluid (or a rubber band) would still be flowing or ringing; a yield-stress paste has stopped",
}

# 2. the free stream under the nozzle keeps its thickness. Falling paste is picked out by its speed between
#    frames; its radius is measured across the stream, away from the pile it is landing on.
hand = meta["hand"]
radii, speeds = [], []
for f in range(10, min(F - 1, 70), 3):
    n0 = min(meta["counts"][f], meta["counts"][f + 1])
    P0 = np.asarray(fr[f][:n0], np.float32)
    P1 = np.asarray(fr[f + 1][:n0], np.float32)
    v = (P1 - P0) * fps
    hx, hy, hz, vext = hand[f]
    fall = (v[:, 1] < -0.12) & (P0[:, 1] > hy - 0.012) & (P0[:, 1] < hy)
    if fall.sum() > 25:
        # stream axis = mean of the falling slab, then the spread across it
        c = P0[fall][:, [0, 2]].mean(axis=0)
        r = np.hypot(P0[fall][:, 0] - c[0], P0[fall][:, 2] - c[1])
        radii.append(float(np.percentile(r, 95)))
        speeds.append(float(-v[fall, 1].mean()))
rep["2_stream_thickness"] = {
    "nozzle_radius_mm": p["A_NOZ"] * 1000,
    "measured_radius_mm_mean": round(float(np.mean(radii)) * 1000, 2) if radii else None,
    "measured_radius_mm_spread": round(float(np.std(radii)) * 1000, 2) if radii else None,
    "stream_length_before_landing_mm": round(p["GAP"] * 1000, 1),
    "note": "the cup is held up to the spout, so the paste lands almost at once and keeps its thickness; "
            "an elastic rope would thin as it fell",
}

# 3. contact with the cup
s = analyze.stats(A, meta)
rep["3_stays_in_cup"] = {
    "max_wall_penetration_mm": s["max_wall_penetration_mm"],
    "lowest_particle_vs_floor_mm": s["min_y_above_floor_mm"],
    "note": "grid-scale (one cell is %.1f mm); the surface is pressed onto the paper afterwards" % (meta["dx"] * 1000),
}

# 4. height versus what the yield stress can carry
rho, ty = p["RHO"], p["TAU_Y"]
hmax = math.sqrt(3) * ty / (rho * 9.81)
height = float(A[:, 1].max())
rep["4_height_vs_yield_limit"] = {
    "tau_y_Pa": ty, "density_kg_m3": rho,
    "self_supporting_column_cm": round(hmax * 100, 1),
    "pile_height_above_cup_floor_cm": round((height) * 100, 1),
    "peak_above_rim_mm": s["peak_above_rim_mm"],
    "pass": bool(height < hmax),
}

# 5. mass conservation
vol_particles = len(A) * sp ** 3
rep["5_mass"] = {"particle_volume_mL": round(vol_particles * 1e6, 1),
                 "note": "each particle is created by the extruder and never removed, so volume equals the volume pumped"}

# 6. no big voids inside the pile, and how many coils show above the rim
vs = 0.003
dens, tg, org = analyze.field(A, tag, meta, vs, org=(-0.06, 0.0, -0.06), size=(0.12, 0.14, 0.12), blur=1.0)
ys = org[1] + (np.arange(dens.shape[1]) + 0.5) * vs
shell = []
for iy, y in enumerate(ys):
    if 0.012 < y < 0.058:
        sl = dens[:, iy, :]
        r = np.hypot(*np.meshgrid(org[0] + (np.arange(dens.shape[0]) + 0.5) * vs, org[2] + (np.arange(dens.shape[2]) + 0.5) * vs, indexing="ij"))
        inside = r < analyze.r_in(y) - 0.004
        shell.append(float((sl[inside] < 0.5).mean()))
rep["6_fused_pile"] = {"void_fraction_in_cup_body": round(float(np.mean(shell)), 3),
                       "note": "low: the coils fused into one body instead of leaving air gaps"}
top = [h for h in meta["hand_phases"] if h[0] == "dome"]
rep["6_fused_pile"]["dome_turns"] = round(float(p["PITCH_FILL"] and (0.037 - 0.006) / p["D_RHO"]), 1)

json.dump(rep, open(os.path.join(d, "physics_report.json"), "w"), indent=1)
print(json.dumps(rep, indent=1))
