# Device matrix

Which tier runs on which hardware, and what it honestly delivers.

Capability is decided at runtime by asking ARKit (`supportsFrameSemantics`,
`supportsSceneReconstruction`), not by matching model strings — see
`ios/CozmoCapture/Capture/DeviceCapabilities.swift`. Every capture bundle
carries the probe result in `manifest.json`, so the matrix below is
reproducible from any capture we submit rather than asserted here.

## Tier support

| Hardware | Photo | Video | LiDAR | Notes |
|---|---|---|---|---|
| iPhone 15 / 16 / 17 (non-Pro) | yes | yes | no | No rear LiDAR. ARKit world tracking available, so poses exist but are withheld at these tiers by design. |
| iPhone 15 Pro / 16 Pro / 17 Pro (and Max) | yes | yes | yes | Full tier. `sceneDepth` at 256x192, `smoothedSceneDepth`, scene mesh with classification. |
| iPhone 13 (our current dev device) | yes | yes | **no** | Below the iPhone 15 floor the brief sets, and no LiDAR. Usable for photo/video development only — not for benchmark numbers. |

## Accuracy delivered per tier

**Not yet measured.** These rows get filled from `benchmark/` against tape and
laser ground truth, and stay empty until then. Publishing a number here before
the benchmark exists is exactly the "confident garbage" the brief penalises.

| Tier | Wall length | Ceiling height | Opening width | Stitched footprint | Gate |
|---|---|---|---|---|---|
| LiDAR | — | — | — | — | Round 1 gates + ≤2 cm openings, ≤1.5 cm ceiling |
| Video | — | — | — | — | wall lengths ±3% |
| Photo | — | — | — | — | wall lengths ±8%, footprint ±8% |

## LiDAR tier readiness

The tier has **never seen real LiDAR data** — no available device produces it.
To ensure it does not fail cold at the walk-in test, where the grader chooses
the tier on the day, it is exercised against a synthetic bundle built by
`scripts/make_synthetic_lidar.py`:

```
python scripts/make_synthetic_lidar.py
cozmo run benchmark/raw/capture_synthetic_lidar
```

That loads, enforces the tier's sensor budget, runs the geometry and emits a
schema-valid plan in 4.1 s across 8 rooms. It proves the **path executes**; it
proves nothing about accuracy, and no number from it appears in the benchmark
report.

The synthetic run also caught a real defect: `--prove-budget` used a fixed list
of paths to attempt, and `poses.jsonl` is in budget at the LiDAR tier while out
of it at the others, so it reported a false budget violation. Now tier-aware.

## Known hardware constraint

The only device available to this project is an **iPhone 13**. It cannot run
the LiDAR tier, which the brief makes mandatory and which the head-to-head
comparison is specified at. A Pro-class iPhone 15 or newer is required before
the LiDAR tier can be developed, benchmarked, or rehearsed. Tracked as risk #1.
