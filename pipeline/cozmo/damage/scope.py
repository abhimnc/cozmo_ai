"""Scope line items: what has to be done, keyed to the surface it is done to.

The contract asks for scope items keyed to surfaces and derived from the damage
findings, so each item here names the damage region or concealed flag that
justifies it. An item nobody can trace back to an observation is a guess at a
price, and a homeowner is entitled to ask why a line is on their estimate.

Two kinds of item, kept distinct because they are different promises:

- **Remediation** answers observed damage. Its quantity is the measured extent,
  so it inherits that measurement's uncertainty.
- **Investigation** answers a *concealed* flag. Nobody can quantify hidden damage
  before opening the surface, so these carry no area at all - they are priced by
  access, and pretending otherwise would put a confident number on something
  unseen.
"""

from __future__ import annotations

from dataclasses import dataclass

from .rules import ConcealedFlag, DamageRegion

# Remediation is quoted with an allowance beyond the measured region: damage
# stops being visible before it stops existing, and a repair has to reach sound
# substrate. 15% is a working figure, not a measured one, and is labelled as such
# wherever it appears.
OVERCUT_ALLOWANCE = 0.15

ACTIONS = {
    "water_stain": "Remove and replace water-damaged surface finish; dry substrate before making good",
    "mould": "Remove mould-affected material under containment; treat and replace substrate",
    "mold": "Remove mould-affected material under containment; treat and replace substrate",
    "crack": "Cut out and make good cracked substrate; investigate movement before finishing",
    "impact": "Cut out damaged section and make good",
}
DEFAULT_ACTION = "Remove damaged material and make good"


@dataclass
class ScopeItem:
    id: str
    room_id: str
    surface_id: str
    action: str
    quantity_m2: float | None
    unit: str
    derived_from: list[str]
    note: str = ""


def build(regions: list[DamageRegion], flags: list[ConcealedFlag]) -> list[ScopeItem]:
    items: list[ScopeItem] = []

    for r in regions:
        items.append(ScopeItem(
            id=f"scope_{r.id}",
            room_id=r.room_id,
            surface_id=r.surface_id,
            action=ACTIONS.get(r.damage_class, DEFAULT_ACTION),
            quantity_m2=round(r.extent_m2 * (1 + OVERCUT_ALLOWANCE), 3),
            unit="m2",
            derived_from=[r.id],
            note=(f"Measured extent {r.extent_m2:.2f} m2 plus a {OVERCUT_ALLOWANCE:.0%} allowance "
                  "to reach sound substrate. The allowance is a trade convention, not a "
                  "measurement, and inherits the extent's uncertainty on top of its own."),
        ))

    # One investigation per surface, not per flag: two rules pointing at the same
    # wall are two reasons to open it, not two openings-up to pay for.
    by_surface: dict[tuple[str, str], list[ConcealedFlag]] = {}
    for f in flags:
        by_surface.setdefault((f.room_id, f.surface_id), []).append(f)

    for (room, surface), group in sorted(by_surface.items()):
        rules = sorted({f.rule_id for f in group})
        items.append(ScopeItem(
            id=f"scope_investigate_{room}_{surface}",
            room_id=room,
            surface_id=surface,
            action="Open up and inspect concealed substrate; re-scope once the extent is visible",
            quantity_m2=None,
            unit="count",
            derived_from=sorted({f.id for f in group}),
            note=("Concealed damage cannot be quantified before the surface is opened, so this "
                  f"line carries no area. Raised by {len(rules)} rule(s): {', '.join(rules)}."),
        ))

    return items
