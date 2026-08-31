# Mirrors, glass, wet-look surfaces and low light

A named constraint: *"Real properties contain mirrors, glass, wet-look surfaces
and low light. Cover them in your submission."* This is what we observed in our
own captures, what each surface does to each stage, and what is and is not
handled.

Our property supplies all four without staging: two bathrooms (mirrors, glazed
tile, wet-look ceramic), a kitchen (glass, steel, gloss), and rooms photographed
between 03:00 and 04:00 by artificial light.

---

## What our captures actually show

| Room | Views usable | Rejected | Median brightness | Hard surfaces |
|---|---|---|---|---|
| living_room | 7 | 1 | 142 | — |
| hall | 8 | 1 | 138 | — |
| bed_room_2 | 6 | 0 | 146 | — |
| bathroom_1 | 4 | **2 of 6** | 156 | mirrors, glazed tile, wet-look |
| bathroom_2 | 7 | 2 | **97** | mirrors, glazed tile, wet-look |
| kitchen | 7 | 2 | **104** | glass, steel, gloss |
| bedroom_3 | 6 | 2 | 100 | — |
| bed_room_1 | **3 of 6** | **3** | 135 | — |

**The rejection rate is higher in the hard-surface rooms**, but not dramatically,
and `bed_room_1` — a plain bedroom — has the worst rate of all. So on this
evidence the pipeline is not *specifically* defeated by these surfaces; it is
weak generally, and they make a weak stage slightly weaker.

The two darkest rooms in the property are the kitchen (104) and bathroom_2 (97),
against ~140 elsewhere. Both are also over-estimated by more than 4× in area,
which is consistent with low light degrading edge detection — though with two
rooms it is a correlation, not a demonstration.

---

## What each surface does, stage by stage

**Mirrors** are the most dangerous, because they fail *silently*. A mirror shows
a geometrically valid reflected room: real straight lines, a real-looking
floor/wall junction, a plausible vanishing point. Nothing in our pipeline can
tell a reflected wall base from a real one, so a mirror large enough to show the
floor line would be fitted as a wall **behind** the actual wall, roughly doubling
the room. We do not detect mirrors and have no defence against this.

Worse, it corrupts the adjacency stage too: a mirror reflecting a doorway creates
image content shared between rooms that do not adjoin.

**Glass** behaves like a mirror at grazing angles and like a window head-on.
A glazed door produces a through-view that the adjacency matcher reads as an
opening, which happens to be *correct* — you can see the next room — but the
opening detector sees jambs at the glass, not at the frame.

**Wet-look and gloss surfaces** produce specular highlights that move with the
camera. Between two views of one room, a highlight is in a different place, so
feature matching finds no correspondence there. This costs adjacency recall
rather than accuracy: our bathrooms are where the matcher's one false positive
lives, and they match each other on *tiling pattern* rather than on shared space.

**Low light** raises sensor noise and lowers edge contrast, which directly starves
the two stages everything rests on: line-segment detection and the floor boundary.
It also lengthens exposure, so a walking video capture blurs more — which is the
measured cause of the video tier's regression.

---

## What is handled

**Little, and honestly so.** Three things help incidentally rather than by design:

1. **Views are rejected, not forced.** A view that yields no usable geometry is
   dropped with a stated reason rather than contributing a bad estimate. That is
   why the bathrooms lose 2 views each instead of producing confident nonsense.
2. **Intervals widen with disagreement.** The predictive interval reflects
   view-to-view spread, and specular surfaces produce disagreement, so the
   uncertainty grows where these surfaces are — which is the correct direction
   even though nothing detects them.
3. **The capture protocol warns against photographing a mirror head-on.** One
   line, and it is the only deliberate mitigation in the system.

---

## What we would build

1. **Mirror detection before geometry.** The strongest cue is that a reflection's
   vanishing points are consistent with the *reflected* frame, so a region whose
   fitted geometry is a mirror image of the surrounding room is a mirror. Cheap
   to test, and it is the single highest-risk surface.
2. **Specular masking** from multi-view intensity variance: a pixel that changes
   brightness sharply between views of the same surface is a highlight, not
   texture, and should be excluded from matching.
3. **An exposure gate on capture**, warning the operator in-app when a room is
   too dark rather than discovering it in the pipeline afterwards.

None is implemented. The first is the one that matters: everything else degrades
accuracy, while an undetected mirror produces a confident, wrong, geometrically
self-consistent room.
