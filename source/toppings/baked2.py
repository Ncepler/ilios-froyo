"""More baked and warm things: Biscoff, cookie dough, cinnamon rolls, coconut shreds, kataifi."""
import numpy as np  # noqa: F401

from lib import MM, fbm, lin, mix, piece, rot_matrix, sd_box, sd_capsule, sd_cyl, sd_ellipsoid, sd_plane, sd_sphere, smax, smin, smoothstep, vnoise, worley  # noqa: F401

# key -> dict(fn=builder, n=variants, heap=dict(bowl=..., over=..., phi=...) or None)
PIECES = {}
