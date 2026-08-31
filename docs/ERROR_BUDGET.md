# Error budget

Measured contributions, not estimates. Every row here traces to a capture in
`benchmark/raw/` and a script that recomputes it. Rows stay out until measured.

## Photo tier

### EXIF focal-length rounding — **measured, 0.49% worst case**

The photo tier may read `photos/**` only, so it recovers focal length from
EXIF `FocalLengthIn35mmFilm`, which is an integer. We write that integer by
rounding ARKit's live estimate, deliberately (see `DECISIONS.md`). The cost:

| Capture | Photos | Mean fx error | Worst fx error |
|---|---|---|---|
| `capture_20260830_173700_photo` | 8 | −0.36% | 0.49% |

Against a ±8% wall-length gate this is negligible — roughly 1/16th of the
budget. Rounding is not where the photo tier will fail.

### **OPEN: the 35 mm-equivalent convention is ambiguous, and it is worth ~4%**

Our EXIF says `FocalLengthIn35mmFilm = 27` for the iPhone 13 wide camera,
computed as `fx · 36 / imageWidth` — the horizontal convention against a 36 mm
full-frame width. Apple markets the same lens as **26 mm**, which is a different
convention (diagonal, on a 3:2 frame).

This matters because the brief's floor tier is "any picture in". If a grader
supplies stills from the **stock Camera app**, their EXIF will carry Apple's
number, not ours. A pipeline that assumes the horizontal convention would
compute `fx = 26 · 4032 / 36 = 2912` against a true ~3045 — a **−4.4% scale
error**, over half the ±8% gate consumed before any geometry runs.

Consequences to handle in the pipeline:

1. Never trust a single convention. Derive focal length from EXIF, then
   cross-check it against vanishing-point or plane-consistency geometry
   recovered from the images themselves, and widen the interval when they
   disagree.
2. Treat a photo set of unknown provenance as having a focal-length prior with
   a ±5% spread, not a point value. This is precisely the kind of thin input
   where the brief expects intervals to widen rather than for us to sound
   confident.

**To do:** shoot the same room with the stock Camera app on the same phone and
read its EXIF, to pin down Apple's convention empirically rather than by
argument.

## Photo tier: geometric focal length — **does not work yet**

**Attempt.** Recover focal length from vanishing points, independently of EXIF,
to check the 4% 35 mm-convention ambiguity recorded above. A rectangular room
has three orthogonal edge directions; two orthogonal vanishing points determine
f through `v1 . v2 + f^2 = 0`.

**Result on the 5-photo Living room capture, against a known 3024 px:**

| Approach | Photos usable | Median error | Worst |
|---|---|---|---|
| Greedy 3 strongest vanishing points | 5 of 5 | +35.7% | +76% |
| Joint Manhattan search, orthogonality enforced | 5 of 5 | +10.7% | +436% |
| …plus physical focal bound (0.4-2.5 image widths) | 5 of 5 | +10.7% | +124% |
| …plus per-axis support floor | 1 of 5 | −14.8% | −14.8% |

A threshold sweep over the axis-support and explained-fraction gates found no
setting that keeps more than one photo of five inside anything near ±8%.

**Diagnosis.** Two failures were found and fixed, and one remains.

1. *Fixed.* Choosing the three strongest line families and checking orthogonality
   afterwards does not work indoors: the strongest families are furniture, rugs
   and curtain folds. Orthogonality has to constrain the search.
2. *Fixed.* Scoring a frame by its union of inliers rewards large focal lengths.
   As f grows every vanishing point recedes, families become near-parallel, and
   the angular test accepts more of the image — so a frame at twice the true
   focal length out-scores the correct one. Visible as a bimodal result, one
   cluster near truth and one near 2x.
3. *Open.* Per-image estimation is simply ill-conditioned on furnished rooms.
   A single photo often shows one wall well and the others obliquely, so one
   axis is weakly supported and its vanishing point poorly located.

**Consequence, stated rather than hidden.** EXIF remains the photo tier's only
scale source, and the 4% convention ambiguity is **unresolved**. Photo-tier
intervals must carry it. Claiming ±8% wall lengths while half that budget sits
in an unchecked focal-length assumption would be exactly the confident garbage
the brief caps scores for.

**Evaluated again on 23 photos, 6 rooms (`capture_20260831_023857_photo`).**
A larger set made the failure legible: the error is not noise, it is a
**systematic +69% bias**, and every gate built to suppress it makes it worse.

| Per-axis support floor | Frames kept | Median error |
|---|---|---|
| 0.03 | 22 of 23 | +69% |
| 0.06 | 19 | +96% |
| 0.09 | 16 | +104% |
| 0.12 | 11 | +109% |
| 0.20 | 2 | +152% |

