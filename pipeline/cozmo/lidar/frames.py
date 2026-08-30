"""Per-room keyframes from a LiDAR capture.

The LiDAR bundle already stores selected RGB keyframes with a room index in
`poses.jsonl`, so grouping them is a lookup rather than a decode.

This path is **written but not validated on real data**: the only device
available to this project is an iPhone 13, which has no rear LiDAR, so no LiDAR
capture exists to test it against. It runs, and it feeds the same estimator as
the other tiers, but any accuracy claim for this tier would be unfounded. The
depth maps the bundle carries are not yet used - using them is the obvious next
gain, since depth removes the camera-height prior that dominates the photo
tier's error.
"""

from __future__ import annotations

import json

from ..bundle import CaptureBundle


def frames_by_room(bundle: CaptureBundle) -> dict[str, list[str]]:
    bundle.budget.require("poses.jsonl")
    index_to_slug = {r.index: r.slug for r in bundle.rooms}

    out: dict[str, list[str]] = {}
    with bundle.open("poses.jsonl", "r") as fh:
        for line in fh:
            rec = json.loads(line)
            slug = index_to_slug.get(rec.get("room_index"))
            if slug is None:
                continue
            rel = f"rgb/{rec['index']:06d}.jpg"
            if (bundle.root / rel).exists():
                out.setdefault(slug, []).append(str(bundle.root / rel))
    # Thin to a manageable number per room, evenly spaced through the walk.
    for slug, paths in out.items():
        if len(paths) > 8:
            step = len(paths) / 8
            out[slug] = [paths[int(i * step)] for i in range(8)]
    return out
