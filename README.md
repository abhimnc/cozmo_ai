# Cozmo AI — Round 2

Handheld iPhone capture in, dimensioned room geometry out. One command per
capture.

> **Read this first.** The pipeline runs end to end on **all three tiers** in
> under 12 seconds and produces schema-valid output. It passes **one accuracy
> gate of six** — the living room's short wall, −0.4%. Photo-tier intervals cover
> the truth 6 times in 6, but average ±100% of their own value, so that reflects
> how little is known rather than good calibration.
>
> Room placement and damage analysis are **absent**, not inaccurate. Opening
> detection exists but finds 2 of 3 doors and none within the 2 cm gate.
> `COMPLIANCE.md` marks all 31 requirements honestly;
> `benchmark/BENCHMARK_REPORT.md` has the numbers.

---

## Run it in under 15 minutes

Requires macOS or Linux, Python 3.11+, and [uv](https://docs.astral.sh/uv/)
(`curl -LsSf https://astral.sh/uv/install.sh | sh`).

```bash
git clone https://github.com/abhimnc/cozmo_ai && cd cozmo_ai
uv venv --python 3.12 .venv
uv pip install -e .

# Run a capture. One command, no configuration.
.venv/bin/cozmo run benchmark/raw/capture_20260831_031153_photo

# Score it against tape ground truth.
.venv/bin/cozmo score out/capture_20260831_031153_photo/plan.json
```

Outputs land in `out/<capture_id>/` as `plan.json` (validated against
`schema/cozmo_plan.schema.json`) and `plan.svg`.

No network calls, no API keys, no model weights. OpenCV and numpy only.

### Raw captures

Not in git — about **1 GB**, dominated by a 486 MB video walkthrough. They are
supplied alongside the submission as `cozmo_raw_captures.zip`
(built by `./scripts/make_repro_bundle.sh`).

```bash
unzip cozmo_raw_captures.zip     # from the repo root
```

That restores `benchmark/raw/` and every command on this page works unchanged.
The archive contains 11 captures: the whole-floor photo set, the video
walkthrough, the synthetic LiDAR bundle, the repeatability pair, and the earlier
captures kept for provenance.

**Verify what you have:**

```bash
cozmo inspect benchmark/raw/capture_20260831_031153_photo --prove-budget
```

### Other commands

```bash
cozmo inspect <bundle> --prove-budget   # show what this tier may read, and prove the rest is refused
cozmo calibrate <bundle>                # EXIF focal length vs image geometry
```

## Reproducing every reported number

```bash
cozmo run   benchmark/raw/capture_20260831_031153_photo   # photo tier
cozmo run   benchmark/raw/capture_20260831_033226_video   # video tier
cozmo score out/capture_20260831_031153_photo/plan.json
cozmo score out/capture_20260831_033226_video/plan.json
```

Fix-loop before/after are stored in `fixloop/before/` and `fixloop/after/` and
regenerate with the same commands at the two commits either side of the fix.

## The capture app

```bash
brew install xcodegen
cd ios
cp Signing.local.xcconfig.example Signing.local.xcconfig   # put your team ID in it
xcodegen generate && open CozmoCapture.xcodeproj
```

Signing team lives in a gitignored file so a clone never carries someone else's
identity. See `docs/CAPTURE_PROTOCOL.md` for what the person holding the phone
does.

## Layout

```
ios/                  Route 1 capture app (ARKit, Swift)
pipeline/cozmo/       bundle → plan
  budget.py           sensor-budget enforcement
  measure.py          Measurement: no value without an interval
  photo/room.py       single-view room geometry
  score.py            scoring against ground truth
schema/               published output schema
benchmark/            captures, ground truth, reports, head-to-head
fixloop/              declaration, before, after, post-mortem
docs/                 technical report, decisions, risks, error budget
```

## Design decisions worth knowing

**Sensor budgets are enforced, not conventional.** Each bundle declares the paths
its tier may read; reads go through `CaptureBundle.open` and anything outside
raises. Poses are recorded at every tier but written under `_reference/` at the
thin tiers, where they are out of budget. `cozmo inspect --prove-budget` shows
each out-of-budget read being refused. This guards a mistake that is easy to make
and nearly invisible: a debugging shortcut that reads poses at the photo tier and
never gets removed.

**No measurement exists without an interval.** `Measurement` cannot be
constructed without `ci_low`, `value`, `ci_high`, `unit` and `method`, and the
schema enforces the same. Intervals are set from measured error, not from what
looks good.

**Absent stages say they are absent.** `stitch.drift` reports
`method: "none", applied: false` because no placement stage exists — deliberately
distinguished from "poses used as-is", which the brief makes an automatic fail.
Openings are an empty list with a stated reason rather than a fabricated door.

## Where to look

| Question | File |
|---|---|
| What is done and not done? | `COMPLIANCE.md` |
| How accurate is it? | `benchmark/BENCHMARK_REPORT.md` |
| How does it work? | `docs/TECHNICAL_REPORT.md` |
| What was fixed, and did it work? | `fixloop/POSTMORTEM.md` |
| How does it compare to a real product? | `benchmark/head_to_head/README.md` |
| Why was it built this way? | `docs/DECISIONS.md` |
| What is it not honest about? | `docs/ERROR_BUDGET.md`, `docs/RISKS.md` |
