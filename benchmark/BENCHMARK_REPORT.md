# Benchmark report

All numbers regenerable:

```
cozmo run   benchmark/raw/<capture_id>
cozmo score out/<capture_id>/plan.json
```

Ground truth: tape, Living room and Hall (`ground_truth/`). Its uncertainty is
now **measured** by repeat readings:

| Quantity | Tape sd | Gate | Verdict |
|---|---|---|---|
| Wall length | 1.56 cm | 40 cm | usable — errors below are measured |
| Opening width | 0.99 cm | 2 cm | marginal |
| **Ceiling height** | **14.01 cm** | **1.5 cm** | **unmeasurable — 9.3× the gate** |

**The ceiling rows below cannot be verified.** The key is 9.3 times coarser than
the tolerance it judges, so a ceiling result of any accuracy is indistinguishable
from tape noise. Read those rows as unverifiable, not as failures. Wall-length
rows stand. See `docs/ERROR_BUDGET.md`.

## Gates at each tier

### Photo tier — `capture_20260831_031153_photo`, 8 rooms, 61 photos

| Room | Quantity | Truth | Estimate | Error | Interval covers truth | Gate ±8% |
|---|---|---|---|---|---|---|
| living_room | long wall | 5.017 | 4.581 | −8.7% | yes | FAIL |
| living_room | short wall | 3.330 | 3.317 | **−0.4%** | yes | **PASS** |
| living_room | ceiling | 3.294 | 2.900 | −12.0% | yes | FAIL |
| hall | long wall | 7.079 | 3.979 | −43.8% | **no** | FAIL |
| hall | short wall | 2.095 | 3.818 | +82.3% | yes | FAIL |
| hall | ceiling | 3.294 | 2.900 | −12.0% | yes | FAIL |

**Accuracy 1/6. Calibration 5/6.** Median wall error **26.2%**.

The living room's short wall at −0.4% is the project's only passing dimension.
The Hall fails worst, and it is the room the rectangle model fits least — stepped
wall, 1.75 m recess — so the failure is where the model is least applicable.

### Video tier — `capture_20260831_033226_video`, 339 s, 14 room markers

| Room | Quantity | Truth | Estimate | Error | Gate ±3% |
|---|---|---|---|---|---|
| hall | short wall | 2.095 | 1.745 | −16.7% | FAIL |
| hall | long wall | 7.079 | 1.356 | −80.8% | FAIL |
| living_room | short wall | 3.330 | 2.529 | −24.1% | FAIL |
| living_room | long wall | 5.017 | 2.382 | −52.5% | FAIL |

**Accuracy 0/6. Calibration 4/6.** Median wall error **38.3%**.

**This tier regressed.** Before the second fix it was 27.2% and 5/6 calibration —
better than the photo tier, as the tier ladder predicts. The floor-plane wall
detector that helped the photo tier hurts this one, because motion blur in a
walking capture produces elongated smears that pass a straightness test. Two
competing explanations were tested and rejected; see `fixloop/ITERATION_2.md`.
The regression is reported rather than reverted, with the reasoning there.

### LiDAR tier

**Runs, on synthetic data only.** No LiDAR-capable device was available. The path
is exercised against a bundle built by `scripts/make_synthetic_lidar.py`: it
loads, enforces the tier's sensor budget, and emits a schema-valid plan across
8 rooms in 5.6 s.

**No accuracy is reported and none should be inferred.** The depth maps are
constructed, so a number from that run would measure the generator, not the
pipeline. It exists so the tier does not crash cold at the walk-in test, where
the graders choose the tier on the day.

## Repeatability — **unrepeatable, not repeatable-but-biased**

Two photo-tier captures of the same four rooms, walked differently.

| Room | Quantity | Capture A | Capture B | Difference |
|---|---|---|---|---|
| living_room | long wall | 3.99 | 3.08 | 0.92 m |
| living_room | short wall | 3.89 | 3.82 | **0.07 m** |
| hall | long wall | 3.81 | 4.31 | 0.51 m |
| hall | short wall | 3.46 | 4.64 | 1.18 m |
| kitchen | long wall | 2.46 | 3.89 | 1.44 m |
| kitchen | short wall | 2.68 | 3.74 | 1.06 m |
| bedroom_3 | long wall | 6.73 | 8.30 | 1.57 m |
| bedroom_3 | short wall | 2.87 | 5.56 | 2.69 m |

**0 of 8 within 1 cm or 0.5%.** After the second fix, best case 43 cm and worst
3.36 m — the spread widened even as accuracy improved, because the floor-plane
detector's choice of which line is the far wall is itself sensitive to viewpoint.

The brief asks which failure this is, and the answer is **unrepeatable**. A
repeatable-but-biased system would give the same wrong answer twice; this gives
different answers to the same room. The cause is upstream of any bias: room
depth is taken from a percentile of back-projected floor-boundary points, and
which points are found depends on where the operator stood and what furniture
was in frame. Different walk, different boundary, different answer.

That also means the accuracy figures above should be read as one sample of a
wide distribution, not as the system's error.

## Head-to-head

**43% (3 of 7 shared dimensions), against a ≥70% gate. Failed.**
Full table and analysis in `head_to_head/README.md`.

## Timing

| Tier | Capture | Rooms | Inputs | Runtime |
|---|---|---|---|---|
| photo | 031153 | 8 | 61 photos, 12 MP | **10.5 s** |
| video | 033226 | 9 | 339 s clip, 486 MB | **7.0 s** |
| lidar | synthetic | 8 | 32 frames + depth | **5.6 s** |

All on an M4 MacBook Air, cold, single command, no cache. Photo-tier runtime rose
from 7.6 s with the floor-plane detector, which is the cost of projecting and
fitting rather than reading one edge per column.

## Honest summary

One dimension passes a gate: the living room's short wall, −0.4%. Nothing else
does.

What works: all three tiers run end to end in seconds and emit schema-valid
output, and intervals cover the truth 5 times in 6 at the photo tier — so the
pipeline is wrong, but not *confidently* wrong, which is the distinction the
brief scores. Two fixes shipped, both with before/after runs: the first moved the
photo tier 41% and the video tier 70%; the second moved the photo tier a further
21% and produced the first passing dimension, at the cost of a video-tier
regression that is reported rather than reverted.

What is missing is not tuning but stages: no opening detection, no room
placement, no damage analysis. Those are absent by time, not by oversight, and
are marked NOT DONE in `COMPLIANCE.md`.
