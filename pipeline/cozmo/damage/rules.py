"""Concealed-damage rules.

The brief asks for concealed-damage flags **with the rule that fired**, which is
the interesting half of the requirement. A flag without a traceable rule is an
opinion, and an adjuster cannot defend an opinion to a homeowner or an insurer.
So a rule here carries its own statement in plain words, and every flag names the
rule and the observations that satisfied it.

**These rules fire on observed damage, and this pipeline has no damage
detector.** On the current captures they therefore produce nothing. That is a
missing input, not a missing rule engine: the engine is exercised by
`evaluate()` against supplied damage regions, and `demo_regions()` provides a
worked set so the behaviour can be seen and checked.

The rules encode ordinary building logic - water runs downwards, wet rooms share
cavities with what adjoins them - rather than anything learned. That is
deliberate: a rule a homeowner can be read aloud is worth more here than a model
whose reasoning cannot be stated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class DamageRegion:
    """One observed damaged area on one surface."""

    id: str
    room_id: str
    surface_id: str          # a wall id, "ceiling" or "floor"
    damage_class: str        # e.g. "water_stain", "crack", "mould"
    extent_m2: float
    surface_area_m2: float | None = None
    height_fraction: float | None = None   # 0 at floor, 1 at ceiling
    confidence: float = 0.0


@dataclass
class ConcealedFlag:
    id: str
    room_id: str
    surface_id: str
    rule_id: str
    rule_statement: str
    triggered_by: list[str]
    confidence: float


@dataclass
class Rule:
    id: str
    statement: str
    applies: Callable[[DamageRegion, dict], bool]
    target: Callable[[DamageRegion, dict], tuple[str, str]]
    confidence: float


def _wet_rooms(context: dict) -> set[str]:
    """Rooms whose id suggests plumbing. Named rooms are what we have."""
    return {r for r in context.get("rooms", [])
            if any(k in r for k in ("bath", "kitchen", "toilet", "wc", "laundry"))}


RULES: list[Rule] = [
    Rule(
        id="R1_CEILING_WATER_FROM_ABOVE",
        statement=("Water staining on a ceiling means water arrived from the storey or void "
                   "above it, so the floor structure above is likely wet where it cannot be seen."),
        applies=lambda d, c: d.surface_id == "ceiling" and "water" in d.damage_class,
        target=lambda d, c: (d.room_id, "ceiling_void"),
        confidence=0.75,
    ),
    Rule(
        id="R2_WALL_BASE_WATER_SUBFLOOR",
        statement=("Water staining in the lower third of a wall means standing water reached the "
                   "wall base, so the subfloor and the wall cavity behind it are likely affected."),
        applies=lambda d, c: (d.height_fraction is not None and d.height_fraction < 0.33
                              and "water" in d.damage_class),
        target=lambda d, c: (d.room_id, "subfloor"),
        confidence=0.70,
    ),
    Rule(
        id="R3_SHARED_WALL_WITH_WET_ROOM",
        statement=("Damage on a wall of a room that adjoins a bathroom or kitchen may continue "
                   "inside the shared cavity, where plumbing runs out of sight."),
        applies=lambda d, c: bool(_wet_rooms(c) & set(c.get("adjacent", {}).get(d.room_id, []))),
        target=lambda d, c: (d.room_id, d.surface_id),
        confidence=0.55,
    ),
    Rule(
        id="R4_EXTENSIVE_SURFACE_DAMAGE",
        statement=("Damage covering more than a third of a surface is rarely confined to what is "
                   "visible; the substrate behind the whole surface should be opened and checked."),
        applies=lambda d, c: (d.surface_area_m2 is not None and d.surface_area_m2 > 0
                              and d.extent_m2 / d.surface_area_m2 > 0.33),
        target=lambda d, c: (d.room_id, d.surface_id),
        confidence=0.65,
    ),
    Rule(
        id="R5_MOULD_IMPLIES_PERSISTENT_MOISTURE",
        statement=("Mould needs sustained moisture, so its presence implies a source that is still "
                   "active and usually out of sight behind the affected surface."),
        applies=lambda d, c: "mould" in d.damage_class or "mold" in d.damage_class,
        target=lambda d, c: (d.room_id, d.surface_id),
        confidence=0.80,
    ),
]


def evaluate(regions: list[DamageRegion], context: dict | None = None) -> list[ConcealedFlag]:
    """Apply every rule to every observed region.

    A region can fire more than one rule and each produces its own flag: a wet
    wall base next to a bathroom is two distinct suspicions with two distinct
    remedies, and collapsing them would lose the reason for one of them.
    """
    context = context or {}
    flags: list[ConcealedFlag] = []
    for rule in RULES:
        for region in regions:
            try:
                if not rule.applies(region, context):
                    continue
            except Exception:
                continue
            room, surface = rule.target(region, context)
            flags.append(ConcealedFlag(
                id=f"{rule.id.lower()}_{region.id}",
                room_id=room,
                surface_id=surface,
                rule_id=rule.id,
                rule_statement=rule.statement,
                triggered_by=[region.id],
                confidence=round(rule.confidence * max(region.confidence, 0.5), 2),
            ))
    return flags


def demo_regions() -> tuple[list[DamageRegion], dict]:
    """A worked damage set, so the rule engine can be seen working.

    Not benchmark data and not derived from any capture. It exists because a rule
    engine that never fires is indistinguishable from one that does not work.
    """
    regions = [
        DamageRegion("dmg_1", "living_room", "ceiling", "water_stain", 1.20, 16.7, 1.0, 0.8),
        DamageRegion("dmg_2", "living_room", "A", "water_stain", 0.45, 16.7, 0.15, 0.7),
        DamageRegion("dmg_3", "bathroom_1", "B", "mould", 0.30, 8.0, 0.4, 0.9),
        DamageRegion("dmg_4", "kitchen", "C", "crack", 3.10, 8.4, 0.5, 0.6),
    ]
    context = {
        "rooms": ["living_room", "hall", "kitchen", "bathroom_1", "bathroom_2"],
        "adjacent": {"living_room": ["hall", "bathroom_2"], "bathroom_1": ["hall"],
                     "kitchen": ["hall"]},
    }
    return regions, context
