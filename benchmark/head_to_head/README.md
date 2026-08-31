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
| Export | 8-page PDF report, "My New Project", 31 August 2026 |
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

**Its ceiling heights are not reliable.** This is a single-storey flat with a
uniform 3.294 m ceiling, measured by tape in two rooms. magicplan reports:

| Room | Ceiling | Error |
|---|---|---|
| Bedroom C | 1.75 m | −47% |
| Bathroom B | 1.79 m | −46% |
| Bathroom A | 1.96 m | −40% |
| Living Room | 2.49 m | −24% |
| Bedroom B | 2.65 m | −20% |
| Bedroom A | 3.28 m | −0% |
| Other | 3.28 m | −0% |
| Kitchen | 3.33 m | +1% |
| Hallway | 3.59 m | +9% |

A **1.84 m spread** across one floor, and **2 of 9** inside the brief's 1.5 cm
ceiling gate. Our own ceiling figure is a stated prior, not an estimate, and it
still beats theirs in the Living room — which says less about our pipeline than
about how hard this quantity is for the incumbent too.

**Neither system would pass the brief's gates.** magicplan's best wall error is
13.8% against an ±8% photo-tier gate, and its ceilings miss a 1.5 cm gate by up
to 1.5 m. The gates are demanding of the whole field, not just of us.

## Deviations recorded

- Specified at the **LiDAR tier**; run at the photo tier because no LiDAR-capable
  device exists for this project.
- magicplan reports one width and one length per room. The Hall is L-shaped with
  a stepped wall and a recess, so its 8.35 × 4.09 is a bounding box rather than
  wall lengths — which is why its area is close while its dimensions are not.
  Compared as given rather than reinterpreted.
