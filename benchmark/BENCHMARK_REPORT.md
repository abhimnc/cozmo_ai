# Benchmark report

All numbers regenerable:

```
cozmo run   benchmark/raw/<capture_id>
cozmo score out/<capture_id>/plan.json
```

Ground truth: tape, Living room and Hall (`ground_truth/`). Its own uncertainty
is **unquantified** — the repeat-three-times exercise was not done — so every
error below is *observed* rather than *measured*. See `docs/ERROR_BUDGET.md`.

## Gates at each tier

### Photo tier — `capture_20260831_031153_photo`, 8 rooms, 61 photos

| Room | Quantity | Truth | Estimate | Error | Interval covers truth | Gate ±8% |
|---|---|---|---|---|---|---|
| living_room | long wall | 5.017 | 3.994 | −20.4% | yes | FAIL |
| living_room | short wall | 3.330 | 3.886 | +16.7% | yes | FAIL |
| living_room | ceiling | 3.294 | 2.900 | −12.0% | yes | FAIL |
| hall | long wall | 7.079 | 3.807 | −46.2% | **no** | FAIL |
| hall | short wall | 2.095 | 3.460 | +65.2% | yes | FAIL |
| hall | ceiling | 3.294 | 2.900 | −12.0% | yes | FAIL |

**Accuracy 0/6. Calibration 5/6.** Median wall error 33.3%.

### Video tier — `capture_20260831_033226_video`, 339 s, 14 room markers

| Room | Quantity | Truth | Estimate | Error | Gate ±3% |
|---|---|---|---|---|---|
| hall | short wall | 2.095 | 2.190 | **+4.5%** | FAIL |
| hall | long wall | 7.079 | 2.936 | −58.5% | FAIL |
| living_room | short wall | 3.330 | 3.667 | **+10.1%** | FAIL |
| living_room | long wall | 5.017 | 2.789 | −44.4% | FAIL |

**Accuracy 0/6. Calibration 5/6.** Median wall error 27.2% — better than the
photo tier, as the tier ladder predicts, but nowhere near a ±3% gate.

### LiDAR tier

**Not run.** No LiDAR-capable device was available to this project. The code
path exists and feeds the same estimator, but no accuracy claim is made for a
tier that has never seen real data.

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

**0 of 8 within 1 cm or 0.5%.** Best case 7 cm; worst 2.69 m.

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
| photo | 031153 | 8 | 61 photos, 12 MP | **7.6 s** |
| video | 033226 | 9 | 339 s clip, 486 MB | **4.9 s** |

Both on an M4 MacBook Air, cold, single command, no cache.

## Honest summary

Nothing passes a gate. What does work: the pipeline runs end to end on both
available tiers in seconds, produces schema-valid output, and its intervals
cover the truth 5 times in 6 — so it is wrong, but it is not *confidently*
wrong. The fix loop moved the photo tier 41% and the video tier 70% and is
documented in `fixloop/`.

What is missing is not tuning but stages: no opening detection, no room
placement, no damage analysis. Those are absent by time, not by oversight, and
are marked NOT DONE in `COMPLIANCE.md`.
