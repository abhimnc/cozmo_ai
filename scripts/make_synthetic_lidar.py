"""Build a synthetic LiDAR capture bundle.

The LiDAR tier has never run on real data: the only device available to this
project is an iPhone 13, which has no rear LiDAR. That leaves the code path
untested, and the walk-in test lets the graders choose the tier on the day. An
untested path that crashes in front of them costs the whole tier.

So this constructs a bundle with the exact shape `CaptureController` writes at
the LiDAR tier - rgb keyframes, Float32 depth and UInt8 confidence maps, a
`poses.jsonl` with room indices, intrinsics and plane anchors - by re-using RGB
frames from a real photo capture and synthesising the depth and pose streams
around them.

**This is a smoke test, not a benchmark.** It proves the tier loads, enforces its
budget, and produces a plan without crashing. It proves nothing about accuracy,
and no accuracy number from it appears anywhere in the benchmark report.
"""

from __future__ import annotations

import json
import math
import shutil
import struct
import sys
from pathlib import Path

SRC = Path("benchmark/raw/capture_20260831_031153_photo")
DST = Path("benchmark/raw/capture_synthetic_lidar")

DEPTH_W, DEPTH_H = 256, 192
FRAMES_PER_ROOM = 4


def main() -> int:
    if not SRC.exists():
        print(f"source capture not found: {SRC}", file=sys.stderr)
        return 2

    if DST.exists():
        shutil.rmtree(DST)
    (DST / "rgb").mkdir(parents=True)
    (DST / "depth").mkdir(parents=True)
    (DST / "_reference").mkdir(parents=True)

    src_manifest = json.loads((SRC / "manifest.json").read_text())
    src_rooms = json.loads((SRC / "rooms.json").read_text())

    poses = []
    index = 0
    for room in src_rooms["rooms"]:
        folder = DST.parent / SRC.name / "photos" / f"{room['index']:02d}_{room['slug']}"
        photos = sorted(folder.glob("*.jpg"))[:FRAMES_PER_ROOM]
        for k, photo in enumerate(photos):
            stem = f"{index:06d}"
            shutil.copy(photo, DST / "rgb" / f"{stem}.jpg")

            # Depth: a plausible floor-to-wall gradient rather than noise, so the
            # geometry stage receives something structured enough to exercise it.
            depth = bytearray()
            conf = bytearray()
            for row in range(DEPTH_H):
                # Nearer at the bottom of the frame, further towards the horizon.
                d = 1.2 + 6.0 * (1.0 - row / DEPTH_H) ** 2
                for _ in range(DEPTH_W):
                    depth += struct.pack("<f", d)
                    conf.append(2)
            (DST / "depth" / f"{stem}.depth").write_bytes(bytes(depth))
            (DST / "depth" / f"{stem}.conf").write_bytes(bytes(conf))

            angle = 2 * math.pi * k / max(1, len(photos))
            poses.append({
                "index": index,
                "timestamp": 1000.0 + index * 0.2,
                "t_rel": index * 0.2,
                # Column-major, world <- camera, yaw only.
                "transform": [math.cos(angle), 0, -math.sin(angle), 0,
                              0, 1, 0, 0,
                              math.sin(angle), 0, math.cos(angle), 0,
                              0.3 * k, 1.45, 0.3 * k, 1],
                "intrinsics": [3038.5, 0, 0, 0, 3038.5, 0, 2016.0, 1512.0, 1],
                "image_width": 4032, "image_height": 3024,
                "tracking_state": "normal", "tracking_reason": None,
                "ambient_intensity": 900.0, "room_index": room["index"],
            })
            index += 1

    (DST / "poses.jsonl").write_text("\n".join(json.dumps(p) for p in poses) + "\n")
    (DST / "intrinsics.json").write_text(json.dumps({
        "schemaVersion": 1,
        "intrinsics": [3038.5, 0, 0, 0, 3038.5, 0, 2016.0, 1512.0, 1],
        "imageWidth": 4032, "imageHeight": 3024,
        "distortionModel": "none_arkit_rectified",
    }, indent=2))
    (DST / "anchors.json").write_text(json.dumps({"schemaVersion": 1, "planes": []}, indent=2))
    (DST / "_reference" / "note.txt").write_text(
        "Synthetic bundle. Depth and poses are constructed, not captured.\n")

    manifest = dict(src_manifest)
    manifest.update({
        "captureId": DST.name,
        "tier": "lidar",
        "frameCount": index,
        "photoCount": 0,
        "sensorBudget": ["manifest.json", "rooms.json", "rgb/**", "depth/**",
                         "poses.jsonl", "intrinsics.json", "anchors.json"],
        "budgetRationale": "Depth, poses and intrinsics, as the spec defines this tier.",
        "operatorNote": ("SYNTHETIC. Depth maps and poses are constructed, RGB frames are reused "
                         "from a real photo capture. Exists to exercise the LiDAR code path, which "
                         "no available device can produce. Not benchmark data; no accuracy claim."),
    })
    (DST / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (DST / "rooms.json").write_text(json.dumps(src_rooms, indent=2))

    print(f"built {DST} with {index} frames across {len(src_rooms['rooms'])} rooms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
