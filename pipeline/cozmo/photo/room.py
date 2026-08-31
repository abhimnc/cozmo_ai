"""Single-view room geometry from a photo.

The chain is: vertical vanishing point gives the camera's tilt, EXIF gives the
focal length, and a camera-height prior gives scale. With those, any pixel
believed to lie on the floor back-projects to a metric floor point, and the
spread of those points is the room.

Scale comes from how high the phone was held. That is a prior, not a
measurement, and it is the dominant term in this tier's error budget - which is
why it is a stated interval rather than a constant.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import cv2
import numpy as np

from . import floorplane, lines, openings as openings_mod
from .exif import read_camera

# Handheld capture height. Chest height for an adult holding a phone to frame a
# room, wide enough to cover most people and both a raised and lowered arm.
CAMERA_HEIGHT_M = 1.45
CAMERA_HEIGHT_REL = 0.10

# Rays shallower than this carry no usable range. Floor distance goes as
# h / sin(depression), so at 3 degrees a 1.45 m camera puts the floor 28 m away
# and a tenth of a degree of pixel noise moves it by metres. 8 degrees bounds
# recoverable range at 10.4 m, which is generous for a residential room and is
# set from indoor geometry rather than from our own error.
#
# Raised from 3 degrees on 2026-08-31; see fixloop/DECLARATION.md. At 3 degrees
# bed_room_1 estimated 28.15 m against the 27.7 m cap - pinned at the threshold
# rather than measuring anything.
MIN_DEPRESSION_DEG = 8.0

# A floor-plane line is only believed as a wall base with this much support and
# this much length. Below either, the evidence cannot separate a wall from a sofa
# and the older lowest-edge heuristic is used instead.
MIN_LINE_SUPPORT = 25
MIN_WALL_RUN_M = 1.2


@dataclass
class RoomView:
    """What one photo says about the room it was taken in."""

    path: str
    ok: bool
    reason: str = ""
    focal_px: float = 0.0
    tilt_deg: float = 0.0
    floor_points: np.ndarray | None = None      # (N, 2), metres, camera-yaw frame
    depth_far_m: float = 0.0                    # furthest floor point ahead
    width_span_m: float = 0.0                   # lateral spread of floor points
    ceiling_height_m: float | None = None
    openings: list = None


def _vertical_vanishing_point(seg: lines.Segments) -> np.ndarray | None:
    """The point where the room's vertical edges meet.

    Verticals are the one direction indoors that is never ambiguous: door
    jambs, wall corners and furniture edges all share gravity. Selecting on
    image orientation first, before any fitting, keeps the horizontal clutter
    that defeated the full Manhattan search out of this estimate entirely.
    """
    if len(seg) < 3:
        return None
    dirs = seg.directions
    steep = np.abs(dirs[:, 1]) > np.cos(np.deg2rad(20.0))
    if steep.sum() < 3:
        return None
    lines_h = seg.homogeneous_lines()[steep]
    lengths = seg.lengths[steep]
    # Weighted least squares: the vanishing point is the null vector of the
    # lines through it, weighted so long edges dominate short ones.
    weighted = lines_h * lengths[:, None]
    _, _, vt = np.linalg.svd(weighted)
    vp = vt[-1]
    return vp if abs(vp[2]) > 1e-12 else None


def _gravity_rotation(vp_vertical: np.ndarray, focal: float,
                      principal: np.ndarray) -> np.ndarray | None:
    """Rotation taking camera coordinates to a frame with +Y along gravity."""
    v = vp_vertical[:2] / vp_vertical[2] - principal
    up = np.array([v[0], v[1], focal], dtype=float)
    up /= np.linalg.norm(up)
    # The vertical vanishing point may be above or below; gravity points down in
    # image terms, so orient it consistently.
    if up[1] < 0:
        up = -up
    down = up
    # Build an orthonormal frame with `down` as +Y.
    fwd = np.array([0.0, 0.0, 1.0])
    right = np.cross(down, fwd)
    n = np.linalg.norm(right)
    if n < 1e-6:
        return None
    right /= n
    fwd = np.cross(right, down)
    return np.vstack([right, down, fwd])


def _floor_boundary(image_path: str, seg: lines.Segments, horizon_y: float) -> np.ndarray:
    """Lowest strong edge per column: the wall/floor junction, where visible.

    In a furnished room it is often the base of a bed or a cupboard instead, and
    that biases every distance short. The bias is real, measurable against the
    tape ground truth, and reported rather than hidden - see the benchmark
    report's photo-tier row.
    """
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    img = cv2.resize(img, (seg.width, seg.height), interpolation=cv2.INTER_AREA)
    edges = cv2.Canny(cv2.GaussianBlur(img, (5, 5), 0), 40, 120)

    pts = []
    start = max(int(horizon_y) + 1, 0)
    for x in range(0, seg.width, 4):
        col = edges[start:, x]
        hits = np.flatnonzero(col)
        if len(hits):
            pts.append((x, start + hits[-1]))
    return np.asarray(pts, dtype=float)


def analyse(image_path: str, focal_35mm: float | None = None) -> RoomView:
    """`focal_35mm` overrides EXIF, for frames that carry none.

    Video frames are decoded from a clip and have no EXIF, so the video tier
    supplies the device's focal length from the manifest instead. That is a
    device-matrix fact rather than a per-capture calibration, and it is recorded
    in the plan's `scale_source`.
    """
    camera = read_camera(image_path)
    if focal_35mm is not None:
        camera = replace(camera, focal_35mm=focal_35mm)
    focal_full = camera.focal_px_horizontal
    if not focal_full:
        return RoomView(image_path, False, "no EXIF focal length; this tier has no other scale source")

    seg = lines.detect(image_path)
    if len(seg) < 6:
        return RoomView(image_path, False, f"only {len(seg)} line segments; too little structure")

    focal = focal_full * seg.scale
    principal = np.array([seg.width / 2.0, seg.height / 2.0])

    vp = _vertical_vanishing_point(seg)
    if vp is None:
        return RoomView(image_path, False, "no vertical vanishing point")
    R = _gravity_rotation(vp, focal, principal)
    if R is None:
        return RoomView(image_path, False, "degenerate gravity frame")

    # Tilt of the optical axis below horizontal.
    axis_world = R @ np.array([0.0, 0.0, 1.0])
    tilt = float(np.degrees(np.arcsin(np.clip(axis_world[1], -1, 1))))
    if abs(tilt) > 45.0:
        return RoomView(image_path, False, f"camera tilted {tilt:.0f} deg; floor geometry unreliable")

    # Horizon: where rays are horizontal in the gravity frame.
    ys = np.arange(seg.height, dtype=float)
    rays = np.stack([np.full_like(ys, 0.0), ys - principal[1], np.full_like(ys, focal)], axis=1)
    world = rays @ R.T
    below = np.flatnonzero(world[:, 1] > 0)
    horizon_y = float(below[0]) if len(below) else seg.height * 0.5

    # Wall bases as straight runs on the floor plane. Falls back to the
    # lowest-edge heuristic when no run is long enough to be a wall - a very
    # cluttered or very small room may genuinely show none.
    candidates = floorplane.candidate_points(image_path, seg.width, seg.height, horizon_y)
    floor_pts = floorplane.project_to_floor(candidates, R, focal, principal,
                                            CAMERA_HEIGHT_M, MIN_DEPRESSION_DEG)
    wall_lines = floorplane.find_floor_lines(floor_pts)
    # Use the floor-plane method only where its preconditions actually hold.
    #
    # It needs enough floor points to tell a straight wall run from scatter. A
    # 12 MP still supplies them; a 1920x1440 video frame often does not, and
    # measured on the benchmark the method helps the photo tier (33.3% -> 26.2%
    # median error) and hurts the video tier (27.2% -> 39.0%) for exactly that
    # reason. Choosing on available support rather than on tier keeps one code
    # path and lets each capture use whichever method its evidence can carry.
    strong = [l for l in wall_lines if l.support >= MIN_LINE_SUPPORT
              and l.length_m >= MIN_WALL_RUN_M]
    if strong:
        # Take the **longest** run, not the most distant one.
        #
        # Choosing the most distant line assumed the far wall is the furthest
        # thing visible. In a room with an open doorway it is not: the floor
        # continues through the opening and the furthest line lies in the next
        # room. Measured across eight rooms, that rule produced areas correlating
        # -0.11 with actual room size - it was not measuring rooms at all, and it
        # compressed an eightfold true spread into two and a half.
        #
        # Length is the better discriminant because it is a property of walls
        # rather than of viewpoint. A wall base is metres long; a fragment glimpsed
        # through a doorway is short, being clipped by the door frame. Same data,
        # same fitting, correlation +0.42.
        chosen = max(strong, key=lambda l: l.length_m)
        lateral = np.sort(chosen.inliers[:, 0])
        depth = float(chosen.distance_m)
        span = float(lateral[int(0.95 * len(lateral))] - lateral[int(0.05 * len(lateral))])
        if depth <= 0 or span <= 0:
            # A non-positive extent is not a small room, it is a failed fit. Let
            # it through and it reaches Measurement as a negative length, whose
            # interval cannot contain its own value.
            return RoomView(image_path, False, "degenerate extent from the fitted wall line")
        found = openings_mod.detect(seg, strong, R, focal, principal, CAMERA_HEIGHT_M)
        return RoomView(image_path, True, "", focal_full, tilt, chosen.inliers,
                        depth, span, None, found)

    boundary = _floor_boundary(image_path, seg, horizon_y)
    if len(boundary) < 12:
        return RoomView(image_path, False, "floor boundary not visible in enough of the frame")

    # Back-project boundary pixels onto the floor plane at y = camera height.
    d = np.stack([boundary[:, 0] - principal[0],
                  boundary[:, 1] - principal[1],
                  np.full(len(boundary), focal)], axis=1)
    d = d @ R.T
    valid = d[:, 1] > 1e-6
    d = d[valid]
    if len(d) < 12:
        return RoomView(image_path, False, "no floor-bound rays")

    # Reject rays too close to horizontal. Distance to the floor goes as
    # h / sin(depression), so a ray a degree below the horizon lands 80 m away
    # and a tenth of a degree of pixel noise moves it tens of metres. These rays
    # carry no usable range and, being the furthest, dominate any maximum.
    # The depression test must run on unit rays. `d` here is [x-cx, y-cy, f],
    # whose magnitude is of order the focal length in pixels, so comparing its
    # y component against sin(theta) directly compared a number near 1000 to one
    # near 0.14 and admitted everything. Normalise first.
    unit = d / np.linalg.norm(d, axis=1, keepdims=True)
    d = d[unit[:, 1] > np.sin(np.deg2rad(MIN_DEPRESSION_DEG))]
    if len(d) < 12:
        return RoomView(image_path, False,
                        f"floor boundary lies within {MIN_DEPRESSION_DEG} deg of the horizon; no usable range")

    t = CAMERA_HEIGHT_M / d[:, 1]
    pts = np.stack([d[:, 0] * t, d[:, 2] * t], axis=1)   # (lateral, forward), metres

    # Trim the tail: rays near the horizon diverge, so the furthest few points
    # carry almost no information and dominate a naive maximum.
    # Upper quartile, not the 90th percentile. The far wall should be among the
    # more distant boundary points, so an upper estimate is right - but the
    # extreme tail is where the shallowest, least reliable rays land, and taking
    # the 90th percentile selected for exactly those.
    forward = np.sort(pts[:, 1])
    depth_far = float(forward[int(0.75 * len(forward))])
    # Lateral spread across all floor points is not a room dimension: the visible
    # width of the floor grows with distance, so a spread taken over every point
    # measures the camera's field of view, not the room. Measure it only among
    # points at the far wall, where the floor boundary actually meets a wall.
    far_band = pts[pts[:, 1] > 0.7 * depth_far]
    if len(far_band) < 6:
        far_band = pts
    lateral = np.sort(far_band[:, 0])
    lo = float(lateral[int(0.05 * len(lateral))])
    hi = float(lateral[int(0.95 * len(lateral))])

    # The forward component can be negative: a ray can meet the floor plane
    # behind the camera when the fit is poor, and 'behind' is not a room size.
    if depth_far <= 0 or (hi - lo) <= 0:
        return RoomView(image_path, False, "degenerate extent from the floor boundary")

    return RoomView(image_path, True, "", focal_full, tilt, pts,
                    depth_far, hi - lo, None)
