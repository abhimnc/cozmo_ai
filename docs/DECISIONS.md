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
