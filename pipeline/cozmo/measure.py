"""Measurements with intervals.

The schema requires a confidence interval on every physical quantity, so the
type that carries a number carries its interval too. There is no constructor
that takes a bare value: an interval cannot be forgotten, only stated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math


@dataclass(frozen=True)
class Measurement:
    value: float
    ci_low: float
    ci_high: float
    unit: str
    method: str
    n_observations: int = 0
    notes: str = ""

    def __post_init__(self) -> None:
        # Lengths and areas cannot be negative. An interval wider than its own
        # value is legitimate on thin input - it is the honest way to say "this
        # could be almost anything" - but it must clamp at zero rather than run
        # below it, or two negative bounds multiply into a large positive area.
        if self.unit in ("m", "m2", "cm"):
            if self.value < 0:
                raise ValueError(
                    f"negative {self.unit}: {self.value}. A negative length is a failed fit "
                    "upstream, not a measurement - it should be rejected where it arises, "
                    "not clamped here."
                )
            if self.ci_low < 0:
                object.__setattr__(self, "ci_low", 0.0)
        if not (self.ci_low <= self.value <= self.ci_high):
            raise ValueError(
                f"interval does not contain its value: {self.ci_low} <= {self.value} <= {self.ci_high}"
            )

    @classmethod
    def from_relative(cls, value: float, rel: float, unit: str, method: str,
                      n: int = 0, notes: str = "") -> "Measurement":
        """A value with a symmetric fractional interval, e.g. rel=0.08 for +/-8%."""
        return cls(value, value * (1 - rel), value * (1 + rel), unit, method, n, notes)

    @classmethod
    def from_samples(cls, samples: list[float], unit: str, method: str,
                     floor_rel: float = 0.0, notes: str = "") -> "Measurement":
        """Interval from the spread of repeated observations.

        `floor_rel` is a minimum width. Agreement between a handful of
        observations is not proof of accuracy — three photos can agree on the
        same wrong wall — so a systematic floor stops a lucky cluster from
        producing an interval narrower than the method can justify.
        """
        n = len(samples)
        value = sorted(samples)[n // 2] if n % 2 else sum(sorted(samples)[n // 2 - 1:n // 2 + 1]) / 2
        if n >= 2:
            mean = sum(samples) / n
            sd = math.sqrt(sum((s - mean) ** 2 for s in samples) / (n - 1))
            # Predictive spread, not the standard error of the mean.
            #
            # `1.96 * sd / sqrt(n)` answers "where is the average of these
            # readings?" and assumes every view measured the same quantity. In a
            # room the rectangle model does not fit - the Hall is stepped with a
            # 1.75 m recess - different views see different walls, so they are not
            # repeated measurements of one number and averaging them has no
            # target. Dividing by sqrt(n) then makes the interval *shrink* as
            # disagreement accumulates, which is backwards: more views
            # contradicting each other is evidence of less certainty, not more.
            #
            # `1.96 * sd` answers the question actually being asked - "what would
            # another view of this room say?" - and widens exactly where the
            # model fits worst.
            half = max(1.96 * sd, value * floor_rel)
        else:
            half = value * max(floor_rel, 0.25)
            notes = (notes + " Single observation; interval is the method's prior, not measured.").strip()
        return cls(value, value - half, value + half, unit, method, n, notes)

    @property
    def relative_width(self) -> float:
        return (self.ci_high - self.ci_low) / (2 * self.value) if self.value else float("inf")

    def to_json(self) -> dict:
        out = {
            "value": round(self.value, 4),
            "ci_low": round(self.ci_low, 4),
            "ci_high": round(self.ci_high, 4),
            "unit": self.unit,
            "method": self.method,
        }
        if self.n_observations:
            out["n_observations"] = self.n_observations
        if self.notes:
            out["notes"] = self.notes
        return out
