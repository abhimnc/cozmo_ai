# Compliance matrix

Requirement → file path → artifact → status. Honest statuses only: **DONE**,
**PARTIAL**, **NOT DONE**. A requirement with no artifact is marked NOT DONE
rather than described as in progress.

Summary: **16 done, 9 partial, 6 not done** of 31 requirements.
All 8 deliverables written; **7 complete, 1 partial**.

## Part 1 — Capture route and tiers

| # | Requirement | Path | Artifact | Status |
|---|---|---|---|---|
| 1.1 | Choose a capture route | `docs/DECISIONS.md` | Route 1 chosen, with reasoning | **DONE** |
| 1.2 | Own iOS capture app | `ios/` | CozmoCapture, builds and runs on device | **DONE** |
| 1.3 | Installable in under 10 min | `scripts/install_on_device.sh` | **Measured: 11 s** cold (DerivedData deleted), M4 MacBook Air, one command. Under 2 min end to end including the one-time certificate trust on the phone. The brief allows "a TestFlight build **or** a dev build"; this is the dev build. TestFlight additionally blocked externally — enrolment Pending at Apple since 31 Aug 10:50 IST | **DONE** |
| 1.4 | Photo tier | `ios/.../CaptureTier.swift` | Implemented, 5 real captures | **DONE** |
| 1.5 | Video tier | `ios/.../VideoRecorder.swift` | Implemented, 339 s / 20,324-frame walkthrough captured | **DONE** |
| 1.6 | LiDAR tier | `pipeline/cozmo/lidar/`, `scripts/make_synthetic_lidar.py` | Runs end to end on a synthetic bundle (4.1 s, schema-valid). **Never run on real LiDAR data** — no LiDAR device available, so no accuracy claim | **PARTIAL** |
| 1.7 | Device matrix | `docs/DEVICE_MATRIX.md` | Tier × hardware, probed at runtime, per-tier accuracy filled from benchmark | **DONE** |

## Part 2 — Output contract

| # | Requirement | Path | Artifact | Status |
|---|---|---|---|---|
| 2.1 | Dimensioned per-room plan: walls | `schema/`, `out/*/plan.json` | 4 walls per room with intervals | **PARTIAL** — rectangle only, ±30% |
| 2.2 | Ceiling height | `out/*/plan.json` | Reported as a **residential prior, not an estimate** | **PARTIAL** |
| 2.3 | Floor area | `out/*/plan.json` | Depth × width, interval propagated | **PARTIAL** |
| 2.4 | Openings | `pipeline/cozmo/photo/openings.py` | Doors and archways detected as jamb pairs standing on a wall line, with metric widths and confidence, emitted in `plan.json`. **Windows not detectable** (no floor contact); widths off −14.8% and +52.7%; **wall assignment attempted and found structurally blocked** at this tier — see `docs/ERROR_BUDGET.md` | **PARTIAL** |
| 2.5 | Stitched multi-room plan, correct adjacency | `photo/adjacency.py`, `layout.py`, `render.py` | **One stitched plan produced**: 8 rooms placed with polygons, adjacency at 80% precision, **zero overlap**, rendered to SVG. Positions are solved from dimensions + adjacency, **not surveyed** — stated in the plan and drawn on the render | **PARTIAL** |
| 2.6 | Per-surface damage regions, class and extent | — | No damage detection | **NOT DONE** |
| 2.7 | Concealed-damage flags with the rule that fired | `pipeline/cozmo/damage/rules.py` | **Rule engine implemented**: 5 rules, each carrying its statement in plain words; every flag names the rule and the regions that satisfied it. Fires 6 flags on a worked damage set (`cozmo demo-damage`). Empty on real captures because **no damage detector exists** | **PARTIAL** |
| 2.8 | Scope line items keyed to surfaces | `pipeline/cozmo/damage/scope.py` | **Generator implemented**: remediation items carry a measured extent plus a labelled trade allowance; investigation items carry **no area**, since concealed damage cannot be quantified before opening up. Every item names what it derives from. 10 items on the worked set | **PARTIAL** |
| 2.9 | Confidence interval on every measurement | `pipeline/cozmo/measure.py` | `Measurement` type cannot be constructed without one; schema enforces it | **DONE** |
| 2.10 | One command per capture | `pipeline/cozmo/cli.py` | `cozmo run <bundle>` → plan.json + plan.svg, ~5 s | **DONE** |
| 2.11 | JSON to a published schema | `schema/cozmo_plan.schema.json` | Validated with `jsonschema` | **DONE** |
| 2.12 | Rendered plan | `pipeline/cozmo/render.py`, `out/*/plan.svg` | SVG with intervals drawn as bands | **DONE** |

