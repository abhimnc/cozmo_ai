# Cozmo AI — Technical report

Handheld iPhone capture in, dimensioned room geometry out. Built 30–31 August
2026. This report states what works, what does not, and the numbers behind both.

**Summary in one line:** the pipeline runs end to end on **all three tiers** in
under 11 seconds, produces schema-valid output whose intervals cover the truth
6 times in 6 at the photo tier, and passes **one** accuracy gate of six. Several contracted stages
— opening detection, room placement, damage analysis — are absent, not merely
inaccurate.

---

## 1. Architecture

Four stages, one shared geometry path across tiers.

```
capture bundle ──▶ sensor budget ──▶ per-view geometry ──▶ plan assembly ──▶ plan.json + plan.svg
   (on device)      (enforced)        (shared by tiers)     (intervals)
```

**Capture (`ios/`).** One ARKit session serves all three tiers. Gravity world
alignment (`worldAlignment = .gravity`) puts +Y on the gravity vector, so ceiling
height would be a Y-extent rather than a plane-fit by-product. Keyframes are
gated at 5 cm / 5° with a 1 s floor. The frame writer bounds encodes in flight
and *drops* frames past that, counting the drops into the manifest — a capture
that thinned under load is something the error budget must know.

**Sensor budget (`pipeline/cozmo/budget.py`).** Each bundle's manifest declares
the paths its tier may read. Reads go through `CaptureBundle.open`; anything
outside raises `BudgetViolation`. Poses are recorded at every tier but written
under `_reference/` at the photo and video tiers, where they are out of budget.
This guards the failure that is easy to commit and hard to notice: a debugging
shortcut reading `_reference/poses.jsonl` that is never removed, quietly turning
the photo tier into the LiDAR tier. `cozmo inspect --prove-budget` demonstrates
each out-of-budget read being refused.

**Per-view geometry (`pipeline/cozmo/photo/room.py`).** Detect line segments
(LSD); recover the vertical vanishing point from near-vertical segments; build a
gravity-aligned rotation; back-project floor-candidate edge points onto the floor
plane using a camera-height prior of 1.45 m; then find **wall bases as straight
runs in that floor plane** (`floorplane.py`).

That last step is the substantive one. Seen from above, the base of a planar wall
is a straight line metres long, while furniture is short segments and scatter —
a separation that exists in the bird's-eye view and nowhere in the image. It
replaced a lowest-edge-per-column heuristic that found bed bases, and it produced
the project's only passing dimension. Where no run has enough support, the older
heuristic still applies.

**Plan assembly (`pipeline/cozmo/plan.py`).** Quantities the pipeline can
estimate carry intervals set from measured error. Quantities it cannot are
reported as *absent* — never guessed.

---

## 2. Tier design and device matrix

The tiers differ only in what reaches the pipeline-readable part of the bundle.
All three then run the same estimator, deliberately: sharing it means a tier
comparison measures **what the input is worth**, not which of two
implementations is better.

| Tier | In budget | Withheld |
|---|---|---|
| Photo | `photos/**` | poses, planes |
| Video | `video.mov`, `video_meta.json`, `rooms.json` | poses, planes |
| LiDAR | `rgb/**`, `depth/**`, `poses.jsonl`, `intrinsics.json` | — |

Video frames carry no EXIF, so focal length comes from the device model in the
manifest — a device-matrix fact, not a per-capture calibration.

| Hardware | Photo | Video | LiDAR |
|---|---|---|---|
| iPhone 15/16/17 non-Pro | yes | yes | no |
| iPhone 15/16/17 Pro | yes | yes | yes |
| **iPhone 13 (our only device)** | yes | yes | **no** |

Capability is probed at runtime via `supportsFrameSemantics`, not matched
against model strings, and the probe is written into every manifest.

**The LiDAR tier has never been run on real data.** No LiDAR-capable device was
available. The code path exists and feeds the same estimator; no accuracy claim
is made for it.

---

## 3. Drift handling

**There is none, and the output says so.**

`stitch.drift` is a required schema field with `method` and `applied`. Our plans
emit `method: "none", applied: false` with the note that no inter-room placement
stage exists. This is deliberately distinguished from "poses used as-is", which
the brief makes an automatic fail: the stage is *absent*, and an omitted field
would have read identically to an honest one.

