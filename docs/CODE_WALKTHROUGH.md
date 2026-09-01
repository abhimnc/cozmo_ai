# Code walkthrough

How a folder of photographs becomes a floor plan, in the order the code runs.

Written for someone joining the project, or reviewing it. Each section says what
runs, why it is written that way, and what it produces. Real values throughout,
taken from `capture_20260831_031153_photo` — 61 photos, 8 rooms.

**Contents**

1. [Entry point](#1-entry-point)
2. [Loading a capture](#2-loading-a-capture)
3. [Input validation](#3-input-validation)
4. [Per-view analysis](#4-per-view-analysis) — the expensive stage
5. [Aggregation](#5-aggregation)
6. [Adjacency](#6-adjacency)
7. [Plan assembly](#7-plan-assembly)
8. [Output](#8-output)
9. [Data structures](#9-data-structures)
10. [Design principles](#10-design-principles)

---

## 1. Entry point

`pyproject.toml` → `cozmo.cli:main`

```python
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cozmo")
    sub = parser.add_subparsers(dest="command", required=True)
    ...
    args = parser.parse_args(argv)
    return args.func(args)
```

| Choice | Reason |
|---|---|
| `argv=None` default | Tests call `main(["run", path])` without spawning a process |
| `required=True` | Bare `cozmo` prints help rather than doing something surprising |
| `set_defaults(func=…)` | No `if command == …` chain; adding a command never edits `main` |
| Returns `int` | Becomes the shell exit code: `0` ok, `2` bad input, `3` unimplemented |

### Commands

| Command | Purpose |
|---|---|
| `run <bundle>` | Produce `plan.json` + `plan.svg` |
| `score <plan>` | Compare a plan against tape ground truth |
| `inspect <bundle> --prove-budget` | Show what this tier may read, and demonstrate refusals |
| `calibrate <bundle>` | Cross-check EXIF focal length against image geometry |
| `demo-damage` | Run the damage rules on a supplied damage set |

`inspect --prove-budget` and `demo-damage` exist because two claims in this
project need demonstrating rather than asserting: that the tier separation is
real, and that the damage stages are implemented but unfed.

---

## 2. Loading a capture

`cli.cmd_run` → `bundle.CaptureBundle.load`

```python
manifest = json.loads((root / "manifest.json").read_text())
budget = SensorBudget.from_manifest(manifest)
```

The capture declares, in its own manifest, which paths its tier may read. The
budget is built here — at load, from the data — so no caller can widen it.

```python
if not tier or not patterns:
    raise ValueError("Capture manifest declares no tier or no sensor budget. "
                     "Refusing to guess: a bundle that does not say what it is "
                     "cannot be scored.")
```

A missing tier could be inferred from the directory name. Guessing wrong would
score the photo tier against video gates, so it refuses instead.

### The access chokepoint

```python
def open(self, relpath: str, mode: str = "rb"):
    if relpath not in _ALWAYS_READABLE:
        self.budget.require(relpath)
    target = (self.root / relpath).resolve()
    if not target.is_relative_to(self.root):
        raise BudgetViolation(relpath, self.tier, self.budget.patterns)
    return open(target, mode)
```

Two guards: budget membership, then path containment after `resolve()` so
`../../etc/passwd` cannot escape the capture root.

**There is deliberately no method taking a raw filesystem path.** That absence
is the design — a convenience accessor would eventually be used, and the gate
bypassed without anyone noticing.

### Glob semantics

```python
if pattern[i:i+2] == "**":  out.append(".*")      # crosses separators
elif ch == "*":             out.append("[^/]*")   # does not
```

Hand-written rather than `fnmatch`, which conflates the two. Under `fnmatch`,
`photos/*` would match `photos/01_hall/0001.jpg`, making the budget looser than
it reads.

**Produces:** a `CaptureBundle` with 63 readable files and 2 withheld
(`_reference/poses.jsonl`, `_reference/planes.json`).

---

## 3. Input validation

```python
problems = bundle.validate_inputs()
if problems and bundle.tier == "photo":
    return 2
```

Three checks costing microseconds, before a stage costing ten seconds:

- Are there any rooms?
- Are there any photos in budget?
- Does any room have fewer than two?

```python
elif n < 2:
    problems.append(f"Room {room.name!r} has {n} photo. The brief's floor is 2 "
                    "per room, and a single view cannot resolve scale or shape.")
```

Messages state the rule *and* the reason. The reader is an operator deciding
whether to re-shoot, not a developer reading a stack trace.

---

## 4. Per-view analysis

`cli._views_for` → `photo.room.analyse`, once per image. **~10 s for 61 images.**

### The single tier branch

```python
if bundle.tier == "photo":   paths = bundle.photos_by_room()
elif bundle.tier == "video": paths = video.frames.frames_by_room(bundle)
elif bundle.tier == "lidar": paths = lidar.frames.frames_by_room(bundle)

out[slug] = [analyse(p) for p in paths]
```

Each branch's entire contract is `dict[room_slug, list[image_path]]`. After
this function the tier is no longer visible to any code.

**Why:** sharing one estimator means a tier comparison measures what the *input*
is worth, rather than which of three implementations received more attention.

### Inside `analyse()`

Eight exits, seven of them refusals. Traced on `01_living_room/0001.jpg`:

| Step | Code | Value |
|---|---|---|
| Read lens | `read_camera(path)` | 4032×3024, focal 3024 px |
| Detect lines | `lines.detect(path)` | 1600×1200 working image, 267 segments |
| Rescale focal | `focal_full * seg.scale` | 3024 × 0.397 = **1200 px** |
| Vertical VP | `_vertical_vanishing_point(seg)` | image (1990, 17613) |
| Gravity rotation | `_gravity_rotation(vp, …)` | tilt 4.0° |
| Horizon | ray per row, first pointing down | row 516 of 1200 |
| Candidates | `floorplane.candidate_points` | 2020 edge pixels |
| Project | `floorplane.project_to_floor` | 1957 survive the 8° cut |
| Fit lines | `floorplane.find_floor_lines` | 4 lines |
| Choose | `max(strong, key=length_m)` | depth 2.89 m, span 3.32 m |

#### Three details that are easy to get wrong

**Focal length must be rescaled with the image.**

```python
focal = focal_full * seg.scale
```

Focal length is in pixels. The image was downscaled 4032 → 1600. Omitting this
line makes every distance wrong by 2.5×. `Segments` carries `scale` as a field
so the coordinate frame travels with the data rather than being remembered by
callers.

**Homogeneous coordinates handle the parallel case.**

The vertical vanishing point comes out at image y = 17,613 in a 1200-pixel
image. That is correct: a near-level phone makes vertical lines near-parallel,
and near-parallel lines meet far away. With a perfectly level phone they meet at
infinity, which ordinary (x, y) cannot represent and homogeneous coordinates
can. No special case is needed.

**The depression test needs a normalised ray.**

```python
unit = d / np.linalg.norm(d, axis=1, keepdims=True)
d = d[unit[:, 1] > np.sin(np.deg2rad(MIN_DEPRESSION_DEG))]
```

`d` has magnitude of order the focal length (~1200). Comparing `d[:,1]` directly
against `sin(8°) = 0.139` compares 1000 against 0.14 — every ray passes. This
bug shipped and the filter was inert until it was found; see
`fixloop/POSTMORTEM.md`.

#### Why the depression floor exists

Floor distance is `h / sin θ`, which diverges as θ → 0:

| Depression | Distance (h = 1.45 m) |
|---|---|
| 30° | 2.9 m |
| 8° | 10.4 m |
| 3° | 27.7 m |
| 1° | 83 m |

Near the horizon a tenth of a degree of pixel noise moves the answer by tens of
metres. Rays shallower than 8° carry no usable range. Before this limit existed,
one bedroom estimated 28.15 m — pinned at the geometric cap of the then-3°
threshold, measuring the threshold rather than the room.

#### Why the longest line, not the furthest

```python
chosen = max(strong, key=lambda l: l.length_m)
```

The original rule took the most distant line, assuming the far wall is the
furthest thing visible. With an open doorway it is not — the floor continues
through the opening and the furthest line lies in the next room. Small rooms
with open doors failed worst; the bathrooms were over by 4.3×.

Length is a property of the wall; distance is a property of where the operator
stood. Changing this one expression moved room-size correlation from **+0.10 to
+0.50**.

**Produces:** 61 `RoomView` objects — 48 usable, 13 refused with reasons.

---

## 5. Aggregation

`plan.estimate_rooms`. **<0.01 s.**

### Merge repeated rooms

```python
for room in bundle.rooms:
    if room.slug not in seen:
        seen[room.slug] = room.name
```

A hub-and-spoke video walk marks the Hall at every pass. It is one hall.

### Prefer complete observations

```python
whole  = [v for v in good if not v.truncated]
source = whole or good
```

A wall that ran out of the image frame was measured to where the *view* stopped,
not where the wall stopped — its length is a lower bound. `whole or good` falls
back when no view saw a complete wall, and records that it did:

```python
basis = (f"{len(whole)} of {len(good)} views saw a whole wall"
         if whole else
         f"no view saw a whole wall; median of {len(good)} truncated views")
```

That string reaches the output, so a poor number carries its explanation.

### Compute the interval

```python
half = max(1.96 * sd, value * floor_rel)
```

**Predictive spread, not standard error of the mean.** `1.96·sd/√n` assumes every
view measured the same quantity; views of a non-rectangular room measure
different walls. Dividing by √n made the interval *shrink* as views disagreed —
treating contradiction as evidence of certainty. Removing it took photo-tier
coverage from 5/6 to 6/6.

**Produces:**

| Room | Estimate | Interval | Views |
|---|---|---|---|
| Living room | 4.33 × 3.76 m | ±96% | 7 |
| Hall | 5.12 × 4.24 m | ±99% | 8 |
| Bed room 1 | 3.70 × 4.76 m | ±156% | 3 |

The widest interval belongs to the room with the fewest usable views. Nobody
chose that; it falls out of the spread.

---

## 6. Adjacency

`photo.adjacency.find_links`, photo tier only. **~7 s for 28 room pairs.**

At the photo tier there are no poses and no frame ordering, so nothing in the
input states which rooms adjoin. Open archways make it recoverable: a photo
taken in one room and pointed at an archway contains part of the next.

```python
good = [m for m, n in raw if m.distance < RATIO * n.distance]   # Lowe's ratio, 0.75
_, mask = cv2.findFundamentalMat(src, dst, cv2.FM_RANSAC, 3.0, 0.99)
```

A **fundamental matrix**, not a homography: the two photographs are taken from
different positions, so the scene is not a plane and a homography would reject
correct matches.

### Threshold selection

Measured on the whole-floor capture:

| `MIN_INLIERS` | Links | Correct | False | Precision | Recall |
|---|---|---|---|---|---|
| 12 | 15 | 6 | 9 | 40% | 75% |
| 15 | 7 | 5 | 2 | 71% | 62% |
| **20** | **5** | **4** | **1** | **80%** | **50%** |
| 60 | 3 | 3 | 0 | 100% | 38% |

20 sits deliberately above the F1 optimum at 15: on a floor plan a false
adjacency places a room where it is not, while a missing one only omits a link.

### Known failure

`bathroom_1 ↔ bathroom_2` matches at 51 inliers and shares no wall. The two
share **tiling**. Image matching conflates *adjacent* with *looks alike*, and any
property with repeated finishes will produce these.

**Complexity:** `O(rooms² × images²)`. Acceptable at 8 rooms; would dominate at
30, where a coarse pre-filter on global descriptors would be needed.

---

## 7. Plan assembly

`plan.build_plan`. **<0.05 s.**

### Layout

```python
hub_id = max(degree, key=lambda k: (degree[k], area))
for step in range(400):
    pull linked pairs together   × 0.05
    push overlapping pairs apart × 0.15
```

Anchored on the highest-degree room — the Hall — because error then stays local:
a room misplaced against the hub is wrong on its own, while a chain of rooms
placed against each other compounds.

Push outweighs pull 3:1 because the gate **forbids** overlap while merely
**preferring** neighbours to touch. Asymmetric requirements, asymmetric weights.

**Positions are solved, not measured.** The plan records
`position_method: "topological_layout"` and the render states it on its face.

### Damage

```python
regions = []                                  # no detector exists
concealed = evaluate_rules(regions, context)
scope = build_scope(regions, concealed)
```

Empty in, empty out. The output reports zero damage because **nothing was
observed**, not because the stages are missing — `cozmo demo-damage` runs the
same functions on a supplied damage set and produces 6 flags and 10 scope items.

### Absence stated explicitly

```python
"drift": {"method": "none", "applied": False,
          "notes": "Adjacency is recovered but room placement is not…"}
```

An omitted field and an honest `"none"` read identically. The note distinguishes
*the stage is absent* from *poses were used uncorrected*, which are graded very
differently.

---

## 8. Output

```python
json_path, svg_path = write_outputs(plan, out_dir)
out_dir = args.output or (Path("out") / bundle.capture_id)
```

Defaulting to the capture id means two runs never overwrite each other.

The renderer reads `plan.json` and nothing else — no access to the bundle, the
geometry, or the estimator. It therefore cannot draw anything the JSON does not
contain. Rooms with no recovered adjacency render dashed because that fact is in
the data.

### Console output

```python
print(f"  {est.name:<16} {est.views_used}/{est.views_total} views   "
      f"{est.depth_m.value:.2f} x {est.width_m.value:.2f} m")
```

Per-room view counts are printed so an operator sees `3/6 views` and knows that
room is weakly supported, without opening the JSON.

---

## 9. Data structures

| Type | Module | Purpose | Invariant |
|---|---|---|---|
| `SensorBudget` | `budget` | Tier + allowed globs | `frozen`, tuple — cannot widen itself |
| `CaptureBundle` | `bundle` | Root + manifest + rooms | All reads route through `.open()` |
| `Segments` | `photo/lines` | Line segments + scale | Coordinate frame travels with data |
| `FloorLine` | `photo/floorplane` | A run on the floor plane | Retains `inliers` as evidence |
| `RoomView` | `photo/room` | One image's verdict | `ok=False` always carries a reason |
| `Opening` | `photo/openings` | A door or archway | Never claims to be a window |
| `Measurement` | `measure` | A physical quantity | Interval mandatory and must contain the value |
| `RoomEstimate` | `plan` | Merged views for one room | Separates used from rejected |
| `PlacedRoom` | `layout` | Size + solved position | Position marked inferred |

### `Measurement` in full

```python
@dataclass(frozen=True)
class Measurement:
    value: float
    ci_low: float
    ci_high: float
    unit: str
    method: str

    def __post_init__(self):
        if self.unit in ("m", "m2", "cm"):
            if self.value < 0:
                raise ValueError("A negative length is a failed fit upstream, "
                                 "not a measurement — reject it where it arises.")
            if self.ci_low < 0:
                object.__setattr__(self, "ci_low", 0.0)
        if not (self.ci_low <= self.value <= self.ci_high):
            raise ValueError("interval does not contain its value")
```

No constructor takes a bare number. `method` is mandatory, so every interval in
the output traces to what produced it. "Every measurement carries an interval"
is a type error rather than a review checklist item.

---

## 10. Design principles

### Enforcement at a boundary, not discipline everywhere

The threat is not malice but entropy: a debug line that reads poses at the photo
tier, survives review, and silently converts the hardest tier into the easiest.
Nothing in the output would look wrong. A boundary that raises turns an
invisible failure into a stack trace.

### Failures are data, not exceptions

One unusable photograph must not lose the other 60. `analyse()` returns
`RoomView(ok=False, reason=…)` rather than raising, and the reason survives into
the output. 13 of 61 images are refused on the reference capture.

### Uncertainty is computed, not chosen

Intervals derive from disagreement between views. The room with three usable
views has the widest interval. No constant in the codebase sets it.

### Constants are justified by geometry, measurement, or convention

| Constant | Value | Basis |
|---|---|---|
| `MIN_DEPRESSION_DEG` | 8.0 | Geometry — bounds range at 10.4 m |
| `MIN_WALL_RUN_M` | 1.2 | Separates a wall from furniture |
| `MIN_INLIERS` | 20 | Measured precision/recall sweep |
| `DEPTH_REL_INTERVAL` | 0.30 | Measured against tape ground truth |
| `CAMERA_HEIGHT_M` | 1.45 | Prior, labelled as a prior |
| `OVERCUT_ALLOWANCE` | 0.15 | Trade convention, labelled as such |

None is justified by "it scored better". That would be fitting the pipeline to
eight rooms in one property.

### Known limitation, and the next change

Room dimensions are a distance and an extent taken from whichever wall a view
happened to fit. The Hall's eight views report depths of 4.22, 2.52, 1.36 and
6.94 m — these are not noisy readings of one wall but measurements of *different
walls*, and their median describes nothing that exists.

Identifying which physical wall a measurement belongs to is the single blocker
behind three separate failures: wall assignment for openings, room placement
from measured pose, and dimension averaging. It fits in the reasoning layer,
between `room.analyse()` and `plan.estimate_rooms()`, with no change to access,
primitives or assembly.