## Part 2 — Benchmark set

| # | Requirement | Path | Artifact | Status |
|---|---|---|---|---|
| 2.13 | Multi-room capture, 3+ rooms plus connector | `benchmark/raw/capture_20260831_031153_photo` | 8 rooms, Hall connector, 61 photos | **DONE** |
| 2.14 | Furnished room with staged damage, two classes | `docs/DAMAGE_PLAN.md` | Not staged — the operator declined to tape proxy damage to their walls. Recorded rather than left blank | **NOT DONE** |
| 2.15 | Same rooms at all three tiers | `benchmark/raw/` | Photo and video captured on real hardware; LiDAR exercised synthetically only | **PARTIAL** |
| 2.16 | One room captured twice, same tier | `benchmark/raw/` | Living room in two photo captures | **DONE** |
| 2.17 | Laser or tape ground truth | `benchmark/ground_truth/` | Tape: Living room and Hall complete, **with measured uncertainty** (wall sd 1.56 cm; ceiling sd 14.01 cm, which cannot resolve the 1.5 cm gate) | **PARTIAL** — 2 of 9 rooms |
| 2.18 | Raw sensor data submitted | `benchmark/raw/` | 10 captures incl. 486 MB video; gitignored, supplied separately | **DONE** |

## Part 2 — Gates

| # | Gate | Path | Result | Status |
|---|---|---|---|---|
| 2.19 | Opening widths ≤2 cm on ≥85% | `benchmark/BENCHMARK_REPORT.md` | Now scorable: **2 of 3** doors/archways found in the room with ground truth, 0 of them within 2 cm. One miss plus width errors of −14.8% and +52.7% | **NOT DONE** — measured and reported |
| 2.20 | Ceiling height ≤1.5 cm | `fixloop/after/score_photo.txt` | −12.0%, a prior not an estimate | **NOT DONE** |
| 2.21 | Repeatability within 1 cm / 0.5% | `benchmark/BENCHMARK_REPORT.md` | Table produced: **0 of 8**, and the report states which failure mode it is (unrepeatable, not repeatable-but-biased) | **NOT DONE** — measured and diagnosed |
| 2.22 | Drift accountability + ablation | `out/*/plan.json` | `stitch.drift` states `method: none, applied: false` because no placement stage exists. **Not** "poses used as-is" — the stage is absent, and the field says so | **PARTIAL** |
| 2.23 | Photo-tier whole-property stitch | `out/*/plan.svg` | Per-room photo folders → **one stitched plan**: 8 rooms placed, correct adjacency on 4 of 5 links, **no room overlaps (0.0 m²)**. Footprint **79.5 m² against ~67 m² actual, +19%** — fails the ±8% row | **PARTIAL** — three of four conditions met |
| 2.24 | Photo ±8% / video ±3% wall lengths | `benchmark/BENCHMARK_REPORT.md` | Photo median **20.7%**, video 38.3%, **0 of 6 passing**. A single passing dimension was traded for an eightfold gain in size correlation (+0.10 → **+0.84**) and a footprint improvement from +60% to +19% — the pass was chance under an estimator that barely tracked room size | **NOT DONE** — measured and reported |
| 2.25 | Calibration scored at every tier | `benchmark/BENCHMARK_REPORT.md` | **6 of 6** intervals contain the truth at the photo tier, 4 of 6 at video. Intervals average ±100% of their value, so coverage reflects how little is known rather than good calibration — stated in the report | **DONE** |

