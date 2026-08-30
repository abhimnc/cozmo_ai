# Design decisions log

Running log. Each entry: the decision, the alternatives, why. This is the
source material for the technical report and for the live defense.

## 2026-08-30 — Capture route: Route 1 (own iOS app)

**Decision.** Build our own ARKit capture app rather than writing a protocol
around a stock scanner.

**Alternatives.** Route 2 with a stock LiDAR logging app (Record3D, 3D Scanner
App) plus a one-page protocol.

**Why.** Three reasons, in order of weight:

1. The drift-accountability gate requires us to do something specific with
   accumulated pose error and show an ablation with it on and off. That needs
   the raw pose stream and preferably raw depth, not a vendor's already-fused
   export.
2. The tiers must be *honestly* separated. With our own app we control exactly
   what each tier writes to disk, so the photo tier physically cannot leak
   poses into the pipeline. With a stock app we would be filtering a richer
   export and asking the graders to trust us.
3. The walk-in test is 30% and runs on their phone, on the day. One app with
   three buttons is a smaller failure surface than a page of instructions for
   a third-party app whose UI may have changed.

**Cost accepted.** Install must be under 10 minutes on their device, which
means a TestFlight build (needs App Store Connect) or a dev build with their
device UDID registered. This is a scheduling risk, tracked in RISKS.md.

## 2026-08-30 — Tiers are enforced, not conventional

**Decision.** Each capture bundle declares its tier in `manifest.json`, and the
pipeline loads inputs through a per-tier "sensor budget" that raises on any
read outside the budget.

**Why.** The spec's tier ladder only means something if thin tiers are actually
thin. LiDAR tier is defined as "depth, poses and intrinsics"; video tier is
therefore RGB frames with no supplied poses, and photo tier is stills with no
depth and no poses. The capture app records everything it can (poses at every
tier are useful to *us* as an internal reference), but writes non-budget
signals into a `_reference/` subtree the pipeline is forbidden to open at that
tier. This gives us a clean answer at the defense and an honest error budget.

## 2026-08-30 — Photo-tier EXIF is written deliberately, and rounded

**Found on the first real device capture.** The photo tier's sensor budget is
`photos/**`, so whatever is not inside those JPEGs is information the photo path
does not have. Re-encoding a bare `CGImage` through `UIImage.jpegData` produced
files with five EXIF tags and no camera model, no focal length. That is thinner
than a photo from the stock Camera app — we had made our own floor tier harder
than the brief asks, and unlike the photos a grader would produce.

**Decision.** Write the EXIF a stock iPhone photo carries: make, model,
`FocalLenIn35mmFilm`, pixel dimensions, capture time.

**The line we are drawing.** ARKit's live per-frame intrinsics are a calibration
we are not entitled to at this tier. An integer 35 mm-equivalent focal length is
a fixed property of the lens that every iPhone photo reports. So the value is
rounded to the whole millimetre before it is written, which is exactly what
separates the two. The unrounded ARKit estimate stays in `_reference/`, out of
budget, where it becomes the ground truth for measuring what the EXIF
approximation costs us. That measurement belongs in the error budget.

**Also fixed here.** The photos were being tagged EXIF orientation 6 while the
pixels stayed in the sensor's native landscape frame — the frame the intrinsics
describe. Correctness then depends on whether the reader honours EXIF
orientation, and a library that silently rotates turns a principal point into a
transposed one. Orientation is now 1 and the pixels are left alone.

## 2026-08-30 — Signing team, second pass

Selecting a team in Xcode's Signing & Capabilities writes `DEVELOPMENT_TEAM`
into the **target** build settings of the generated `.xcodeproj`, and a
target-level setting beats the project-level one. So the xcconfig indirection
added earlier was silently defeated the moment anyone touched that pane, and a
real team ID went back into the committed project file.

`project.yml` now sets `DEVELOPMENT_TEAM: $(COZMO_DEVELOPMENT_TEAM)` at target
level as well, so regenerating restores the indirection. This will recur every
time someone edits Signing & Capabilities in the GUI; `xcodegen generate` is the
fix, and `grep DEVELOPMENT_TEAM ios/CozmoCapture.xcodeproj/project.pbxproj`
should only ever show `$(COZMO_DEVELOPMENT_TEAM)` before a commit.
