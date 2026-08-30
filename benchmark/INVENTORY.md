# Benchmark set — inventory

The brief specifies the composition so it cannot be flattered. This tracks what
exists against what is required. Raw captures live in `benchmark/raw/`
(gitignored; submitted separately as deliverable 8).

## Required composition

| # | Requirement | Status | Have |
|---|---|---|---|
| 1 | One multi-room capture, **3+ rooms plus a connector** | **partial** | `capture_20260830_172319_photo`: Living room, Bedroom, + Hall as connector. That is 2 rooms + connector — **one room short** |
| 2 | One furnished room with **staged damage spanning two damage classes** | **not started** | — |
| 3 | The same rooms at **all three tiers**, multi-room set included | **photo only** | LiDAR tier is not capturable on an iPhone 13 (risk #1). Video tier not yet captured |
| 4 | At least one room captured **twice at the same tier** (repeatability gate) | **done** | Living room, photo tier: `..._172319` (4 photos) and `..._174340` (5 photos) |
| 5 | **Laser or tape ground truth** on everything | **not started** | — |

## Captures on hand

| Capture | Tier | Rooms | Photos | Purpose |
|---|---|---|---|---|
| `capture_20260830_172319_photo` | photo | Living room, Hall, Bedroom | 11 | multi-room stitch; repeatability A |
| `capture_20260830_173700_photo` | photo | Hall2, Living room 2 | 8 | EXIF validation; second space |
| `capture_20260830_174340_photo` | photo | Living room | 5 | **repeatability B** — same room as 172319 |
| `capture_20260830_172252_photo` | photo | — | 0 | empty; keep as a pipeline rejection case |

## Topology

The Hall is a hub: it connects to many rooms, so the property is a star with the
Hall at the centre. Two things follow. The Hall is the natural anchor for the
stitch, because its error propagates everywhere while a bedroom's stays local.
And a star is almost all tree — which is why the one cycle below matters so much.

This also settles requirement 1: the Hall is the connector the brief asks for
alongside "three or more rooms".

## Loop constraint

The Living room connects to the Hall through two separate archways, on
perpendicular walls. That is a closed cycle in the room graph and the only
source of a measurable stitching residual we currently have at the photo tier.
It makes Hall ground truth load-bearing rather than optional, and it is what
lets the drift ablation run on the photo tier at all. See `docs/DECISIONS.md`.

## Next captures needed, in priority order

1. **Tape ground truth for the Living room.** Wall lengths, ceiling height, and
   every door/window width. Without it none of the captures above can score a
   gate — they are input with no answer key. Cheapest, highest value.
3. **One more room** in the multi-room capture, to satisfy 3 rooms + connector.
4. **Video tier** of the same spaces. Runs on the iPhone 13 today.
5. **A stock Camera app photo** of the same room, to settle the 35 mm-equivalent
   convention empirically (see `docs/ERROR_BUDGET.md`).
6. Staged damage across two classes, and the LiDAR tier — both blocked on other
   things (damage classes need defining; LiDAR needs Pro hardware).

## Note on repeatability

The pair in row 4 is a genuine pair: same physical room, same tier, different
walks (103 s / 4 photos versus 46 s / 5 photos). The differing photo count and
duration are a feature — the gate asks whether the *same room* produces the
*same plan*, not whether identical inputs produce identical outputs. A pair shot
from the same spots would flatter the number.
