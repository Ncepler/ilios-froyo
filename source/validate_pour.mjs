// Headless checks on the pour the site simulates (site/pour-sim.js), the same code and parameters the page runs.
//
//   node source/validate_pour.mjs [report.json]
//
// Fails (exit 1) if the rope stretches, anything ends up outside the paper, the spout's cap dips into the cup,
// or the pour does not come to rest on its own.

import { writeFileSync } from 'node:fs';
import { simulatePour, nodesAt, POUR } from '../site/pour-sim.js';
import { CUP, rIn, RIM_IN } from '../site/cup-dims.js';

const t0 = performance.now();
const rec = simulatePour();
const ms = performance.now() - t0;
const { count: n, final, rad, frozenT, frames, params: P } = rec;
const pct = (a, q) => { const s = Float64Array.from(a).sort(); return s[Math.min(s.length - 1, Math.floor(q * s.length))]; };

// the rope keeps its length (a yield-stress paste does not neck or thin while it flows)
const stretch = [];
for (let i = 0; i < n - 1; i++) {
  const o = i * 3;
  const d = Math.hypot(final[o + 3] - final[o], final[o + 4] - final[o + 1], final[o + 5] - final[o + 2]);
  stretch.push(Math.abs(d - P.DS) / P.DS);
}

// nothing outside the paper: below the rim every coil sits inside the wall; over the rim the swirl may overhang
// the rolled bead by at most one laid-rope half-width, as it does on a well-poured cup
let outside = 0, worst = -1, belowFloor = 0, top = 0;
for (let i = 0; i < n; i++) {
  const o = i * 3, x = final[o], y = final[o + 1], z = final[o + 2], r = Math.hypot(x, z);
  const lim = y < CUP.H ? rIn(y) - P.FX * rad[i] * 0.9 : RIM_IN + P.FX * rad[i];
  if (r > lim + 1e-4) outside++;
  worst = Math.max(worst, r - lim);
  if (y - P.FY * rad[i] * 0.97 < CUP.ZB) belowFloor++;    // the sim presses a coil 2% flat against the paper
  top = Math.max(top, y + P.FY * rad[i]);
}

// the spout's cap stays out of the cup until the server pulls away
let capIn = 0;
for (const f of frames) if (f.N[1] < P.LIFT_MIN - 1e-4) capIn++;

// comes to rest on its own (not held still by the settle timeout at the end)
const end = frames[frames.length - 1].t;
let forced = 0;
for (let i = 0; i < n; i++) if (frozenT[i] >= rec.releaseT + 1.4 - 1e-6) forced++;

// volume poured, against the 16 oz (473 ml) cup
let vol = 0;
for (let i = 0; i < n; i++) vol += Math.PI * rad[i] * rad[i] * P.DS;

// scrubbing is exact in both directions: a time read after jumping around matches a time read in order
const A = new Float32Array(n * 3), B = new Float32Array(n * 3);
const tq = rec.swirlT + 0.37;
const nq = nodesAt(rec, tq, A); nodesAt(rec, end * 0.9, B); nodesAt(rec, 0.2, B);
let scrub = nodesAt(rec, tq, B) === nq ? 0 : Infinity;
for (let i = 0; i < nq * 3; i++) scrub = Math.max(scrub, Math.abs(A[i] - B[i]));

const report = {
  simulated_in_ms: Math.round(ms),
  nodes: n,
  rope_length_m: +(n * P.DS).toFixed(3),
  duration_s: +end.toFixed(2),
  swirl_starts_s: +rec.swirlT.toFixed(2),
  valve_closes_s: +rec.valveCloseT.toFixed(2),
  tail_breaks_s: +rec.releaseT.toFixed(2),
  link_stretch_p99: +pct(stretch, 0.99).toFixed(4),
  link_stretch_max: +Math.max(...stretch).toFixed(4),
  nodes_outside_paper: outside,
  worst_overhang_mm: +(Math.max(0, worst) * 1000).toFixed(2),
  nodes_below_floor: belowFloor,
  frames_with_cap_in_cup: capIn,
  nodes_frozen_by_timeout: forced,
  peak_above_rim_cm: +((top - CUP.H) * 100).toFixed(2),
  volume_ml: Math.round(vol * 1e6),
  cup: { rim_cm: +(CUP.RT * 200).toFixed(1), base_cm: +(CUP.RB * 200).toFixed(1), height_cm: +(CUP.H * 100).toFixed(1) },
  params: Object.fromEntries(Object.entries(POUR).map(([k, v]) => [k, +(+v).toPrecision(4)])),
  scrub_mismatch_m: scrub,
};

const fails = [];
if (report.link_stretch_p99 > 0.05) fails.push('rope stretches more than 5%');
if (outside) fails.push(`${outside} nodes outside the paper`);
if (belowFloor) fails.push(`${belowFloor} nodes below the cup floor`);
if (capIn) fails.push(`spout cap inside the cup in ${capIn} frames`);
if (forced > n * 0.02) fails.push(`${forced} nodes only stopped at the settle timeout`);
if (report.peak_above_rim_cm < 2 || report.peak_above_rim_cm > 9) fails.push('swirl height off');
if (scrub > 0) fails.push('scrubbing is not exact');
report.pass = fails.length === 0;
report.failures = fails;

const json = JSON.stringify(report, null, 2);
console.log(json);
if (process.argv[2]) writeFileSync(process.argv[2], json + '\n');
process.exit(fails.length ? 1 : 0);