**Root cause, now identified.** The objective is monotonically biased toward
large focal lengths. As f grows every vanishing point recedes, the line families
become near-parallel, and a fixed angular threshold accepts a wider swath of the
image — so an inflated frame scores higher on *every* axis at once. Gating on
per-axis support therefore selects harder for inflated frames rather than
against them, which is exactly what the sweep shows. The explained-fraction gate
is equally useless: the single worst estimate (+226%) explained 82% of line
structure.

The fix is to change the objective, not to add gates on top of it. The count of
inliers has to be normalised against how many a *random* frame at that focal
length would collect, so a frame is scored on the inliers it wins beyond chance.
Joint multi-image estimation was the earlier plan and it does **not** fix this
on its own: a shared focal length across 23 images would converge on the same
+69%, because the bias is coherent across images rather than averaging out.

**Audit against withheld data.** Running from outside the pipeline, against
ARKit intrinsics in `_reference/` that the photo tier cannot read:

| Source | Focal (px) | Error vs ARKit |
|---|---|---|
| ARKit, 23 frames | 3038.5 median | — |
| EXIF, what the tier uses | 3024.0 | **−0.48%** |
| Geometric estimator | ~5100 | +69% |

This reverses the priority. EXIF is accurate to half a percent on our own
captures, so the 35 mm-convention worry does not bite here — our capture app
writes the convention it computes. The risk was always about *stock Camera*
photos carrying Apple's 26 mm instead, and that remains untested. Meanwhile the
"independent check" is far less trustworthy than the thing it was built to
check, and must not be allowed to widen an interval that EXIF already gets
right.

**What is kept in the meantime.** The rejection behaviour. The estimator now
refuses roughly four photos in five rather than reporting a number it cannot
support. That is worth more than a plausible average: the brief scores
calibration at every tier, and an honest abstention costs less than a confident
error.

## Ground-truth side

### Ceiling flatness — **withdrawn**

An earlier reading of the Living room gave wall heights of 325.4/325.9 cm, a
0.5 cm corner-to-corner spread, and that was written up here as a floor on
achievable ceiling accuracy. The operator's corrected measurement (2026-08-31)
gives a uniform 329.4 cm, so the spread was an artefact of the superseded
numbers rather than a property of the room. The full 1.5 cm gate is available.
Recorded rather than deleted because the reasoning still applies to any room
whose ceiling genuinely is not flat, and we should check for it per room.

## Ground-truth uncertainty — **measured 2026-08-31**

One wall and one opening measured three times each, tape fully retracted and
re-placed between readings.

| Quantity | Readings (cm) | sd | Gate | sd ÷ gate | Verdict |
|---|---|---|---|---|---|
| Wall length | 507.0, 510.1, 508.2 | **1.56** | 40 cm (±8% of 5 m) | 0.04 | usable |
| Opening width | 90.0, 88.2, 88.4 | **0.99** | 2 cm | 0.50 | **marginal** |
| Opening height | 185.0, 190.0, 190.0 | **2.89** | 2 cm | 1.44 | unmeasurable |
| Ceiling height | 330.0, 302.0, 315.0 | **14.01** | 1.5 cm | **9.3** | **unmeasurable** |

### What each row permits

**Wall length: sound.** Tape noise is 4% of the ±8% gate, so a pipeline error at
that scale is genuinely distinguishable from the key's own noise. Every
wall-length figure in the benchmark report stands.

**Opening width: marginal.** Tape noise is half the 2 cm gate. A pipeline
producing exactly 2 cm of error could not be reliably told from a pass. Moot
today — there is no opening detector — but any future opening result needs a
better key.

**Ceiling height: the gate cannot be verified by tape at all.** A spread of
28 cm against a 1.5 cm gate makes the ground truth **9.3 times coarser than the
tolerance it would judge.** No ceiling result of any accuracy can be validated
against this key.

That is a finding about method, not only about us. The brief permits "laser or
tape ground truth", and a tape reading to a 3.3 m ceiling — arm extended,
overhead, reading at an angle — cannot resolve 1.5 cm. **Laser measurement is
effectively mandatory for the ceiling gate**, whatever the brief allows.

### Two recorded values sit outside their own repeat range

| Quantity | Recorded | Repeat range | |
|---|---|---|---|
| Wall A length | 505.7 | 507.0 – 510.1 | below every repeat |
| Door width | 85.5 | 88.2 – 90.0 | 2.7 cm below every repeat |

Half the checked quantities fall outside the range of their own repeats, so the
original single readings carry a **bias** on top of random spread. Recorded
values are kept as the answer key — they were taken systematically across all
walls in one session — but they are now quoted with uncertainty rather than as
exact figures, and this is why.

### What changes in the benchmark report

Errors are now **measured**, not merely observed, for wall lengths. The ceiling
rows should be read as unverifiable rather than as failures: our −12.0% ceiling
error is real in direction, but the key cannot resolve the gate it is being
scored against.

