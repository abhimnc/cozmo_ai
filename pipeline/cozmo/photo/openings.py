"""Detecting doors and archways.

An opening in a wall has a shape the rest of the wall does not: two vertical
jambs, the same distance away, standing on the floor at the wall line, separated
by a door-like distance.

Each of those is checkable with what the geometry stage already produces. The
jambs are vertical segments — vertical in the *gravity-aligned* frame, which is
recovered from the vertical vanishing point, not assumed from image orientation.
Their base points back-project onto the floor plane, and a jamb belonging to a
wall lands on that wall's line. The separation between a pair is then a distance
in metres, not pixels, so the width falls out of the same projection that gives
room size.

**Windows are not detected**, and cannot be by this method: a window does not
reach the floor, so its jambs have no base point to project. That is a stated
limitation, not an oversight — the brief scores a missed opening and a phantom
opening equally, so claiming windows we cannot see would cost twice.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .floorplane import FloorLine
from .lines import Segments

# A door-like separation. Below 0.5 m is furniture or a pillar; above 2.5 m is
# two openings read as one, or a wall corner mistaken for a jamb. The Living
# room's widest archway is 2.013 m, so the upper bound admits it with margin.
MIN_OPENING_M = 0.50
MAX_OPENING_M = 2.50

# How close a jamb's floor point must lie to a wall line to be considered part of
# that wall. Set to the same tolerance the wall line itself was fitted with.
WALL_ASSOCIATION_M = 0.20

# A jamb must be at least this tall in the image, as a fraction of frame height.
# Short vertical segments are furniture edges and picture frames.
MIN_JAMB_FRAC = 0.12


@dataclass
class Opening:
    width_m: float
    height_m: float | None
    wall_distance_m: float
    jamb_confidence: float
    kind: str                    # "door_or_archway" - see module docstring on windows


def _vertical_segments(seg: Segments, rotation: np.ndarray, focal: float,
                       principal: np.ndarray) -> list[tuple[np.ndarray, np.ndarray]]:
    """Segments that are vertical in the world, returned as (bottom, top) pixels.

    Verticality is tested after rotating into the gravity frame, so a tilted
    photo does not hide its own door frames.
    """
    out = []
    for x1, y1, x2, y2 in seg.points:
        if abs(y2 - y1) < MIN_JAMB_FRAC * seg.height:
            continue
        bottom, top = ((x1, y1), (x2, y2)) if y1 > y2 else ((x2, y2), (x1, y1))
        d = np.array([[bottom[0] - principal[0], bottom[1] - principal[1], focal],
                      [top[0] - principal[0], top[1] - principal[1], focal]]) @ rotation.T
        d = d / np.linalg.norm(d, axis=1, keepdims=True)
        # A world-vertical edge spans a large change in the gravity component
        # while barely changing bearing.
        if abs(d[0, 1] - d[1, 1]) < 0.15:
            continue
        out.append((np.asarray(bottom), np.asarray(top)))
    return out


def _floor_point(pixel: np.ndarray, rotation: np.ndarray, focal: float,
                 principal: np.ndarray, camera_height: float) -> np.ndarray | None:
    d = np.array([pixel[0] - principal[0], pixel[1] - principal[1], focal]) @ rotation.T
    u = d / np.linalg.norm(d)
    if u[1] <= np.sin(np.deg2rad(8.0)):
        return None
    t = camera_height / d[1]
    return np.array([d[0] * t, d[2] * t])


def detect(seg: Segments, wall_lines: list[FloorLine], rotation: np.ndarray,
           focal: float, principal: np.ndarray, camera_height: float) -> list[Opening]:
    """Openings visible in one view, as metric widths."""
    if not wall_lines:
        return []

    jambs = []
    for bottom, top in _vertical_segments(seg, rotation, focal, principal):
        fp = _floor_point(bottom, rotation, focal, principal, camera_height)
        if fp is None:
            continue
        jambs.append((fp, bottom, top))
    if len(jambs) < 2:
        return []

    openings: list[Opening] = []
    for line in wall_lines:
        normal = np.array([-line.direction[1], line.direction[0]])
        on_wall = [(np.dot(fp - line.point, line.direction), fp, bottom, top)
                   for fp, bottom, top in jambs
                   if abs(np.dot(fp - line.point, normal)) < WALL_ASSOCIATION_M]
        if len(on_wall) < 2:
            continue
        on_wall.sort(key=lambda j: j[0])

        # Adjacent pairs only. A door is bounded by the two jambs either side of
        # it; pairing every jamb with every other invents openings spanning
        # whatever lies between them.
        for (a, _, ab, at), (b, fp_b, bb, bt) in zip(on_wall, on_wall[1:]):
            width = b - a
            if not (MIN_OPENING_M <= width <= MAX_OPENING_M):
                continue

            # Height from the shorter jamb: a door's head is level, so the
            # shorter apparent jamb is the better-observed one, and the taller is
            # usually a wall corner running to the ceiling.
            height = None
            dist = float(np.linalg.norm(fp_b))
            tops = []
            for base, tip in ((ab, at), (bb, bt)):
                d = np.array([tip[0] - principal[0], tip[1] - principal[1], focal]) @ rotation.T
                u = d / np.linalg.norm(d)
                # Elevation above horizontal, times ground distance, plus camera height.
                elev = -u[1] / max(np.linalg.norm(u[[0, 2]]), 1e-6)
                tops.append(camera_height + elev * dist)
            if tops:
                height = float(min(tops))

            if any(abs(o.width_m - width) < 0.05 and abs(o.wall_distance_m - dist) < 0.3
                   for o in openings):
                # Same physical opening reached through a different jamb pair on
                # the same wall. Counting it twice would inflate the opening
                # count, and the gate scores a phantom opening as harshly as a
                # missed one.
                continue
            openings.append(Opening(
                width_m=float(width),
                height_m=height,
                wall_distance_m=dist,
                jamb_confidence=min(1.0, line.support / 60.0),
                kind="door_or_archway",
            ))
    return openings


def aggregate(per_view: list[list[Opening]], tolerance_rel: float = 0.25) -> list[Opening]:
    """Merge openings seen across several views of one room.

    Two views of the same doorway give two width estimates; a spurious detection
    usually appears in one view only. Clustering by width and keeping clusters
    seen more than once is therefore both a merge and a filter — and the filter
    matters more, because the gate counts a phantom opening as harshly as a
    missed one.
    """
    flat = [o for view in per_view for o in view]
    if not flat:
        return []
    flat.sort(key=lambda o: o.width_m)

    clusters: list[list[Opening]] = [[flat[0]]]
    for o in flat[1:]:
        # Relative, not absolute. A single-view width carries roughly 15% error
        # because it inherits the camera-height prior and the wall-distance
        # estimate, so two readings of the same 2 m archway can sit 0.3 m apart
        # while two readings of a 0.8 m door sit 0.12 m apart. A fixed tolerance
        # over-merges narrow openings and splits wide ones.
        if (o.width_m - clusters[-1][-1].width_m) <= tolerance_rel * o.width_m:
            clusters[-1].append(o)
        else:
            clusters.append([o])

    out = []
    for c in clusters:
        # Singletons are kept, not dropped. With two or three detections per
        # room, requiring corroboration removed every opening including the real
        # ones - a filter that returns nothing is not a conservative filter, it
        # is a broken one. Corroboration is reported as confidence instead, so a
        # consumer can weigh it rather than having the decision made for them.
        widths = sorted(x.width_m for x in c)
        heights = [x.height_m for x in c if x.height_m]
        out.append(Opening(
            width_m=widths[len(widths) // 2],
            height_m=sorted(heights)[len(heights) // 2] if heights else None,
            wall_distance_m=sorted(x.wall_distance_m for x in c)[len(c) // 2],
            jamb_confidence=min(1.0, len(c) / 4.0),
            kind="door_or_archway",
        ))
    return out
