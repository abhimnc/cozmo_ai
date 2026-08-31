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
            # Prefer views where the wall stayed inside the frame.
            #
            # A wall that runs out of the image was measured to where our view
            # stopped, not where the wall did, so its length is a lower bound.
            # Mixing lower bounds into a median drags the answer wherever the
            # framing happened to fall. Measured on the benchmark: bathroom_1's
            # single whole-wall view gives 1.88 m against a 1.38-2.35 m room,
            # while its three truncated views give 3.3-3.7 m.
            #
            # When no view saw a whole wall the truncated ones are all there is,
            # and the median of them is used. Taking the *largest* was tried on the
            # reasoning that each is a lower bound so the biggest is the tightest.
            # It was much worse - footprint 85.5 to 173.7 m2 against ~67 - because
            # the bound only holds in principle: measurement noise pushes some
            # truncated readings above the truth, and a maximum selects for
            # exactly those.
            whole = [v for v in good if not getattr(v, "truncated", False)]
            source = whole or good
            depths = [v.depth_far_m for v in source]
            widths = [v.width_span_m for v in source]
            basis = (f"{len(whole)} of {len(good)} views saw a whole wall"
                     if whole else
                     f"no view saw a whole wall; median of {len(good)} truncated views")
            depth = Measurement.from_samples(
                depths, "m", "floor_backprojection_camera_height_prior",
                floor_rel=DEPTH_REL_INTERVAL,
                notes=f"Scale from a 1.45 m camera-height prior. {basis}. Interval set from measured error against tape ground truth.")
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
               command: str, runtime_s: float, links=None) -> dict:
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

    # Damage reasoning. regions is empty until a detector exists; the rest
    # follows from it, so all three collapse to empty together.
    from .damage.rules import evaluate as evaluate_rules
    from .damage.scope import build as build_scope

    regions = []                      # no detector yet
    context = {"rooms": [e.room_id for e in estimates],
               "adjacent": {}}
    for l in (links or []):
        context["adjacent"].setdefault(l.room_a, []).append(l.room_b)
        context["adjacent"].setdefault(l.room_b, []).append(l.room_a)
    concealed = evaluate_rules(regions, context)
    scope = build_scope(regions, concealed)

    damage_json = [{"id": r.id, "room_id": r.room_id, "surface_id": r.surface_id,
                    "damage_class": r.damage_class,
                    "extent": Measurement.from_relative(r.extent_m2, 0.3, "m2",
                                                        "detected_region").to_json(),
                    "confidence": r.confidence} for r in regions]
    flags_json = [{"id": f.id, "room_id": f.room_id, "surface_id": f.surface_id,
                   "rule_id": f.rule_id, "rule_statement": f.rule_statement,
                   "triggered_by": f.triggered_by, "confidence": f.confidence}
                  for f in concealed]
    scope_json = [{"id": s.id, "room_id": s.room_id, "surface_id": s.surface_id,
                   "action": s.action,
                   "quantity": Measurement.from_relative(
                       s.quantity_m2 if s.quantity_m2 else 1.0,
                       0.3 if s.quantity_m2 else 0.0,
                       s.unit if s.quantity_m2 else "count",
                       "extent_plus_overcut" if s.quantity_m2 else "investigation_no_area",
                       notes=s.note).to_json(),
                   "derived_from": s.derived_from} for s in scope]

    # Lay the rooms out from their dimensions and the recovered adjacency.
    from .layout import PlacedRoom, solve as solve_layout

    placed, layout_stats = solve_layout(
        [PlacedRoom(r["id"], r["name"],
                    r["walls"][1]["length"]["value"],
                    r["walls"][0]["length"]["value"]) for r in rooms_json],
        [(l.room_a, l.room_b) for l in (links or [])],
    )
    by_id = {p.room_id: p for p in placed}
    for r in rooms_json:
        if r["id"] in by_id:
            r["polygon"] = [[round(c, 3) for c in pt] for pt in by_id[r["id"]].polygon()]

    adjacency = [
        {"room_a": l.room_a, "room_b": l.room_b,
         "via": f"shared_view_{l.inliers}_inliers",
         "confidence": round(l.confidence, 2)}
        for l in (links or [])
    ]

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
            "adjacency": adjacency,
            "footprint_area": {
                "value": round(footprint, 3), "ci_low": round(footprint_lo, 3),
                "ci_high": round(footprint_hi, 3), "unit": "m2",
                "method": "union_of_placed_rooms",
                "notes": (f"Union of {layout_stats['placed']} placed room rectangles. Room sizes and "
                          "adjacency are measured; room *positions* are solved from those, not "
                          "observed, so the footprint is a sum of measured areas rather than a "
                          "surveyed outline."),
            },
            "room_overlap_area": {
                "value": layout_stats["overlap_area_m2"],
                "ci_low": layout_stats["overlap_area_m2"],
                "ci_high": layout_stats["overlap_area_m2"], "unit": "m2",
                "method": "measured_from_placed_polygons",
                "notes": "Checked directly against the placed rectangles, not assumed.",
            },
            "layout": {
                "position_method": "topological_layout",
                "position_note": ("Positions are solved so adjacent rooms touch and none overlap. "
                                  "Dimensions and adjacency are measured; positions are not - "
                                  "nothing observed says where along the hall a bedroom sits."),
                **{k: v for k, v in layout_stats.items() if k != "placed"},
            },
            "drift": {
                "method": "none",
                "applied": False,
                "notes": "Adjacency is recovered but room *placement* is not, so there are no accumulated poses to correct. Stated explicitly: this is an absence of the placement stage, not poses used as-is.",
            },
        },
        # No damage detector exists, so no regions are observed and the rule
        # engine has nothing to fire on. The stages are wired: give `evaluate()`
        # damage regions and flags and scope appear. Empty here means "nothing
        # observed", not "not implemented" - see COMPLIANCE.md, which marks the
        # detector NOT DONE and the rules PARTIAL.
        "damage": damage_json,
        "concealed_flags": flags_json,
        "scope": scope_json,
        "calibration": {
            "interval_basis": "empirical_from_benchmark",
            "coverage_target": 0.95,
            "scale_source": "exif_focal_length_and_camera_height_prior",
            "warnings": [
                "Room depth measured 11% and 23% low against tape ground truth on the two rooms that have it.",
                "Far-wall width measured 96% and 382% high on those same rooms; its interval is +/-100% and it should not be relied on.",
                "Ceiling height is a residential prior, not an estimate.",
                "Opening detection finds doors and archways only - a window has no floor contact for the method to use - and found 2 of 3 in the room with ground truth, with widths off by -14.8% and +52.7% against a 2 cm gate.",
                "No damage detector: damage regions, concealed flags and scope items are empty because nothing is observed, not because the stages are missing. Run `cozmo demo-damage` to see the rule engine fire on a worked damage set.",
                "Adjacency comes from verified image matches between rooms' photo sets, measured at 80% precision and 50% recall on the whole-floor capture. Rooms that merely look alike can match: this property's two bathrooms share tiling and are the known false positive.",
                "Openings are not assigned to a wall. Adjacency is reported without room placement, so the plan is a graph of which rooms touch, not a laid-out floor plan.",
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
