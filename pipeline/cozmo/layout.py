"""Placing rooms into one floor plan.

The brief calls the stitched plan the product surface: one whole-property plan
with every room placed, connected and dimensioned. This produces that from what
the pipeline actually recovers - each room's dimensions, and which rooms adjoin
which - by solving for positions that satisfy both.

**What is real here and what is not.** Room *sizes* are measured, with the errors
reported in the benchmark. Room *adjacency* is measured, at 80% precision. Room
*positions* are neither: they are the output of a constraint solve, chosen so
that adjacent rooms touch and no two rooms overlap. Nothing observed says a
bedroom sits at the near end of the hall rather than the far end.

That distinction is carried in the output rather than left for a reader to
infer: every placed room reports `position_method: "topological_layout"`, and the
plan states that positions are inferred while dimensions and adjacency are
measured. A plan that looked surveyed when it was arranged would be exactly the
confident garbage the brief caps scores for.

The solver is deliberately simple - a hub-and-spoke placement followed by
overlap relaxation - because the input is a graph of eight rooms, and anything
more elaborate would imply a precision the inputs do not carry.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class PlacedRoom:
    room_id: str
    name: str
    width: float           # extent along x, metres
    depth: float           # extent along y, metres
    x: float = 0.0         # centre
    y: float = 0.0
    anchored: bool = False

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        return (self.x - self.width / 2, self.y - self.depth / 2,
                self.x + self.width / 2, self.y + self.depth / 2)

    def polygon(self) -> list[list[float]]:
        x0, y0, x1, y1 = self.bounds
        return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def _overlap(a: PlacedRoom, b: PlacedRoom) -> float:
    ax0, ay0, ax1, ay1 = a.bounds
    bx0, by0, bx1, by1 = b.bounds
    dx = min(ax1, bx1) - max(ax0, bx0)
    dy = min(ay1, by1) - max(ay0, by0)
    return dx * dy if dx > 0 and dy > 0 else 0.0


def solve(rooms: list[PlacedRoom], edges: list[tuple[str, str]],
          iterations: int = 400) -> tuple[list[PlacedRoom], dict]:
    """Position rooms so neighbours touch and nobody overlaps.

    Anchored on the highest-degree room. In a residential property that is the
    connector - the hall here, with five recovered edges - and placing everything
    relative to it matches how the building is actually organised, as well as
    keeping error local: a room misplaced against the hall is wrong on its own,
    while a chain of rooms placed against each other compounds.
    """
    by_id = {r.room_id: r for r in rooms}
    degree = {r.room_id: 0 for r in rooms}
    for a, b in edges:
        if a in degree and b in degree:
            degree[a] += 1
            degree[b] += 1

    if not rooms:
        return [], {"placed": 0, "overlap_area": 0.0, "connected": True}

    hub_id = max(degree, key=lambda k: (degree[k], by_id[k].width * by_id[k].depth))
    hub = by_id[hub_id]
    hub.x = hub.y = 0.0
    hub.anchored = True

    # Spokes around the hub, spaced by angle. Rooms with no recovered edge are
    # still placed - a room the matcher could not link is not a room that ceased
    # to exist - but they go on the outside where they disturb least.
    neighbours = [r for r in rooms if r.room_id != hub_id and degree[r.room_id] > 0]
    orphans = [r for r in rooms if r.room_id != hub_id and degree[r.room_id] == 0]

    def ring(items, radius_pad):
        n = max(1, len(items))
        for i, room in enumerate(items):
            angle = 2 * math.pi * i / n
            radius = (max(hub.width, hub.depth) + max(room.width, room.depth)) / 2 + radius_pad
            room.x = radius * math.cos(angle)
            room.y = radius * math.sin(angle)

    ring(neighbours, 0.10)
    ring(orphans, 0.10 + max((max(r.width, r.depth) for r in neighbours), default=0.0))

    # Relaxation: pull linked rooms together, push overlapping rooms apart. The
    # push is stronger than the pull because the gate forbids overlaps outright
    # while merely preferring neighbours to touch.
    edge_set = [(a, b) for a, b in edges if a in by_id and b in by_id]
    for step in range(iterations):
        cooling = 1.0 - step / iterations
        for a_id, b_id in edge_set:
            a, b = by_id[a_id], by_id[b_id]
            dx, dy = b.x - a.x, b.y - a.y
            dist = math.hypot(dx, dy) or 1e-6
            want = (max(a.width, a.depth) + max(b.width, b.depth)) / 2
            pull = (dist - want) * 0.05 * cooling
            ux, uy = dx / dist, dy / dist
            if not a.anchored:
                a.x += ux * pull; a.y += uy * pull
            if not b.anchored:
                b.x -= ux * pull; b.y -= uy * pull

        for i, a in enumerate(rooms):
            for b in rooms[i + 1:]:
                if _overlap(a, b) <= 0:
                    continue
                dx, dy = b.x - a.x, b.y - a.y
                dist = math.hypot(dx, dy) or 1e-6
                push = 0.15 * cooling * (a.width + b.width) / 2
                ux, uy = dx / dist, dy / dist
                if not a.anchored:
                    a.x -= ux * push; a.y -= uy * push
                if not b.anchored:
                    b.x += ux * push; b.y += uy * push

    total_overlap = sum(_overlap(a, b) for i, a in enumerate(rooms) for b in rooms[i + 1:])
    xs = [c for r in rooms for c in (r.bounds[0], r.bounds[2])]
    ys = [c for r in rooms for c in (r.bounds[1], r.bounds[3])]

    # Footprint is the union of the room rectangles, which with zero overlap is
    # their sum. The bounding box is reported too but is *not* the footprint: it
    # includes the gaps between rooms, and those gaps are an artefact of a layout
    # that places rooms by relaxation rather than by measured position.
    union = sum(r.width * r.depth for r in rooms) - total_overlap

    return rooms, {
        "placed": len(rooms),
        "overlap_area_m2": round(total_overlap, 3),
        "footprint_m2": round(union, 2),
        "bounding_box_m2": round((max(xs) - min(xs)) * (max(ys) - min(ys)), 2),
        "hub_room": hub_id,
        "orphan_rooms": [r.room_id for r in orphans],
        "orphan_note": ("Rooms with no recovered adjacency. They are drawn, because a room the "
                        "matcher could not link has not ceased to exist, but nothing observed "
                        "says where they belong - so they are placed outside the connected group "
                        "rather than guessed into a plausible gap."),
    }