Ablation is therefore not possible. What the benchmark *does* contain is the
constraint an ablation would need: the Living room connects to the Hall, the
Hall to bathroom_2, and bathroom_2 back to the Living room — the property's only
cycle, and the only place a stitch could be caught contradicting itself. Every
other room hangs off the Hall by a single edge that cannot disagree with
anything. The design decision recorded ahead of implementation is that the room
graph is a **multigraph** solved over its full edge set, because the obvious
spanning-tree implementation would use one archway, ignore the other, and report
zero stitching error by discarding its only contradicting evidence.

---

## 4. Error budget

| Term | Magnitude | Basis |
|---|---|---|
| EXIF focal length | **−0.48%** | audited against ARKit intrinsics |
| EXIF rounding to integer mm | 0.49% worst | measured, 8 photos |
| Camera-height prior (1.45 m) | ±10% | prior, dominant scale term |
| Floor-boundary detection | **dominant** | see below; improved by iteration 2 |
| Ground-truth tape uncertainty | 1.56 cm (wall), 14.01 cm (ceiling) | measured, repeat readings |

The scale chain is sound: EXIF is accurate to half a percent, and the 35 mm
convention ambiguity we feared (Apple's 26 mm versus the horizontal convention's
27) does not bite, because our capture app writes the convention it computes.

**The dominant term is still floor-boundary detection**, though less so after
iteration 2. Wall bases are now found as straight runs on the floor plane rather
than as the lowest edge per column, which moved the photo tier from 33.3% to
26.2% median error. What remains is that a room can present no run long enough to
be a wall, and that motion blur produces smears which pass a straightness test —
the cause of the video tier's regression.

**Ground-truth uncertainty is measured**, by repeat tape readings:

| Quantity | sd | Gate | sd ÷ gate |
|---|---|---|---|
| Wall length | 1.56 cm | 40 cm | 0.04 |
| Opening width | 0.99 cm | 2 cm | 0.50 |
| Ceiling height | **14.01 cm** | 1.5 cm | **9.3** |

Wall-length errors are therefore *measured*. **The ceiling gate cannot be
verified by tape at all** — the key is 9.3 times coarser than the tolerance. That
is a finding about method, not only about us: the brief permits laser or tape,
and a tape reading to a 3.3 m ceiling cannot resolve 1.5 cm, so laser is
effectively mandatory for that gate whatever the brief allows.

Two of four recorded quantities also fell outside the range of their own repeats,
so the original single readings carry a bias on top of random spread. They are
kept as the answer key, having been taken systematically in one session, but are
now quoted with uncertainty.

---

## 5. Calibration analysis

Calibration is scored separately from accuracy throughout, and it is the one
thing that works.

`Measurement` cannot be constructed without `ci_low`, `value`, `ci_high`, `unit`
and `method`; the schema enforces the same. Intervals are set from measured
error, not from what would look good: room depth ±30% because it measured 11%
and 23% low; far-wall width ±100% with an explicit warning because it measured
96% and 382% high.

**Coverage: 6 of 6 at the photo tier, 4 of 6 at video.** Intervals come from a
**predictive** spread (`1.96·sd`), not a standard error of the mean
(`1.96·sd/√n`). The distinction matters: views of a non-rectangular room measure
*different walls*, so they are not repeated readings of one quantity, and
dividing by √n made the interval shrink as disagreement accumulated — treating
contradiction as evidence of certainty. The Hall, stepped with a 1.75 m recess,
was where that failed first.

**The resulting intervals are ±100% of their own value.** Full coverage is
therefore a statement about how little the pipeline knows, not about how well it
is calibrated. An interval of "4.58 m, between 0.15 and 9.01" is honest and
nearly useless, and narrowing it requires a better estimator, not better
statistics.

**Known calibration weakness.** Ceiling height is a single residential prior
applied to every room. This property has two bathrooms with storage boxed above
and a bedroom over a garage, so a uniform prior is wrong by construction on a
third of the rooms and only looks acceptable because nothing checks it there.

---

## 6. The fix loop (two iterations)

Declaration committed **before** the fix (`fixloop/DECLARATION.md`).

**Worst gate:** photo-tier wall length, 0 of 4 inside ±8%, median 56.3%, worst
+192.8%.

