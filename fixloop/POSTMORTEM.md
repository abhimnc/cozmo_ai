# Fix loop: post-mortem

Predictions in `DECLARATION.md`, committed before the fix. Both runs are
regenerable from raw input:

```
cozmo run benchmark/raw/capture_20260831_031153_photo    # photo tier
cozmo run benchmark/raw/capture_20260831_033226_video    # video tier
cozmo score out/<capture_id>/plan.json
```

`fixloop/before/` and `fixloop/after/` hold the plans, renders and score output
from each side.

## Result

### Photo tier — wall-length absolute error

| Room / wall | Before | After |
|---|---|---|
| living_room long | 30.3% | **20.4%** |
| living_room short | 35.6% | **16.7%** |
| hall long | 76.9% | **46.2%** |
| hall short | 192.8% | **65.2%** |
| **median** | **56.2%** | **33.3%** |

**−41% relative.** The worst single number fell from +192.8% to +65.2%.

### Video tier — not predicted, reported for completeness

| Room / wall | Before | After |
|---|---|---|
| hall short | 48.8% | **4.5%** |
| hall long | 55.6% | 58.5% |
| living_room short | 125.0% | **10.1%** |
| living_room long | 160.8% | **44.4%** |
| **median** | **90.3%** | **27.2%** |

**−70% relative.** Two dimensions came inside 11%, and the Hall's short wall at
4.5% would clear the photo tier's ±8% gate — though the video tier's gate is
±3%, so it still fails.

## Predictions against outcomes

| # | Predicted | Actual | |
|---|---|---|---|
| 1 | median absolute error below 30% | **33.3%** | **missed, narrowly** |
| 2 | at least 1 of 4 dimensions inside ±8% | **0 of 4** | **missed** |
| 3 | no estimate over 11 m | max **8.11 m** | met |
| 4 | interval coverage no worse than 5 of 6 | **5 of 6** | met |

**Two of four met.** The direction and the mechanism were right; the magnitude
was optimistic.

## Why it fell short of the gate

The declaration named this risk in advance and it is what happened: the fix
attacks the *divergence*, not the *detection*.

Floor distance goes as `h / sin(depression)`, and admitting rays near the
horizon let noise set the answer. Bounding the depression removed that, and the
implausible estimates went with it — nothing now exceeds 8.11 m against a
previous 28.15 m, and every room is a physically possible size.

What remains is that the floor boundary is found as the lowest strong edge per
column, and in these rooms that is frequently the base of a bed, a cupboard or a
mosquito net rather than the wall. Those edges are *nearer* than the wall, which
is why the residual error is now mostly **negative** where it was previously
positive: living_room long −20.4%, hall long −46.2%. The estimator has stopped
overshooting into nowhere and started undershooting onto furniture. That is a
different, more tractable problem, and it needs a real floor-region segmenter
rather than an edge heuristic.

The Hall's short wall (+65.2%) is the exception and has its own cause: the Hall
is 2.6 m wide, so its side walls are very close and steeply depressed, and the
75th-percentile depth reaches past them down the corridor's length.

## A bug found while shipping the fix, and disclosed

The declared change — raising the minimum depression from 3° to 8° — **would
have done nothing on its own.** The test compared the ray's `y` component
against `sin(θ)` without normalising the ray. `d` is `[x−cx, y−cy, f]`, whose
magnitude is of order the focal length in pixels, so the comparison was between
a number near 1000 and one near 0.14, and every ray passed. The depression floor
had been inert since it was written, including at 3°.

So the shipped change is really two: normalising the ray so the threshold means
what it says, and then setting it to 8°. The measured improvement is the two
together, and it would be dishonest to attribute it to the threshold alone.

## What this says about the gate

Neither tier passes, and no amount of tuning these two constants will get there:
±8% on a 5 m wall is 40 cm, and the floor-boundary detection is wrong by more
than that whenever furniture sits against a wall. The next fix is a floor-region
segmenter that finds where the floor plane actually ends, not where the lowest
edge happens to be.

Interval coverage held at 5 of 6 through the change, which was prediction 4 and
mattered most: accuracy improved without the intervals being quietly narrowed
until they stopped covering the truth.