## Video tier: sharpest-frame selection — **tried and rejected**

**Hypothesis.** The video tier regressed when wall detection moved to floor-plane
line fitting (38.3% median wall error against the photo tier's 26.2%). The
diagnosis was motion blur: a smeared edge in a walking capture is elongated and
straight, so it passes a straightness test and is fitted as a wall. The remedy
would be to select the sharpest frame in a window around each wanted timestamp
rather than the frame at that instant.

**Result: worse.** Median wall error **38.3% → 50.3%**.

**Why.** Variance-of-Laplacian, the standard sharpness proxy, measures
high-frequency content — which is **texture**, not geometric usefulness. A crisp
close-up of a patterned bedspread scores far above a slightly soft view down a
hallway. Selecting on it therefore prefers frames full of clutter and short of
room structure, which is the opposite of what the geometry stage needs.

**Reverted**, with the reasoning left in `pipeline/cozmo/video/frames.py` beside
the constant it would have used. A frame score that would actually help must
reward *long straight edges at room scale* rather than high-frequency detail —
a different metric, not a threshold on this one.

**A real bug was found while testing it**, and kept: opening height could come
out **negative** when a jamb's top fell below the horizon, which is not a short
doorway but a jamb whose top was never in frame. It reached `Measurement` as a
negative length, whose interval cannot contain its own value, and crashed the
run. Negative physical quantities now raise at construction with a message
saying they must be rejected where they arise rather than clamped, and the
opening detector drops an unmeasurable height while keeping the usable width.

## Assigning openings to named walls — **attempted, structurally blocked**

The output contract wants each opening on a wall. Ours report
`wall_id: "unassigned"`, and an attempt to resolve that found the obstacle is
structural rather than a matter of effort.

**What is recoverable from one view.** A rectangular room's four walls form two
pairs, and a single image can tell a wall the camera *faces* from one *beside*
it: the first runs across the view, the second runs away from it.

**Why it does not help.** Measured across the whole-floor capture, the
classification returns **facing for 8 of 9** detected openings. An opening is
found from its two vertical jambs, and both are only visible when the camera
roughly faces that wall — edge-on, a doorway is a line rather than a pair of
jambs. So "facing" is a precondition of *detecting* an opening at all, not a
property that separates one wall from another.

**What would be needed**, neither of which exists at this tier:

1. A coordinate frame shared between views. Naming a wall "A" rather than "C"
   requires knowing that two photos looked at the same wall, and the photo tier
   has no poses and no registration between views.
2. A room model richer than a rectangle. The Hall is stepped with a recess; there
   is no true "wall C" in our output for an opening to be assigned to.

This is also why room stitching was not attempted: adjacency needs openings tied
to named walls, and that is upstream of everything the stitch would do.

## Aggregating across views — measured, and a real conflict

Each room is seen several times and the per-view estimates disagree. How they are
combined was tested rather than assumed, across all eight rooms:

| Aggregation | Size correlation | Footprint vs ~67 m² | Median wall error |
|---|---|---|---|
| **median (kept)** | +0.50 | **85.5 m² (+27%)** | 27.3% |
| 75th percentile | **+0.70** | 104.4 m² (+55%) | **24.0%** |
| 90th percentile | +0.64 | 134.0 m² (+100%) | — |
| max | +0.69 | 251.2 m² (+274%) | — |

**The hypothesis behind the upper percentiles was right.** A view can never see
*more* wall than exists, only less, so every per-view estimate is biased low by
partial visibility and an upper percentile should recover more of the true
extent. Correlation confirms it: +0.50 → +0.70.

**But upper percentiles carry their own bias.** Taking the top of several noisy
estimates selects for the noise as well as the signal, and the footprint doubles.

**The conflict is genuine and neither option resolves it.** The 75th percentile
is better on size correlation and marginally better on wall error; the median is
far better on footprint. No option passes any gate, so the tie-break is which
estimator is more honest about itself — and the median is unbiased by
construction, while the 75th percentile is knowingly biased high. Choosing a
known-biased estimator because it scores better on two of three measures would be
tuning to the scoreboard.

**Recorded because it points at the real fix.** The right answer is neither
percentile: it is to know *how much* of a wall each view saw, and weight
accordingly. A view seeing a wall's full run should count for more than one
seeing a corner of it. That needs the fitted line's endpoints checked against the
image border to tell a wall that ends from a wall that leaves the frame — which
is a modest change, and the first thing to try next.

## Known capture-side issues

- A capture saved with zero photos still writes a manifest and survives the
  launch purge, which only removes manifest-less directories
  (`capture_20260830_172252_photo` is one). The pipeline must reject an empty
  capture with a clear message rather than producing an empty plan.
- `ambient_intensity` reads 0 on the first frame of a session; ARKit's light
  estimate is not ready yet. Relevant to the low-light failure mode, where that
  field is the trigger.
