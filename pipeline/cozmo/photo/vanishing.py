"""Vanishing points, and a focal length that owes nothing to EXIF.

A rectangular room has three mutually orthogonal edge directions. Their
vanishing points constrain the camera: for two orthogonal directions with
vanishing points v1 and v2 measured from the principal point,

    v1 . v2 + f^2 = 0

so f follows from image content alone. That matters here more than usual. The
photo tier's only other source of scale is the EXIF focal length, and EXIF is
ambiguous by about 4% — Apple calls the iPhone 13 wide lens 26 mm while the
horizontal 35 mm convention gives 27. Four percent is half the photo tier's
entire budget. An independent estimate is what turns that from an assumption
into something checkable.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .lines import Segments


@dataclass
class VanishingPoint:
    point: np.ndarray       # homogeneous, 3-vector, in downscaled image coords
    inliers: np.ndarray     # boolean mask over segments
    support: float          # total inlier length in pixels

    @property
    def is_finite(self) -> bool:
        return abs(self.point[2]) > 1e-9

    def as_2d(self) -> np.ndarray | None:
        if not self.is_finite:
            return None
        return self.point[:2] / self.point[2]

    def direction(self) -> np.ndarray:
        """Image direction of the family of lines meeting at this point."""
        d = self.point[:2] if not self.is_finite else self.point[:2] / self.point[2]
        return d / (np.linalg.norm(d) + 1e-12)


def _angles_to(vp: np.ndarray, seg: Segments) -> np.ndarray:
    """Angle, in radians, between each segment and the ray to the vanishing point."""
    mids = seg.midpoints
    dirs = seg.directions
    if abs(vp[2]) > 1e-9:
        to_vp = (vp[:2] / vp[2])[None, :] - mids
    else:
        to_vp = np.repeat(vp[None, :2], len(mids), axis=0)
    norm = np.linalg.norm(to_vp, axis=1, keepdims=True)
    to_vp = to_vp / (norm + 1e-12)
    # Lines are undirected, so fold the angle into [0, pi/2].
    cos = np.abs(np.sum(to_vp * dirs, axis=1))
    return np.arccos(np.clip(cos, 0.0, 1.0))


def find_vanishing_points(
    seg: Segments,
    max_points: int = 3,
    threshold_deg: float = 1.5,
    iterations: int = 2000,
    min_support_frac: float = 0.04,
    rng: np.random.Generator | None = None,
) -> list[VanishingPoint]:
    """Greedy RANSAC: strongest vanishing point first, then repeat on what is left.

    Segments vote by *length*, not by count. A 400-pixel wall/floor junction is
    far better evidence of a room direction than twenty short segments off a
    patterned rug, and counting votes equally lets texture outshout structure.
    """
    if len(seg) < 4:
        return []

    rng = rng or np.random.default_rng(0)
    lines = seg.homogeneous_lines()
    lengths = seg.lengths
    threshold = np.deg2rad(threshold_deg)
    remaining = np.ones(len(seg), dtype=bool)
    found: list[VanishingPoint] = []

    for _ in range(max_points):
        idx = np.flatnonzero(remaining)
        if len(idx) < 4:
            break

        best_support, best_vp, best_inliers = 0.0, None, None
        probs = lengths[idx] / lengths[idx].sum()

        for _ in range(iterations):
            i, j = rng.choice(len(idx), size=2, replace=False, p=probs)
            vp = np.cross(lines[idx[i]], lines[idx[j]])
            if np.linalg.norm(vp) < 1e-9:
                continue
            ang = _angles_to(vp, seg)
            inliers = (ang < threshold) & remaining
            support = float(lengths[inliers].sum())
            if support > best_support:
                best_support, best_vp, best_inliers = support, vp, inliers

        if best_vp is None or best_support < min_support_frac * lengths.sum():
            break

        # Refit to all inliers: the two-line sample fixes the hypothesis, the
        # consensus fixes the estimate. The vanishing point is the least-squares
        # null vector of its supporting lines.
        support_lines = lines[best_inliers]
        _, _, vt = np.linalg.svd(support_lines)
        refined = vt[-1]
        ang = _angles_to(refined, seg)
        inliers = (ang < threshold) & remaining
        if lengths[inliers].sum() < best_support * 0.8:
            refined, inliers = best_vp, best_inliers

        found.append(VanishingPoint(refined, inliers, float(lengths[inliers].sum())))
        remaining &= ~inliers

    return sorted(found, key=lambda v: -v.support)


def classify(vps: list[VanishingPoint], vertical_tolerance_deg: float = 25.0
             ) -> tuple[VanishingPoint | None, list[VanishingPoint]]:
    """Split into the vertical vanishing point and the horizontal ones.

    The vertical direction is the one whose supporting lines run up and down the
    image. Gravity alignment is not available at this tier — that is a LiDAR-tier
    signal — so it is identified from image content like everything else here.
    """
    vertical, horizontal = None, []
    best = -1.0
    tol = np.cos(np.deg2rad(90.0 - vertical_tolerance_deg))
    for vp in vps:
        verticality = abs(vp.direction()[1])
        if verticality > tol and vp.support > best:
            if vertical is not None:
                horizontal.append(vertical)
            vertical, best = vp, vp.support
        else:
            horizontal.append(vp)
    return vertical, sorted(horizontal, key=lambda v: -v.support)


def focal_from_orthogonal(v1: VanishingPoint, v2: VanishingPoint,
                          principal: tuple[float, float]) -> float | None:
    """Focal length in pixels from two orthogonal vanishing points.

    Returns None when the pair carries no focal information: if either point is
    at infinity, or if the constraint yields a negative f^2, the geometry is
    degenerate and a number would be invented rather than measured.
    """
    p1, p2 = v1.as_2d(), v2.as_2d()
    if p1 is None or p2 is None:
        return None
    c = np.asarray(principal, dtype=float)
    dot = float(np.dot(p1 - c, p2 - c))
    if dot >= 0:
        return None
    return float(np.sqrt(-dot))


# A vanishing point's image direction is "vertical" when |dy| is large. The
# thresholds bracket a phone held within about 30 degrees of upright.
COS_60 = 0.866   # one axis must be at least this vertical
COS_30 = 0.500   # the other two must be no more vertical than this

# Every axis of a Manhattan frame must be supported by this fraction of the
# image's total line length. Without a floor per axis, a frame can score well on
# two real directions while its third sits in empty space.
MIN_AXIS_SUPPORT = 0.03


@dataclass
class ManhattanFrame:
    """Three mutually orthogonal vanishing points and the focal length they imply."""

    focal_px: float
    vps: list[np.ndarray]        # three homogeneous vanishing points
    support: float               # total inlier length across all three
    inlier_fraction: float


def _verticality(vp: np.ndarray, principal: np.ndarray) -> float:
    """How vertical the line family meeting at this vanishing point is, in [0, 1].

    Measured from the *principal point*, not the image origin: a vanishing point
    at (0, -5000) is far above the frame and its lines run vertically, but its
    offset from the top-left corner says nothing useful.
    """
    if abs(vp[2]) > 1e-9:
        u = vp[:2] / vp[2] - principal
    else:
        u = vp[:2]
    n = float(np.linalg.norm(u))
    return 0.0 if n < 1e-9 else abs(float(u[1])) / n


def _project(direction: np.ndarray, focal: float, principal: np.ndarray) -> np.ndarray:
    """Vanishing point of a 3D direction, homogeneous so infinity needs no special case."""
    dx, dy, dz = direction
    return np.array([focal * dx + principal[0] * dz,
                     focal * dy + principal[1] * dz,
                     dz])


def find_manhattan_frame(
    seg: Segments,
    principal: tuple[float, float],
    threshold_deg: float = 2.0,
    candidate_samples: int = 4000,
    top_candidates: int = 24,
    rng: np.random.Generator | None = None,
) -> ManhattanFrame | None:
    """Search for three orthogonal room axes and the focal length consistent with them.

    Greedily taking the three strongest line families and then testing whether
    they happen to be orthogonal does not work indoors: the strongest families
    are often a rug, a sofa edge and a curtain fold, and they answer to no
    Manhattan frame. Orthogonality has to constrain the search, not audit it
    afterwards.

    So: harvest many candidate vanishing points, keep the best-supported few,
    then test *pairs*. Each pair fixes a focal length through the orthogonality
    constraint, and the focal length fixes the third axis by cross product. The
    whole frame is then scored on the segments it explains. A frame that is not
    Manhattan cannot score well, because its third axis lands where no lines are.
    """
    if len(seg) < 6:
        return None

    rng = rng or np.random.default_rng(0)
    lines = seg.homogeneous_lines()
    lengths = seg.lengths
    total_length = float(lengths.sum())
    threshold = np.deg2rad(threshold_deg)
    c = np.asarray(principal, dtype=float)

    # 1. Harvest candidate vanishing points from random pairs of segments,
    #    sampling proportional to length so structure outvotes texture.
    probs = lengths / total_length
    idx = rng.choice(len(seg), size=(candidate_samples, 2), replace=True, p=probs)
    idx = idx[idx[:, 0] != idx[:, 1]]
    cands = np.cross(lines[idx[:, 0]], lines[idx[:, 1]])
    norms = np.linalg.norm(cands, axis=1)
    cands = cands[norms > 1e-9]
    if len(cands) < 2:
        return None

    # 2. Keep the best-supported, suppressing near-duplicates so the shortlist
    #    spans distinct directions rather than one direction found many times.
    scored = []
    for vp in cands:
        support = float(lengths[_angles_to(vp, seg) < threshold].sum())
        scored.append((support, vp))
    scored.sort(key=lambda t: -t[0])

    shortlist: list[np.ndarray] = []
    for support, vp in scored:
        if support < 0.02 * total_length:
            break
        d = vp[:2] / (np.linalg.norm(vp[:2]) + 1e-12)
        if all(abs(float(np.dot(d, s[:2] / (np.linalg.norm(s[:2]) + 1e-12)))) < 0.995
               for s in shortlist):
            shortlist.append(vp)
        if len(shortlist) >= top_candidates:
            break
    if len(shortlist) < 2:
        return None

    # 3. Every pair proposes a focal length; the focal length completes the frame.
    best: ManhattanFrame | None = None
    for i in range(len(shortlist)):
        for j in range(i + 1, len(shortlist)):
            v1, v2 = shortlist[i], shortlist[j]
            if abs(v1[2]) < 1e-9 or abs(v2[2]) < 1e-9:
                continue
            u1, u2 = v1[:2] / v1[2] - c, v2[:2] / v2[2] - c
            dot = float(np.dot(u1, u2))
            if dot >= 0:
                continue
            f = float(np.sqrt(-dot))
            # Physical bound on a handheld phone camera, not a fit to our data.
            # A phone's focal length in pixels sits near the image width: the
            # iPhone 13 wide lens is about 0.75w. Anything past 2.5w is a
            # telephoto no phone has, and below 0.4w a fisheye. Frames outside
            # this are numerically valid and physically impossible, and without
            # the bound a degenerate near-parallel pair can propose an arbitrarily
            # large focal length that happens to score well.
            if not (0.4 * seg.width < f < 2.5 * seg.width):
                continue

            d1 = np.array([u1[0], u1[1], f]); d1 /= np.linalg.norm(d1)
            d2 = np.array([u2[0], u2[1], f]); d2 /= np.linalg.norm(d2)
            d3 = np.cross(d1, d2)
            v3 = _project(d3, f, c)

            vps = [v1, v2, v3]

            # Upright prior: reject frames that no handheld photo could produce.
            #
            # People hold a phone within roughly 30 degrees of upright, so one
            # room axis must project near-vertically in the image and the other
            # two near-horizontally. Without this the search happily accepts a
            # numerically valid frame built from two wall directions that are not
            # perpendicular, whose focal length then comes out around twice the
            # truth - the second cluster visible in the first evaluation runs.
            #
            # This is a constraint on how the picture was taken, not a fit to the
            # answer: it says nothing about focal length and would apply equally
            # to any handheld capture.
            verticality = sorted(_verticality(vp, c) for vp in vps)
            if verticality[-1] < COS_60 or verticality[1] > COS_30:
                continue

            # Score each axis separately, and require all three to be present.
            #
            # Scoring the union of inliers rewards large focal lengths: as f
            # grows every vanishing point recedes, the line families become
            # near-parallel, and the angular test accepts a wider and wider swath
            # of the image. A frame twice the true focal length can therefore
            # out-score the correct one, which is exactly the second cluster the
            # evaluation runs kept producing.
            #
            # Demanding real support on all three axes removes the reward. A real
            # room shows three directions; an inflated frame has a third axis
            # sitting where no lines are, and cannot buy its way out with the
            # other two.
            per_vp = []
            assigned = np.zeros(len(seg), dtype=bool)
            for vp in vps:
                mask = _angles_to(vp, seg) < threshold
                per_vp.append(float(lengths[mask].sum()))
                assigned |= mask
            if min(per_vp) < MIN_AXIS_SUPPORT * total_length:
                continue
            support = float(lengths[assigned].sum())

            if best is None or support > best.support:
                best = ManhattanFrame(focal_px=f, vps=vps, support=support,
                                      inlier_fraction=support / total_length)
    return best
