"""Turning a walkthrough clip into per-room stills.

The video tier's budget is the clip, the room markers and the clip metadata —
no poses. So the clip is cut at the room markers and sampled within each
segment, and everything downstream is the photo-tier estimator. That is a
deliberate choice: sharing the estimator means the tier comparison measures what
the *input* is worth rather than which of two implementations is better.

Frames carry no EXIF, so focal length comes from the device model recorded in
the manifest. That is a device-matrix fact, not a per-capture calibration.
"""

from __future__ import annotations

from pathlib import Path

import cv2

from ..bundle import CaptureBundle

# Sampled per room segment. Enough for a spread; few enough to keep a 5-minute
# clip inside a walk-in test's patience.
FRAMES_PER_ROOM = 6

# Skip this much after entering a room: the operator is usually still moving
# through the doorway, and those frames see the door frame rather than the room.
ENTRY_SKIP_S = 2.0


def frames_by_room(bundle: CaptureBundle, cache: Path | None = None) -> dict[str, list[str]]:
    bundle.budget.require("video.mov")
    bundle.budget.require("video_meta.json")
    meta = bundle.read_json("video_meta.json")
    duration = float(meta.get("durationSeconds") or 0.0)

    cache = cache or (bundle.root.parent / f".cache_{bundle.capture_id}_frames")
    cache.mkdir(parents=True, exist_ok=True)

    # Room markers cut the clip. A room entered more than once - the Hall on a
    # hub-and-spoke walk - contributes every visit.
    marks = [(r.slug, r.entered_at_seconds or 0.0) for r in bundle.rooms]
    marks.sort(key=lambda m: m[1])
    segments: dict[str, list[tuple[float, float]]] = {}
    for i, (slug, start) in enumerate(marks):
        end = marks[i + 1][1] if i + 1 < len(marks) else duration
        if end - start > ENTRY_SKIP_S + 0.5:
            segments.setdefault(slug, []).append((start + ENTRY_SKIP_S, end))

    cap = cv2.VideoCapture(str(bundle.root / "video.mov"))
    fps = cap.get(cv2.CAP_PROP_FPS) or 60.0
    out: dict[str, list[str]] = {}
    try:
        for slug, spans in segments.items():
            wanted: list[float] = []
            total = sum(e - s for s, e in spans)
            for s, e in spans:
                n = max(1, round(FRAMES_PER_ROOM * (e - s) / total)) if total else 1
                wanted += [s + (e - s) * (k + 0.5) / n for k in range(n)]
            paths = []
            for k, t in enumerate(wanted):
                dst = cache / f"{slug}_{k:03d}.jpg"
                if not dst.exists():
                    cap.set(cv2.CAP_PROP_POS_FRAMES, int(t * fps))
                    ok, frame = cap.read()
                    if not ok:
                        continue
                    cv2.imwrite(str(dst), frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
                paths.append(str(dst))
            out[slug] = paths
    finally:
        cap.release()
    return out
