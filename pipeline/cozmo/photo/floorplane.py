"""Finding wall bases on the floor plane, rather than the lowest edge in a column.

The previous approach took the lowest strong edge in each image column and called
it the wall/floor junction. In a furnished room that is frequently the base of a
bed, a cupboard or a mosquito net, and the error is unbounded: it is the dominant
term in the photo tier's budget and the reason two captures of one room disagree
by up to 2.69 m.

The idea here is that a wall base has a property furniture does not. Back-project
every floor-candidate edge point onto the floor plane and look from above: the
base of a planar wall becomes a **straight line**, several metres long, because
the wall is straight and vertical. A bed base projects to a short segment at the
wrong distance; clutter projects to scatter. Straightness and length in the
bird's-eye view separate them, and neither is available in the image alone.

So: collect candidates, project, fit lines robustly, and keep the ones long
enough to be walls.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class FloorLine:
    """A straight run on the floor plane, in metres, in the camera's yaw frame."""

    point: np.ndarray        # a point on the line, (lateral, forward)
    direction: np.ndarray    # unit direction
    inliers: np.ndarray      # (N, 2) supporting floor points
    length_m: float
    distance_m: float        # perpendicular distance from the camera

    @property
    def support(self) -> int:
        return len(self.inliers)


def candidate_points(image_path: str, width: int, height: int, horizon_y: float,
                     stride: int = 3, per_column: int = 4) -> np.ndarray:
    """Floor-candidate edge pixels: several per column, not only the lowest.

    Keeping more than one per column is the point. The true wall base is often
    *above* a piece of furniture in the same column, so a lowest-only rule can
    never recover it however it is filtered afterwards.
    """
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return np.empty((0, 2))
    img = cv2.resize(img, (width, height), interpolation=cv2.INTER_AREA)
    edges = cv2.Canny(cv2.GaussianBlur(img, (5, 5), 0), 40, 120)

    start = max(int(horizon_y) + 1, 0)
    pts = []
    for x in range(0, width, stride):
        hits = np.flatnonzero(edges[start:, x])
        if not len(hits):
            continue
        for y in hits[::-1][:per_column]:
            pts.append((x, start + y))
    return np.asarray(pts, dtype=float)


def project_to_floor(pixels: np.ndarray, rotation: np.ndarray, focal: float,
                     principal: np.ndarray, camera_height: float,
                     min_depression_deg: float) -> np.ndarray:
    """Back-project image points onto the floor plane. Returns (lateral, forward) metres."""
    if len(pixels) == 0:
        return np.empty((0, 2))
    d = np.stack([pixels[:, 0] - principal[0],
                  pixels[:, 1] - principal[1],
                  np.full(len(pixels), focal)], axis=1) @ rotation.T
    unit = d / np.linalg.norm(d, axis=1, keepdims=True)
    d = d[unit[:, 1] > np.sin(np.deg2rad(min_depression_deg))]
    if len(d) == 0:
        return np.empty((0, 2))
    t = camera_height / d[:, 1]
    return np.stack([d[:, 0] * t, d[:, 2] * t], axis=1)


def find_floor_lines(points: np.ndarray, min_length_m: float = 1.2,
                     tolerance_m: float = 0.08, max_lines: int = 4,
                     rng: np.random.Generator | None = None) -> list[FloorLine]:
    """Greedy RANSAC for straight runs on the floor plane.

    `min_length_m` is what separates a wall from a sofa: a wall base visible in a
    photo runs at least a metre or so, while furniture footprints are shorter and
    do not line up with anything.
    """
    rng = rng or np.random.default_rng(0)
    if len(points) < 8:
        return []

    remaining = np.ones(len(points), dtype=bool)
    found: list[FloorLine] = []

    for _ in range(max_lines):
        idx = np.flatnonzero(remaining)
        if len(idx) < 8:
            break
        best = None
        for _ in range(600):
            i, j = rng.choice(len(idx), size=2, replace=False)
            p, q = points[idx[i]], points[idx[j]]
            v = q - p
            n = np.linalg.norm(v)
            if n < 0.3:                      # too close to define a direction
                continue
            v = v / n
            normal = np.array([-v[1], v[0]])
            dist = np.abs((points - p) @ normal)
            inliers = (dist < tolerance_m) & remaining
            if inliers.sum() < 8:
                continue
            proj = (points[inliers] - p) @ v
            length = float(proj.max() - proj.min())
            if length < min_length_m:
                continue
            if best is None or inliers.sum() > best[0].sum():
                best = (inliers, p, v, length)
        if best is None:
            break
        inliers, p, v, length = best
        normal = np.array([-v[1], v[0]])
        found.append(FloorLine(
            point=p, direction=v, inliers=points[inliers], length_m=length,
            distance_m=float(abs(np.dot(p, normal))),
        ))
        remaining &= ~inliers

    return sorted(found, key=lambda l: -l.support)
