# Head-to-head against an incumbent scanning app

## App under comparison

| | |
|---|---|
| App | **Polycam 3D Scanner, LiDAR, 360** |
| Developer | Polycam Inc. |
| Version | **6.0.21** |
| Plan | Basic plan trial (not the free tier) |
| Device | iPhone 13 (iPhone14,5), iOS 26.3.1 |

Recorded as the Basic trial rather than claimed as free tier, because the
comparison should state what was actually used. The brief's wording is that a
free tier is *sufficient*, not that a paid one is disallowed.

## Deviation from the brief, stated up front

The brief specifies this comparison **at the LiDAR tier**. The only device
available to this project is an iPhone 13, which has no rear LiDAR, so no LiDAR
tier capture exists on either side. The comparison is therefore run at the tier
both systems can actually reach on this hardware, and the deviation is recorded
here rather than glossed over. See `docs/RISKS.md` risk 1.

## Rooms

Living room and Hall — the two rooms with complete tape ground truth
(`benchmark/ground_truth/`), so both systems are scored against the same
independent answer key rather than against each other.

## Attempt 1 — Polycam 6.0.21: abandoned

Floorplan mode requires LiDAR, which the iPhone 13 does not have, so the app
routes a non-LiDAR device to photogrammetry capture instead. That path did not
produce a usable floor plan for these rooms and was abandoned after about 30
minutes.

Recorded rather than deleted: the brief says cost is not an accepted reason for
skipping this comparison because free tiers exist, and the honest finding here is
that the incumbent's floor-plan feature is **gated on hardware, not on price**.
A non-Pro iPhone cannot produce a Polycam floor plan at any tier. That is a
substantive result about the incumbent, not an excuse.

## Attempt 2 — magicplan

magicplan's AR room capture works on any ARKit device, LiDAR or not, which makes
it the appropriate comparator for this hardware. In progress.

## Status

Attempt 2 in progress.
