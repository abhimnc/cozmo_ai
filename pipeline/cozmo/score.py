"""Scoring a plan against tape ground truth.

Compares what the pipeline produced to what was measured by hand, and applies
the brief's gates. Two rules the comparison follows, both of which change the
answer:

- Wall length is compared to **wall length**, never to the clear floor run.
  The Living room's walls and its floor differ by 40 cm because of two door
  reveals; scoring one against the other would report an 8% error that is really
  two doorways.
- A room's estimated depth and width are matched to whichever ground-truth wall
  pair minimises error, because nothing in the output fixes which wall the
  pipeline called "depth". Matching them arbitrarily would measure our labelling,
  not our geometry.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DimensionResult:
    room: str
    quantity: str
    truth_m: float
    estimate_m: float
    ci_low: float
    ci_high: float

    @property
    def error_m(self) -> float:
        return self.estimate_m - self.truth_m

    @property
    def error_pct(self) -> float:
        return self.error_m / self.truth_m * 100 if self.truth_m else float("nan")

    @property
    def covered(self) -> bool:
        """Does the quoted interval actually contain the truth?

        This is the calibration question, and it is scored separately from
        accuracy. A wrong estimate whose interval covers the truth is an honest
        estimate; a close one whose interval misses it is a lucky guess sold as
        a measurement.
        """
        return self.ci_low <= self.truth_m <= self.ci_high


def load_truth(path: Path) -> dict:
    return json.loads(path.read_text())


def score_room(plan_room: dict, truth: dict) -> list[DimensionResult]:
    # A stepped wall has no single length; its projected run is the comparable
    # quantity, since that is what a floor plan draws.
    walls = sorted(
        w.get("length_m", w.get("projected_length_m"))
        for w in truth["walls"]
        if w.get("length_m") or w.get("projected_length_m")
    )
    # The plan reports depth (walls A/C) and width (walls B/D).
    est_depth = plan_room["walls"][0]["length"]
    est_width = plan_room["walls"][1]["length"]

    # Ground truth has two distinct wall lengths per pair; take each pair's mean
    # since the plan models the room as a rectangle and cannot express the 8 cm
    # by which opposite walls differ.
    short_pair = (walls[0] + walls[1]) / 2
    long_pair = (walls[2] + walls[3]) / 2

    # Match to minimise total error: which of our two numbers is "the long wall"
    # is not something the output asserts.
    def pairing(a_truth, b_truth):
        return (abs(est_depth["value"] - a_truth) / a_truth
                + abs(est_width["value"] - b_truth) / b_truth)

    if pairing(long_pair, short_pair) <= pairing(short_pair, long_pair):
        pairs = [(est_depth, long_pair, "long wall"), (est_width, short_pair, "short wall")]
    else:
        pairs = [(est_depth, short_pair, "short wall"), (est_width, long_pair, "long wall")]

    results = [
        DimensionResult(truth["room_id"], label, t, e["value"], e["ci_low"], e["ci_high"])
        for e, t, label in pairs
    ]
    ch = plan_room["ceiling_height"]
    results.append(DimensionResult(truth["room_id"], "ceiling height",
                                   truth["ceiling_height_m"], ch["value"],
                                   ch["ci_low"], ch["ci_high"]))
    return results


def score_plan(plan_path: Path, truth_dir: Path) -> list[DimensionResult]:
    plan = json.loads(plan_path.read_text())
    out: list[DimensionResult] = []
    for room in plan["rooms"]:
        # Ground truth exists for two rooms; match on the canonical id.
        for candidate in (room["id"], room["id"].replace("bed_room", "bedroom")):
            tf = truth_dir / f"{candidate}.json"
            if tf.exists():
                out += score_room(room, load_truth(tf))
                break
    return out


GATES = {
    "photo": {"wall_length_rel": 0.08, "label": "wall lengths within +/-8%"},
    "video": {"wall_length_rel": 0.03, "label": "wall lengths within +/-3%"},
    "lidar": {"wall_length_rel": 0.02, "label": "Round 1 gates"},
}
CEILING_GATE_M = 0.015
