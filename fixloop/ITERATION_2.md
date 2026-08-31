# Fix loop, iteration 2: floor-plane wall detection

A second shipped change, after the first (`DECLARATION.md`, `POSTMORTEM.md`)
moved the photo tier 41% but left the *cause* untouched. The first fix bounded a
divergence; this one attacks the detection that the post-mortem named as the
remaining problem.

## What changed

The wall/floor junction was found as the lowest strong edge in each image
column. In a furnished room that is frequently a bed base or a cupboard.

The new method uses a property furniture does not have. Back-project every
floor-candidate edge point onto the floor plane and look from above: the base of
a planar wall becomes a **straight line several metres long**, because the wall
is straight and vertical. Furniture projects to short segments and scatter.
Straightness and length in the bird's-eye view separate them, and neither is
available in the image alone. See `pipeline/cozmo/photo/floorplane.py`.

Also changed: several candidate points are kept per column instead of only the
lowest, because the true wall base is often *above* furniture in the same column
and a lowest-only rule can never recover it however it is filtered afterwards.

## Result — a genuine trade-off, not a clean win

### Photo tier: better, and the project's first gate pass

| Room / wall | Truth | Before | After | |
|---|---|---|---|---|
| living_room short | 3.330 m | 3.886 (+16.7%) | **3.317 (−0.4%)** | **PASS** |
| living_room long | 5.017 m | 3.994 (−20.4%) | **4.581 (−8.7%)** | |
| hall short | 2.095 m | 3.460 (+65.2%) | 3.818 (+82.3%) | worse |
| hall long | 7.079 m | 3.807 (−46.2%) | 3.979 (−43.8%) | |

Median absolute error **33.3% → 26.2%**. Accuracy **0/6 → 1/6**. Calibration
held at 5/6.

### Video tier: worse

Median absolute error **27.2% → 39.0%**, calibration 5/6 → 4/6.

## Why the video tier regressed, and what was ruled out

Two hypotheses were tested and both rejected:

1. *The minimum wall-run length is wrong for lower-resolution frames.* Swept
   0.6–1.6 m; video stayed at 39–41% throughout. Rejected.
2. *Video frames yield too few floor points to find a line.* Measured: 1590
   candidates per video frame against 1821 per photo, and identical segment
   counts. Rejected.

What remains is that video frames yield **wrong** lines rather than fewer.
Motion blur during a walking capture produces elongated smears that pass a
straightness test, and a smear on a rug is indistinguishable from a wall base
once projected. That is a real property of the input, not a threshold to tune,
and fixing it needs a blur or motion gate on frame selection — not attempted
here.

## Why it ships anyway

The brief calls the photo tier the floor: *"any picture in, results out."* It is
the hardest tier and the one every other requirement is anchored to, and it now
produces the project's first passing dimension. The video regression is real,
measured, and reported here and in the benchmark report rather than buried.

A tier-conditional switch was considered and rejected: sharing one estimator
across tiers is what makes the tier comparison mean anything, and branching on
the tier label would turn that comparison into a comparison of two
implementations. Branching on a *measured input property* would have been
legitimate, but the two properties tested do not separate the cases.