**Root cause:** floor distance goes as `h / sin(depression)`, so a 3° floor
admitted distances to 27.7 m, and taking the 90th percentile deliberately
selected the shallowest, least reliable rays. `bed_room_1` estimated 28.15 m
against that 27.7 m cap — pinned at the threshold rather than measuring a room.

**A competing hypothesis was tested and rejected**: that open archways let the
floor boundary run into the next room. That predicts more archways giving larger
estimates; measured correlation was **−0.31**, the wrong direction.

**Fix:** depression floor 3° → 8°; percentile 90 → 75.

**Result:** photo median 56.2% → **33.3%** (−41%); video 90.3% → **27.2%**
(−70%); worst single number +192.8% → +65.2%; largest estimate 28.15 m → 8.11 m.

**Predictions: 2 of 4 met.** Met: no estimate over 11 m; coverage held at 5/6.
Missed: median below 30% (got 33.3%); at least one dimension inside the gate (got
none). Direction and mechanism right, magnitude optimistic.

**A bug found while shipping, and disclosed.** The declared threshold change
would have done nothing alone: the depression test compared an unnormalised
ray's `y` component against `sin θ` — a number near 1000 against one near 0.14 —
so the floor had been inert since written. The shipped change is really two, and
crediting the threshold alone would be dishonest.

### Iteration 2 — floor-plane wall detection (`fixloop/ITERATION_2.md`)

The first fix bounded a divergence; its post-mortem named detection as the
remaining cause, and this attacks that. Wall bases become straight runs on the
floor plane instead of the lowest edge per column.

**Photo tier:** median 33.3% → **26.2%**, accuracy 0/6 → **1/6**, calibration
held at 5/6. The living room's short wall lands at **−0.4%** — the project's
first and only passing dimension.

**Video tier: regressed**, 27.2% → 38.3%, calibration 5/6 → 4/6. Two explanations
were tested and rejected — the run-length threshold (swept 0.6–1.6 m, no effect)
and floor-point scarcity (1590 vs 1821 per frame, identical segment counts). What
remains is that motion blur in a walking capture produces elongated smears that
pass a straightness test, so those frames yield *wrong* lines rather than fewer.

Shipped with the regression reported rather than reverted. A tier-conditional
switch was considered and rejected: sharing one estimator is what makes the tier
comparison mean anything, and branching on the tier label would turn it into a
comparison of two implementations.

---

## 7. Known failure modes

**Unrepeatable.** Two photo captures of the same four rooms agree on **0 of 8**
wall dimensions within 1 cm or 0.5%; worst disagreement 3.36 m. The spread
*widened* through iteration 2 even as accuracy improved, because which line the
detector calls the far wall is itself viewpoint-sensitive. The brief asks
which failure this is: **unrepeatable**, not repeatable-but-biased. A biased
system gives the same wrong answer twice; this gives different answers because
which floor-boundary points are found depends on where the operator stood.
Accuracy figures should therefore be read as one sample of a wide distribution.

**Furniture against walls.** The dominant error. A bed base reads as the wall.

**Non-convex rooms.** The Hall is stepped with a recess; a rectangle model cannot
express it, and its interval does not widen to admit that.

**Narrow corridors.** Walls seen at grazing angles, where edge localisation is
worst — and the Hall is simultaneously the hardest room and the one whose error
would propagate everywhere, being the connector.

**Mirrors, glass, wet-look surfaces, low light.** Present in the captures — two
bathrooms, a kitchen — and **not analysed**. A named constraint in the brief, not
addressed.

**Absent stages, not inaccurate ones.** No opening detection, so no openings and
no adjacency. No room placement, so no stitched plan — which the brief calls the
product surface. No damage detection, concealed flags or scope line items. All
marked NOT DONE in `COMPLIANCE.md` rather than described as partial.

---

## 8. What we would do next

1. **A blur or motion gate on video frame selection.** The single clearest
   finding of iteration 2, and the reason one tier regressed while the other
   improved.
2. **Opening detection**, which unlocks adjacency, which unlocks the stitch.
3. **Per-room ceiling estimation** from the wall/ceiling boundary at a known
   floor distance, replacing a prior that is wrong by construction here.
4. **Quantify the tape**, so errors become measured rather than observed.