## Part 3 — Head-to-head

| # | Requirement | Path | Artifact | Status |
|---|---|---|---|---|
| 3.1 | Compare on 2 rooms vs a consumer app | `benchmark/head_to_head/` | magicplan free tier, Living room + Hall | **DONE** |
| 3.2 | Name app and version, submit export | `benchmark/head_to_head/magicplan_export.pdf` | magicplan (Sensopia) 8-page PDF export committed; Polycam 6.0.21 attempt also recorded | **DONE** |
| 3.3 | Beat or tie on ≥70% of shared dimensions | `benchmark/head_to_head/README.md` | **43% (3 of 7). Failed** | **NOT DONE** — measured and reported |

## Part 4 — Fix loop

| # | Requirement | Path | Artifact | Status |
|---|---|---|---|---|
| 4.1 | Declare worst gate with failing number | `fixloop/DECLARATION.md` | Wall length, 0/4, median 56.3%. **Committed before the fix** | **DONE** |
| 4.2 | Root-cause hypothesis with evidence | `fixloop/DECLARATION.md` | Horizon-grazing rays; competing hypothesis tested and rejected (r = −0.31) | **DONE** |
| 4.3 | Predicted number | `fixloop/DECLARATION.md` | Four specific predictions | **DONE** |
| 4.4 | Ship the fix | `pipeline/cozmo/photo/room.py` | Depression floor 3°→8°, percentile 90→75, plus a normalisation bug found and disclosed | **DONE** |
| 4.5 | Before and after, both regenerable | `fixloop/before/`, `fixloop/after/` | Plans, renders and scores for both tiers; `cozmo run` regenerates from raw | **DONE** |
| 4.6 | Readable diff | git history | `fixloop/POSTMORTEM.md` + commits | **DONE** |

## Part 5 — Process evidence

| # | Requirement | Path | Artifact | Status |
|---|---|---|---|---|
| 5.1 | Commit as you work | git history | 40+ commits over the build, incremental, each explaining a decision | **DONE** |

## Deliverables

| # | Deliverable | Path | Status |
|---|---|---|---|
| D1 | Compliance matrix | `COMPLIANCE.md` | **DONE** |
| D2 | Capture route + device matrix | `docs/CAPTURE_PROTOCOL.md`, `docs/DEVICE_MATRIX.md`, `scripts/install_on_device.sh` | **DONE** — dev-build route measured at 11 s, which the brief accepts as an alternative to TestFlight |
| D3 | Repo + README, 15 min on a clean machine | `README.md` | **DONE** — verified by cloning fresh and running it |
| D4 | Reproduction bundle | [download](https://drive.google.com/file/d/1K7o64UsY5goG9nawqMY-G9xkF2YTlfEn/view?usp=sharing), `scripts/make_repro_bundle.sh` | **DONE** — 1.0 GB, 386 files, all 11 captures. Unzip at the repo root and every documented command runs unchanged. Not in git for size, and not on a public release because it is 386 photographs of a private home |
| D5 | Benchmark report | `benchmark/BENCHMARK_REPORT.md` | **DONE** — gates at both runnable tiers, repeatability table, head-to-head, timing |
| D6 | Fix loop bundle | `fixloop/` | **DONE** |
| D7 | Technical report, max 6 pages | `docs/TECHNICAL_REPORT.md` | **DONE** |
| D8 | Raw benchmark data | `benchmark/raw/` | **DONE** |

## Constraints

| Constraint | Status |
|---|---|
| Handheld consumer capture only | **DONE** — iPhone 13 throughout |
| Runs without calling our infrastructure | **DONE** — no network calls; OpenCV and numpy only |
| Pretrained models/APIs disclosed | **DONE** — none used. ARKit is disclosed as the capture-side dependency |
| Weights fetched by script | n/a — no weights |
| Mirrors, glass, wet-look, low light covered | **NOT DONE** — present in the captures (bathrooms, kitchen) but not analysed |
