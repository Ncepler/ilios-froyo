// The real Ilios cup's dimensions (see cup.js and docs/ILIOS-FIELD-NOTES.md). Metres, Y up, origin at the foot.
// Kept free of three.js so the pour simulation can also run headless.

export const CUP = {
  H: 0.0840,        // overall height (top of the rolled rim)
  RT: 0.0480,       // outer radius at the top of the wall, under the bead
  RB: 0.0370,       // outer radius at the bottom of the wall
  T: 0.00055,       // paper thickness
  ZB: 0.0068,       // inside floor (top of the recessed base)
  ZU: 0.0060,       // underside of the base disc
  BEAD: 0.00145,    // rolled rim bead radius
};
export const SLOPE = (CUP.RT - CUP.RB) / (CUP.H - 0.0016 - 0.0015);
export const rOut = y => CUP.RB + (y - 0.0015) * SLOPE;
export const rIn = y => rOut(Math.max(y, 0.0015)) - CUP.T * Math.sqrt(1 + SLOPE * SLOPE);
export const RIM_IN = rIn(CUP.H - 0.0019);
