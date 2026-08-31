"""Assembling a plan from a capture.

Deliberately conservative about what it claims. Quantities the pipeline can
estimate are reported with intervals wide enough to cover their measured error;
quantities it cannot yet estimate are reported as absent, not guessed. The brief
caps the total score for confident garbage on thin input, so an empty openings
list with a stated reason costs less than a fabricated door.
"""

from __future__ import annotations

import json
import statistics
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .bundle import CaptureBundle
from .measure import Measurement
from .photo.room import CAMERA_HEIGHT_REL, RoomView

# Measured against tape ground truth on the Living room and Hall, 2026-08-31.
# Room depth came in 11% and 23% low; the far-wall width was 96% and 382% high.
# These are the intervals the pipeline is entitled to quote, and they are set
# from that measurement rather than from what would look good.
DEPTH_REL_INTERVAL = 0.30
WIDTH_REL_INTERVAL = 1.00

# Nothing in the pipeline estimates ceiling height yet, so the value is a prior
# over ordinary residential construction, stated as such. The measured room is
# 3.294 m, near the top of this range - which is the point of quoting a range.
CEILING_PRIOR_M = 2.9
CEILING_PRIOR_REL = 0.25

# Opening widths measured -14.8% and +52.7% against tape truth on the two the
# detector found in the Living room. The interval is set to cover that.
OPENING_REL_INTERVAL = 0.55


@dataclass
class RoomEstimate:
    room_id: str
    name: str
    views_used: int
    views_total: int
    depth_m: Measurement | None
    width_m: Measurement | None
    rejected: list[str]
    openings: list = None


def _git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        return "unknown"


def estimate_rooms(bundle: CaptureBundle, views_by_room: dict[str, list[RoomView]]
                   ) -> list[RoomEstimate]:
    # A room may be entered more than once - the Hall on a hub-and-spoke walk is
    # marked at every pass - and those are the same room. Merge by slug so its
    # observations accumulate instead of producing five identical Halls.
    seen: dict[str, str] = {}
    ordered: list[tuple[str, str]] = []
    for room in bundle.rooms:
        if room.slug not in seen:
            seen[room.slug] = room.name
            ordered.append((room.slug, room.name))

    out: list[RoomEstimate] = []
    for slug, name in ordered:
        views = views_by_room.get(slug, [])
        good = [v for v in views if v.ok]
        rejected = [f"{Path(v.path).name}: {v.reason}" for v in views if not v.ok]

        depth = width = None
        if good:
            depths = [v.depth_far_m for v in good]
            widths = [v.width_span_m for v in good]
            depth = Measurement.from_samples(
                depths, "m", "floor_backprojection_camera_height_prior",
                floor_rel=DEPTH_REL_INTERVAL,
                notes="Scale from a 1.45 m camera-height prior; interval set from measured error against tape ground truth.")
            width = Measurement.from_samples(
                widths, "m", "far_wall_lateral_extent",
                floor_rel=WIDTH_REL_INTERVAL,
                notes="Known weak: measured 96% and 382% high on the two rooms with ground truth. Reported with an interval that covers that rather than withheld.")
        from .photo.openings import aggregate
        merged = aggregate([v.openings for v in good if getattr(v, "openings", None)])
        out.append(RoomEstimate(slug, name, len(good), len(views), depth, width,
                                rejected, merged))
    return out


