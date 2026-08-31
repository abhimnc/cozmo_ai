# Fix declaration

Written **before** the fix was implemented. Commit history shows this file
landing ahead of the change it predicts.

## 1. The single worst-performing gate, with the failing number

**Photo-tier wall lengths, gate ±8%. Result: 0 of 4 wall dimensions pass.**

| Room | Quantity | Truth | Estimate | Error |
|---|---|---|---|---|
| hall | short wall | 2.095 m | 6.133 m | **+192.8%** |
| hall | long wall | 7.079 m | 12.521 m | +76.9% |
| living_room | short wall | 3.330 m | 4.514 m | +35.6% |
| living_room | long wall | 5.017 m | 6.540 m | +30.3% |

Median absolute error **56.3%**. Worst single number **+192.8%**.

Ceiling height also fails, but it is not the worst gate and not the target here:
it fails because there is no ceiling estimator at all, only a stated prior. That
is a missing stage, not a broken one.

## 2. Root-cause hypothesis, and the evidence

**Hypothesis: the estimator is dominated by rays that carry no range
information.**

Room depth comes from back-projecting the floor boundary onto the floor plane.
For a camera at height *h*, a ray depressed θ below horizontal meets the floor at
`d = h / sin θ`. That diverges as θ → 0:

| Depression | Distance |
|---|---|
| 3° | 27.7 m |
| 6° | 13.9 m |
| 8° | 10.4 m |
| 15° | 5.6 m |

The current implementation admits any ray beyond **3°** and then takes the
**90th percentile** of the resulting distances as room depth. That is a
near-worst-case combination: the shallowest rays produce the largest distances,
and a high percentile deliberately selects them.

**Evidence.**

- `bed_room_1` estimates **28.15 m**, against the 3° cap of 27.7 m. It is pinned
  at the geometric limit of the threshold, not measuring a room.
- Estimated depths run 2.80 m to 28.15 m across eight rooms of one flat. A
  residential room is rarely over 10 m; half the estimates are physically
  implausible on their face.
- The two rooms that look sane, kitchen (2.80 m) and bathroom_2 (3.00 m), are
  the two smallest, where the floor boundary is necessarily steeply depressed.

**A competing hypothesis was tested and rejected.** Every room in this property
connects by open archway, so the floor boundary might continue through an
opening and measure the next room's floor. If so, rooms with more archways would
overestimate more. Measured correlation between archway count and estimated
depth: **−0.31** — the wrong direction. The Hall has nine openings and the
third-*smallest* estimate. Rejected.

## 3. The fix, and the number predicted after it

**Fix.** Two changes to `pipeline/cozmo/photo/room.py`:

1. Raise the minimum depression from 3° to **8°**, bounding recoverable range at
   10.4 m. Justified by indoor geometry rather than by our data: a residential
   room longer than 10 m is rare, and beyond that a tenth of a degree of pixel
   noise moves the answer by metres.
2. Replace the 90th-percentile far distance with the **75th percentile** of the
   surviving rays. Still an upper estimate, since the far wall should be among
   the more distant boundary points, but no longer selecting the extreme tail.

**Prediction.**

- Median absolute wall-length error falls from **56.3%** to **below 30%**.
- At least **1 of 4** wall dimensions comes inside the ±8% gate (currently 0).
- No estimate exceeds 11 m.
- Interval coverage stays at **5 of 6 or better** — the fix must not buy accuracy
  by narrowing intervals until they stop covering the truth.

**Stated risk.** This attacks the divergence, not the underlying detection. The
floor boundary is found as the lowest strong edge per column, which in a
furnished room is often the base of a bed or cupboard rather than the wall. If
that dominates, the error will move but not to inside the gate, and the
post-mortem will say so.
