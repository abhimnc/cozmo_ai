# Benchmark set — inventory

The brief specifies the composition so it cannot be flattered. This tracks what
exists against what is required. Raw captures live in `benchmark/raw/`
(gitignored; submitted separately as deliverable 8).

## Required composition

| # | Requirement | Status | Have |
|---|---|---|---|
| 1 | One multi-room capture, **3+ rooms plus a connector** | **capturable** | The property has 6 rooms off a Hall connector (`ground_truth/property.json`). The existing capture covers Living room, Hall, Bedroom only; re-capture including the kitchen and one more bedroom clears this |
| 2 | One furnished room with **staged damage spanning two damage classes** | **not started** | — |
| 6 | Mirrors, glass, wet-look surfaces, low light (a stated constraint, not a listed row) | **available** | Two bathrooms give mirrors, glass and wet-look surfaces together; the kitchen adds a second instance. Low light still needs staging |
| 7 | A closed-door adjacency, so the photo tier's worst failure mode is measured rather than avoided | **needs staging** | Every connection in this property is an archway. Close the Living room's wall D door or cover an archway and re-capture |
| 3 | The same rooms at **all three tiers**, multi-room set included | **photo only** | LiDAR tier is not capturable on an iPhone 13 (risk #1). Video tier not yet captured |
| 4 | At least one room captured **twice at the same tier** (repeatability gate) | **done** | Living room, photo tier: `..._172319` (4 photos) and `..._174340` (5 photos) |
| 5 | **Laser or tape ground truth** on everything | **not started** | — |

## Room identity does not survive a retype

`Bedroom 1` appears in both single-floor captures and means a **different
physical room** in each. Nothing in the bundle links a room across captures: the
name is whatever the operator typed, and it was typed twice with different
intent.

This matters because two scored outputs depend on room identity holding. The
repeatability gate is "two captures of the same room at the same tier", and the
stitched plan is scored on rooms being in the right place. Any tool that joined
captures by name would have silently merged two bedrooms' photos into one room.

Fixed in the capture app: room names are now offered back from previous captures
rather than retyped, most-recent-first, with names already used in the current
capture greyed out. Until a re-capture, the two existing captures must be
treated as having **disjoint** bedroom sets.

## Captures on hand

| Capture | Tier | Rooms | Photos | Purpose |
|---|---|---|---|---|
| `capture_20260831_023857_photo` | photo | Living Room, Hall, Kitchen, 3 bedrooms | 23 | **the multi-room set.** Contains the Hall, so every room has a connector and the set is stitchable |
| `capture_20260831_030010_photo` | photo | 2 bathrooms, 3 bedrooms | 24 | per-room detail. **Not stitchable alone**: no Hall and no Living room, so none of these five rooms touch each other |
| `capture_20260830_172319_photo` | photo | Living room, Hall, Bedroom | 11 | superseded — mixes two floors |
| `capture_20260830_173700_photo` | photo | Hall2, Living room 2 | 8 | superseded — the second floor |
| `capture_20260830_174340_photo` | photo | Living room | 5 | repeatability partner for the old set |
| `capture_20260830_172252_photo` | photo | — | 0 | empty; keep as a pipeline rejection case |

## Property

Nine spaces: Hall, Living room, three bedrooms, kitchen, small puja room, two
bathrooms. Full graph in `ground_truth/property.json`.

**Every Hall connection is an open archway.** At the photo tier that is the best
case available: an archway carries a through-view, so every adjacency in the
property has direct image evidence and none has to be inferred.

The Hall is a hub: it connects to all six rooms, so the property is a star with the
Hall at the centre. Two things follow. The Hall is the natural anchor for the
stitch, because its error propagates everywhere while a bedroom's stays local.
And a star is almost all tree — which is why the one cycle below matters so much.

This settles requirement 1: six rooms and a connector, comfortably past the
"three or more" the brief asks for. It is a capture problem now, not a property
problem.

Two rooms are worth capturing for reasons beyond the count. The **kitchen** has
glass and wet-look surfaces, which the brief names as a constraint to cover, and
the **puja room** is small — the camera cannot back far enough away to frame a
whole wall, so every view is oblique. Small rooms are also brutally scored: with
few openings the >=85% gate rounds up to 100%.

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