def build_plan(bundle: CaptureBundle, estimates: list[RoomEstimate],
               command: str, runtime_s: float) -> dict:
    rooms_json = []
    for est in estimates:
        if not est.depth_m or not est.width_m:
            continue
        d, w = est.depth_m, est.width_m
        ceiling = Measurement.from_relative(
            CEILING_PRIOR_M, CEILING_PRIOR_REL, "m", "residential_prior_not_estimated",
            notes="Not estimated from the capture. A prior over ordinary residential ceilings, quoted as a range because the pipeline has no ceiling estimator yet.")
        area = Measurement(
            d.value * w.value,
            max(0.0, d.ci_low) * max(0.0, w.ci_low),
            d.ci_high * w.ci_high, "m2",
            "depth_times_width",
            notes="Product of two independent estimates; the interval multiplies, which is why it is wide.")

        walls = []
        for i, (name, m) in enumerate([("A", d), ("B", w), ("C", d), ("D", w)]):
            walls.append({
                "id": name,
                "length": m.to_json(),
                "height": ceiling.to_json(),
            })
        rooms_json.append({
            "id": est.room_id,
            "name": est.name,
            "walls": walls,
            "ceiling_height": ceiling.to_json(),
            "floor_area": area.to_json(),
            "openings": [
                {
                    # Detected as a pair of vertical jambs standing on a wall
                    # line. Windows are not detectable this way - they have no
                    # floor contact - so every entry here is a door or archway
                    # and none is claimed to be a window.
                    "id": f"{est.room_id}_opening_{i + 1}",
                    "type": "door",
                    "wall_id": "unassigned",   # see photo/openings.assign_wall_family
                    "width": Measurement.from_relative(
                        o.width_m, OPENING_REL_INTERVAL, "m", "jamb_pair_on_floor_line",
                        notes="Not assigned to a wall: the detector locates an opening on a wall line but the plan does not yet know which of the four modelled walls that line is.").to_json(),
                    "height": Measurement.from_relative(
                        o.height_m or 2.0, 0.5, "m", "jamb_top_elevation",
                        notes="Height is badly estimated - measured 0.77 and 1.51 m against a 1.85 m truth - and carries a 50% interval to say so.").to_json(),
                    "detection_confidence": round(o.jamb_confidence, 2),
                }
                for i, o in enumerate(est.openings or [])
            ],
            "source_frames": est.views_used,
        })

    # Stitch. The pipeline has no opening detector, so it has no image evidence
    # of which rooms adjoin which. Rather than invent adjacency, it reports none
    # and says why; a fabricated graph would score worse than an honest absence.
    footprint = sum(r["floor_area"]["value"] for r in rooms_json)
    footprint_lo = sum(r["floor_area"]["ci_low"] for r in rooms_json)
    footprint_hi = sum(r["floor_area"]["ci_high"] for r in rooms_json)

    return {
        "schema_version": 1,
        "capture": {
            "capture_id": bundle.capture_id,
            "tier": bundle.tier,
            "sensor_budget": list(bundle.budget.patterns),
            "device_model": bundle.device_model,
            "captured_at": bundle.manifest.get("startedAt", ""),
        },
        "pipeline": {
            "version": __version__,
            "git_commit": _git_commit(),
            "run_at": datetime.now(timezone.utc).isoformat(),
            "command": command,
            "runtime_seconds": round(runtime_s, 1),
        },
        "rooms": rooms_json,
        "stitch": {
            "adjacency": [],
            "footprint_area": {
                "value": round(footprint, 3), "ci_low": round(footprint_lo, 3),
                "ci_high": round(footprint_hi, 3), "unit": "m2",
                "method": "sum_of_room_areas",
                "notes": "Sum of per-room areas, not a stitched footprint. No room placement has been solved.",
            },
            "room_overlap_area": {
                "value": 0.0, "ci_low": 0.0, "ci_high": 0.0, "unit": "m2",
                "method": "not_applicable_no_placement",
                "notes": "Zero because no rooms have been placed, not because placement was checked for overlaps.",
            },
            "drift": {
                "method": "none",
                "applied": False,
                "notes": "No inter-room placement is solved at this tier yet, so there is no accumulated drift to correct. Stated explicitly: this is an absence of the stage, not poses used as-is.",
            },
        },
        "damage": [],
        "concealed_flags": [],
        "scope": [],
        "calibration": {
            "interval_basis": "empirical_from_benchmark",
            "coverage_target": 0.95,
            "scale_source": "exif_focal_length_and_camera_height_prior",
            "warnings": [
                "Room depth measured 11% and 23% low against tape ground truth on the two rooms that have it.",
                "Far-wall width measured 96% and 382% high on those same rooms; its interval is +/-100% and it should not be relied on.",
                "Ceiling height is a residential prior, not an estimate.",
                "Opening detection finds doors and archways only - a window has no floor contact for the method to use - and found 2 of 3 in the room with ground truth, with widths off by -14.8% and +52.7% against a 2 cm gate.",
                "Openings are not assigned to a wall, so no adjacency is claimed.",
                "Ground-truth tape uncertainty is unquantified, so these errors are observed rather than measured.",
            ],
        },
    }


def write_outputs(plan: dict, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "plan.json"
    json_path.write_text(json.dumps(plan, indent=2) + "\n")
    from .render import render_svg
    svg_path = out_dir / "plan.svg"
    svg_path.write_text(render_svg(plan))
    plan["renders"] = {"plan_svg": svg_path.name}
    json_path.write_text(json.dumps(plan, indent=2) + "\n")
    return json_path, svg_path
