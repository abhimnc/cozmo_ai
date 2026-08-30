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

## Known hardware constraint

The only device available to this project is an **iPhone 13**. It cannot run
the LiDAR tier, which the brief makes mandatory and which the head-to-head
comparison is specified at. A Pro-class iPhone 15 or newer is required before
the LiDAR tier can be developed, benchmarked, or rehearsed. Tracked as risk #1.
