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

Measured against tape ground truth on the Living room and Hall
(`benchmark/BENCHMARK_REPORT.md`). **No tier passes its gate**, and these are the
numbers each honestly delivers rather than the ones it was designed to.

| Tier | Median wall error | Gate | Ceiling | Opening width | Footprint | Calibration |
|---|---|---|---|---|---|---|
| **Photo** | **20.6%** | ±8% — fails | prior only, not estimated | 2 of 3 found, none within 2 cm | 79.5 m² vs ~67, **+19%** | **6 of 6** intervals contain truth |
| **Video** | **58.5%** | ±3% — fails | prior only | not detected | not stitched | 5 of 6 |
| **LiDAR** | **not measured** | — | — | — | — | — |

**The LiDAR row is empty on purpose.** No LiDAR-capable device was available, so
the tier has only ever run on a synthetic bundle. It executes and emits a
schema-valid plan; any accuracy figure from constructed depth would measure the
generator rather than the pipeline.

**Read the wall-error column with the calibration column.** The photo tier is
wrong by about a fifth and says so: every interval it quotes contains the truth.
Its intervals average ±100% of their value, which is honest and not very useful —
see the benchmark report.

**Room-size correlation, all eight rooms: +0.84.** A single-room error figure
hides whether the estimator tracks size at all; this one does. It was +0.10
before two fixes shipped today.

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
