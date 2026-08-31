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

## Attempt 2 — magicplan: completed

| | |
|---|---|
| App | **magicplan** (Sensopia) |
| Plan | free tier |
| Export | 8-page PDF report, `magicplan_export.pdf` in this directory |
| Device | iPhone 13 (iPhone14,5), iOS 26.3.1 |
| Captured | 9 rooms, total area 69.81 m² |

Numbers transcribed to `magicplan_export.json`. Its AR capture works without
LiDAR, which is why it succeeded where Polycam could not.

## Result: we beat or tie on 3 of 7 shared dimensions — 43%. **Gate is ≥70%. Failed.**

| Room | Dimension | Tape truth | magicplan | err | ours | err | Winner |
|---|---|---|---|---|---|---|---|
| living_room | long wall | 5.02 m | 4.00 | 20.3% | 3.99 | 20.4% | tie |
| living_room | short wall | 3.33 m | 2.87 | 13.8% | 3.89 | 16.7% | magicplan |
| living_room | ceiling | 3.29 m | 2.49 | 24.4% | 2.90 | **12.0%** | **ours** |
| hall | long wall | 7.08 m | 8.35 | 18.0% | 3.81 | 46.2% | magicplan |
| hall | short wall | 2.10 m | 4.09 | 95.2% | 3.46 | **65.2%** | **ours** |
| hall | ceiling | 3.29 m | 3.59 | 9.0% | 2.90 | 12.0% | magicplan |
| hall | floor area | 19.78 m² | 20.24 | 2.3% | 13.17 | 33.4% | magicplan |

Ours better on 2, tie on 1, magicplan better on 4.

## What the comparison actually shows

**We lose, and the margin is honest.** magicplan is a mature product with an AR
capture loop that asks the operator to tap corners; our photo tier infers
geometry from stills with no interaction. Losing 4-2 is the expected result and
there is no reading of the table that makes us the better system today.

**Where we win is where its AR loop has no signal.** Both of our wins are on
quantities the operator never taps: ceiling height and the Hall's short
dimension. Where magicplan gets a corner tapped, it is far better — its Hall
floor area is within **2.3%**, which no part of our pipeline approaches.

**Correction, 2026-08-31.** An earlier version of this file claimed magicplan's
ceiling heights were unreliable, on the evidence that they ranged 1.75 m to
3.59 m across a flat whose ceiling was measured at 3.294 m in two rooms. That
claim was wrong, and it was wrong because of my assumption, not their data.

The operator reports that three rooms genuinely have lower ceilings: both
bathrooms have storage boxed in above them, and bedroom 3 sits over an
underground garage so its floor is raised. Re-read with the architecture
accounted for:

| Room | magicplan | Assessment |
|---|---|---|
| Bedroom C | 1.75 m | genuinely low — garage below |
| Bathroom B | 1.79 m | genuinely low — storage above |
| Bathroom A | 1.96 m | genuinely low — storage above |
| Living Room | 2.49 m | **wrong, −24%** |
| Bedroom B | 2.65 m | **wrong, −20%** |
| Bedroom A | 3.28 m | consistent |
| Other | 3.28 m | consistent |
| Kitchen | 3.33 m | consistent |
| Hallway | 3.59 m | consistent |

magicplan detected three real height changes that a uniform-ceiling assumption
would have marked as errors, and it is wrong on two rooms. Four of the six rooms
expected at 3.294 m land within 10%. That is a materially better result than
this file first reported, and the difference was my premise.

The specific comparison rows above are unaffected: the Living room ceiling is
one of the two magicplan genuinely gets wrong, so our win there stands.

**What this says about our own pipeline is worse.** We quote a *single*
residential ceiling prior for every room. On this property that cannot be right
for both a 3.294 m hall and a bathroom with storage boxed above it — so the
prior is wrong by construction on a third of the rooms, and only looks
acceptable because it is never checked against them. magicplan at least
*measures* the quantity and therefore can detect the change.

**Neither system would pass the brief's gates.** magicplan's best wall error is
13.8% against an ±8% photo-tier gate, and its ceilings miss a 1.5 cm gate by up
to 1.5 m. The gates are demanding of the whole field, not just of us.

## The incumbent is also unrepeatable

magicplan was run twice on the Living room, same app, same device, same day
(`magicplan_rescan.pdf`). The two scans disagree substantially, and the second is
much better:

| Quantity | Tape truth | Scan 1 | err | Scan 2 | err | Scan-to-scan |
|---|---|---|---|---|---|---|
| long wall | 5.017 m | 4.00 | −20.3% | **4.61** | **−8.1%** | 0.61 m |
| short wall | 3.330 m | 2.87 | −13.8% | **3.24** | **−2.7%** | 0.37 m |
| ceiling | 3.294 m | 2.49 | −24.4% | **3.13** | **−5.0%** | 0.64 m |
| area | — | 11.47 m² | — | 13.96 m² | — | 2.49 m² |

The bedroom moved too: ceiling 2.65 → 3.09 m, area 4.47 → 4.97 m².

**Three things follow.**

**magicplan fails the repeatability gate as well.** The gate is 1 cm or 0.5% per
wall; its own scan-to-scan spread is 37–64 cm on one room. Our system is far
worse — 0 of 8, worst 2.69 m — but "same room in, same plan out" is not something
the incumbent delivers either. That is worth knowing before treating any single
scan of it as truth.

**Its best is much better than its first scan suggested.** Scan 2 lands within
2.7% and 8.1% on the walls and 5.0% on the ceiling. On a like-for-like best-scan
basis magicplan would beat us on every dimension, and the comparison table above
— which uses scan 1, the scan taken alongside the rest of the property — flatters
us. Stated because it does.

**It also revises the ceiling correction above.** Scan 1 read the Living room at
2.49 m and this bedroom at 2.65 m, and both were called wrong. Scan 2 reads them
at 3.13 m and 3.09 m, close to the 3.294 m tape figure. So those two were scan
error rather than a systematic ceiling problem, and the bedroom is **not**
genuinely low the way the bathrooms and bedroom 3 are.

## Deviations recorded

- Specified at the **LiDAR tier**; run at the photo tier because no LiDAR-capable
  device exists for this project.
- magicplan reports one width and one length per room. The Hall is L-shaped with
  a stepped wall and a recess, so its 8.35 × 4.09 is a bounding box rather than
  wall lengths — which is why its area is close while its dimensions are not.
  Compared as given rather than reinterpreted.
