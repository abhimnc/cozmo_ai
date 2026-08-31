# Compliance matrix

Requirement → file path → artifact → status. Honest statuses only: **DONE**,
**PARTIAL**, **NOT DONE**. A requirement with no artifact is marked NOT DONE
rather than described as in progress.

Summary: **12 done, 7 partial, 12 not done** of 31 requirements.

## Part 1 — Capture route and tiers

| # | Requirement | Path | Artifact | Status |
|---|---|---|---|---|
| 1.1 | Choose a capture route | `docs/DECISIONS.md` | Route 1 chosen, with reasoning | **DONE** |
| 1.2 | Own iOS capture app | `ios/` | CozmoCapture, builds and runs on device | **DONE** |
| 1.3 | Installable in under 10 min | `docs/CAPTURE_PROTOCOL.md` | Xcode/devicectl install documented; **no TestFlight build** — needs a paid developer account | **PARTIAL** |
| 1.4 | Photo tier | `ios/.../CaptureTier.swift` | Implemented, 5 real captures | **DONE** |
| 1.5 | Video tier | `ios/.../VideoRecorder.swift` | Implemented, 339 s / 20,324-frame walkthrough captured | **DONE** |
| 1.6 | LiDAR tier | `ios/.../CaptureController.swift`, `pipeline/cozmo/lidar/` | Code path complete, **never run on real LiDAR data** — no LiDAR device available | **PARTIAL** |
| 1.7 | Device matrix | `docs/DEVICE_MATRIX.md` | Tier × hardware, probed at runtime, per-tier accuracy filled from benchmark | **DONE** |

## Part 2 — Output contract

| # | Requirement | Path | Artifact | Status |
|---|---|---|---|---|
| 2.1 | Dimensioned per-room plan: walls | `schema/`, `out/*/plan.json` | 4 walls per room with intervals | **PARTIAL** — rectangle only, ±30% |
| 2.2 | Ceiling height | `out/*/plan.json` | Reported as a **residential prior, not an estimate** | **PARTIAL** |
| 2.3 | Floor area | `out/*/plan.json` | Depth × width, interval propagated | **PARTIAL** |
| 2.4 | Openings | — | No opening detector | **NOT DONE** |
| 2.5 | Stitched multi-room plan, correct adjacency | — | No placement solved; `stitch.adjacency` empty with stated reason | **NOT DONE** |
| 2.6 | Per-surface damage regions, class and extent | — | No damage detection | **NOT DONE** |
| 2.7 | Concealed-damage flags with the rule that fired | `schema/` | Schema defines it, requires `rule_id` + `rule_statement`; no detector | **NOT DONE** |
| 2.8 | Scope line items keyed to surfaces | `schema/` | Schema defines it; no generator | **NOT DONE** |
| 2.9 | Confidence interval on every measurement | `pipeline/cozmo/measure.py` | `Measurement` type cannot be constructed without one; schema enforces it | **DONE** |
| 2.10 | One command per capture | `pipeline/cozmo/cli.py` | `cozmo run <bundle>` → plan.json + plan.svg, ~5 s | **DONE** |
| 2.11 | JSON to a published schema | `schema/cozmo_plan.schema.json` | Validated with `jsonschema` | **DONE** |
| 2.12 | Rendered plan | `pipeline/cozmo/render.py`, `out/*/plan.svg` | SVG with intervals drawn as bands | **DONE** |

## Part 2 — Benchmark set

| # | Requirement | Path | Artifact | Status |
|---|---|---|---|---|
| 2.13 | Multi-room capture, 3+ rooms plus connector | `benchmark/raw/capture_20260831_031153_photo` | 8 rooms, Hall connector, 61 photos | **DONE** |
| 2.14 | Furnished room with staged damage, two classes | — | Not staged | **NOT DONE** |
| 2.15 | Same rooms at all three tiers | `benchmark/raw/` | Photo and video done; LiDAR impossible on available hardware | **PARTIAL** |
| 2.16 | One room captured twice, same tier | `benchmark/raw/` | Living room in two photo captures | **DONE** |
| 2.17 | Laser or tape ground truth | `benchmark/ground_truth/` | Tape: Living room and Hall complete, walls/ceiling/openings/wall thickness | **PARTIAL** — 2 of 9 rooms |
| 2.18 | Raw sensor data submitted | `benchmark/raw/` | 10 captures incl. 486 MB video; gitignored, supplied separately | **DONE** |

## Part 2 — Gates

| # | Gate | Path | Result | Status |
|---|---|---|---|---|
| 2.19 | Opening widths ≤2 cm on ≥85% | — | No opening detection; cannot be scored | **NOT DONE** |
| 2.20 | Ceiling height ≤1.5 cm | `fixloop/after/score_photo.txt` | −12.0%, a prior not an estimate | **NOT DONE** |
| 2.21 | Repeatability within 1 cm / 0.5% | — | Scoring script exists; repeatability table not produced | **NOT DONE** |
| 2.22 | Drift accountability + ablation | `out/*/plan.json` | `stitch.drift` states `method: none, applied: false` because no placement stage exists. **Not** "poses used as-is" — the stage is absent, and the field says so | **PARTIAL** |
| 2.23 | Photo-tier whole-property stitch | — | Not implemented | **NOT DONE** |
| 2.24 | Photo ±8% / video ±3% wall lengths | `fixloop/after/` | Photo median 33.3%, video 27.2%. Both fail | **NOT DONE** — measured and reported |
| 2.25 | Calibration scored at every tier | `fixloop/after/` | 5 of 6 intervals contain truth at both tiers | **DONE** |

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
| D2 | Capture route + device matrix | `docs/CAPTURE_PROTOCOL.md`, `docs/DEVICE_MATRIX.md` | **PARTIAL** — no TestFlight |
| D3 | Repo + README, 15 min on a clean machine | `README.md` | **PARTIAL** |
| D4 | Reproduction bundle | `benchmark/raw/`, `cozmo run` | **PARTIAL** — raw data supplied separately |
| D5 | Benchmark report | `fixloop/`, `benchmark/` | **PARTIAL** — no repeatability table |
| D6 | Fix loop bundle | `fixloop/` | **DONE** |
| D7 | Technical report, max 6 pages | `docs/TECHNICAL_REPORT.md` | pending |
| D8 | Raw benchmark data | `benchmark/raw/` | **DONE** |

## Constraints

| Constraint | Status |
|---|---|
| Handheld consumer capture only | **DONE** — iPhone 13 throughout |
| Runs without calling our infrastructure | **DONE** — no network calls; OpenCV and numpy only |
| Pretrained models/APIs disclosed | **DONE** — none used. ARKit is disclosed as the capture-side dependency |
| Weights fetched by script | n/a — no weights |
| Mirrors, glass, wet-look, low light covered | **NOT DONE** — present in the captures (bathrooms, kitchen) but not analysed |
