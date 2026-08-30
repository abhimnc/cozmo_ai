# Cozmo AI — Round 2

Handheld iPhone capture in, dimensioned whole-property floor plan and damage
scope out. One command per capture.

## Status

Early. The capture app builds and runs all three tiers; the pipeline does not
exist yet.

| Piece | State |
|---|---|
| iOS capture app (`ios/`) | builds, all three tiers wired, LiDAR untestable on available hardware |
| Capture bundle format (`ios/CozmoCapture/Capture/CaptureBundle.swift`) | v1, versioned |
| Pipeline (`pipeline/`) | not started |
| Output JSON schema (`schema/`) | not started |
| Benchmark set (`benchmark/`) | not captured |

## Layout

```
ios/          Route 1 capture app (ARKit, Swift, XcodeGen)
pipeline/     capture bundle -> floor plan + damage + scope
schema/       published output schema
benchmark/    benchmark captures, ground truth, gate results
docs/         decisions, risks, capture protocol, device matrix
scripts/      weight fetching, reproduction entry points
```

## Building the capture app

```
brew install xcodegen
cd ios && xcodegen generate
open CozmoCapture.xcodeproj
```

Or from the command line, against a connected device:

```
cd ios
xcodebuild -project CozmoCapture.xcodeproj -scheme CozmoCapture \
  -destination 'id=<device-udid>' -allowProvisioningUpdates build
```

`xcrun devicectl list devices` gives the UDID.

**Toolchain requirement:** the Xcode version must be new enough for the iOS
version on the target phone. Xcode 16.4 tops out at iOS 18.x device support.

## Key design points

- **Tiers are enforced, not conventional.** Each bundle's `manifest.json`
  declares a `sensor_budget` — the paths the pipeline may read at that tier.
  Poses are recorded at every tier but written under `_reference/` at the video
  and photo tiers, where they are out of budget. See `docs/DECISIONS.md`.
- **Gravity-aligned world.** `worldAlignment = .gravity` puts +Y on the gravity
  vector, so ceiling height is a Y-extent rather than a plane-fit by-product.
- **Continuous tiers capture the whole property in one session**, so every room
  shares a coordinate frame and stitching starts from real adjacency.

See `docs/CAPTURE_PROTOCOL.md` for what the person holding the phone does.
