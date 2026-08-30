"""Sensor-budget enforcement.

The brief's tier ladder only means something if the thin tiers are actually
thin. Every capture bundle declares, in its own manifest, the set of paths the
pipeline may read at that tier. This module turns that declaration into a rule
the code obeys: reads go through :class:`SensorBudget`, and anything outside it
raises rather than quietly returning data.

The point is that the claim becomes checkable. "The photo tier does not use
poses" is an assertion in a report; a :class:`BudgetViolation` traceback is
evidence. It also protects against the failure that is easy to commit and hard
to notice — a debugging shortcut that reads ``_reference/poses.jsonl`` and is
never taken out, quietly turning the photo tier into the LiDAR tier and
inflating every number downstream.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


class BudgetViolation(RuntimeError):
    """Raised when the pipeline reaches for a file this tier may not read."""

    def __init__(self, path: str, tier: str, allowed: Iterable[str]) -> None:
        self.path = path
        self.tier = tier
        self.allowed = list(allowed)
        super().__init__(
            f"{path!r} is outside the {tier!r} tier's sensor budget.\n"
            f"  Allowed: {', '.join(self.allowed)}\n"
            f"  Reading it would make this tier something other than what it claims to be."
        )


def _compile(pattern: str) -> re.Pattern[str]:
    """Translate a bundle glob to a regex.

    Only two wildcards, with the meanings the manifest relies on:
    ``**`` spans directory separators, ``*`` does not. Written by hand because
    ``fnmatch`` conflates the two, which would let ``photos/*`` match
    ``photos/01_hall/0001.jpg`` and make the budget looser than it reads.
    """
    out: list[str] = []
    i = 0
    while i < len(pattern):
        ch = pattern[i]
        if ch == "*":
            if pattern[i : i + 2] == "**":
                out.append(".*")
                i += 2
                continue
            out.append("[^/]*")
        elif ch == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(ch))
        i += 1
    return re.compile("^" + "".join(out) + "$")


@dataclass(frozen=True)
class SensorBudget:
    """The paths one tier may read, as declared by the capture itself."""

    tier: str
    patterns: tuple[str, ...]

    @classmethod
    def from_manifest(cls, manifest: dict) -> "SensorBudget":
        tier = manifest.get("tier")
        patterns = manifest.get("sensorBudget") or manifest.get("sensor_budget")
        if not tier or not patterns:
            raise ValueError(
                "Capture manifest declares no tier or no sensor budget. "
                "Refusing to guess: a bundle that does not say what it is cannot be scored."
            )
        return cls(tier=tier, patterns=tuple(patterns))

    def allows(self, relpath: str) -> bool:
        relpath = relpath.replace("\\", "/").lstrip("./")
        return any(_compile(p).match(relpath) for p in self.patterns)

    def require(self, relpath: str) -> None:
        if not self.allows(relpath):
            raise BudgetViolation(relpath, self.tier, self.patterns)
