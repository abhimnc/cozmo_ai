"""Cross-checking EXIF focal length against image geometry.

The photo tier's scale rests on focal length. EXIF supplies one, image geometry
supplies another, and the two disagreeing is information — not noise to be
averaged away. This module reports both and their difference, which is the
input to the interval the pipeline is allowed to quote.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import lines, vanishing
from .exif import PhotoCamera, read_camera


# Two pairwise focal estimates from the same image may differ by this much before
# the Manhattan assumption is judged to have failed. Set from the gate it feeds:
# the photo tier allows +/-8% on wall lengths, and focal error passes into length
# error roughly one-for-one, so a triplet that cannot agree to well inside that
# has nothing to contribute.
# Fraction of total line length a Manhattan frame must explain to be believed.
# Indoor scenes carry plenty of non-axis structure - furniture, patterns, clutter -
# so this is not near 1. It is set to reject frames fitted to noise, not to demand
# a bare room.
MIN_INLIER_FRACTION = 0.45


@dataclass
class FocalEstimate:
    path: str
    camera: PhotoCamera
    n_segments: int
    n_vanishing_points: int
    inlier_fraction: float | None
    focal_exif_px: float | None
    focal_geometry_px: float | None
    pairs_used: int
    consistency: float | None
    rejected: str | None

    @property
    def relative_error(self) -> float | None:
        if not self.focal_exif_px or not self.focal_geometry_px:
            return None
        return (self.focal_geometry_px - self.focal_exif_px) / self.focal_exif_px


def estimate(path: str, seed: int = 0) -> FocalEstimate:
    camera = read_camera(path)
    seg = lines.detect(path)

    # Work in the downscaled frame the segments live in, then convert back.
    principal = (seg.width / 2.0, seg.height / 2.0)
    frame = vanishing.find_manhattan_frame(seg, principal,
                                           rng=np.random.default_rng(seed))

    # Support gate.
    #
    # Orthogonality is now enforced inside the search, so what remains to judge is
    # whether the frame actually explains the picture. A Manhattan frame can always
    # be fitted to something; the question is how much of the image's line
    # structure it accounts for. Below the threshold the frame is a shape found in
    # noise, and its focal length is fabricated.
    focal_geometry = None
    consistency = None
    rejected = None

    if frame is None:
        rejected = "no orthogonal frame found"
    else:
        consistency = frame.inlier_fraction
        if frame.inlier_fraction < MIN_INLIER_FRACTION:
            rejected = (f"frame explains only {frame.inlier_fraction * 100:.0f}% of line structure; "
                        "too little to trust")
        else:
            focal_geometry = frame.focal_px / (seg.scale or 1.0)

    return FocalEstimate(
        path=path,
        camera=camera,
        n_segments=len(seg),
        n_vanishing_points=3 if frame else 0,
        inlier_fraction=frame.inlier_fraction if frame else None,
        focal_exif_px=camera.focal_px_horizontal,
        focal_geometry_px=focal_geometry,
        pairs_used=1 if frame else 0,
        consistency=consistency,
        rejected=rejected,
    )
