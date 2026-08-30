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

## Ground-truth uncertainty — **deliberately unquantified**

Tape uncertainty has not been measured: the repeat-three-times exercise was
deferred on 2026-08-31. The consequence is precise and should be stated in the
benchmark report rather than left implicit.

A single-pass tape run over a 5 m wall carries sag, corner-placement and reading
error. We do not know its spread, so we cannot claim a pipeline error smaller
than that spread has been *measured* — only that it was observed. Against a 2 cm
opening gate and a 1.5 cm ceiling gate, plausible tape spread is the same order
as the tolerance itself.

What this permits and forbids:

- **Permitted:** reporting pipeline-versus-ground-truth differences as observed
  numbers, and comparing tiers against each other, since all share one key.
- **Forbidden:** quoting a ground-truth interval, or claiming a sub-centimetre
  result is distinguishable from the key's own noise.

Cost to close: measuring one wall and one opening three times each.

## Known capture-side issues

- A capture saved with zero photos still writes a manifest and survives the
  launch purge, which only removes manifest-less directories
  (`capture_20260830_172252_photo` is one). The pipeline must reject an empty
  capture with a clear message rather than producing an empty plan.
- `ambient_intensity` reads 0 on the first frame of a session; ARKit's light
  estimate is not ready yet. Relevant to the low-light failure mode, where that
  field is the trigger.
