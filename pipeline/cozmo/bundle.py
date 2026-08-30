"""Reading a capture bundle, through the sensor budget.

Every read goes through :meth:`CaptureBundle.open`. There is deliberately no
convenience accessor that takes a raw filesystem path, because that would be
the hole through which the budget leaks.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from .budget import BudgetViolation, SensorBudget

# Read to load the bundle at all. Neither carries sensor data: one says what the
# capture is, the other what the rooms are called. Both appear in every tier's
# declared budget anyway; listing them here keeps loading honest if one does not.
_ALWAYS_READABLE = ("manifest.json", "rooms.json")


class EmptyCapture(ValueError):
    """A bundle that parsed but holds no usable input."""


@dataclass
class Room:
    index: int
    name: str
    slug: str
    photo_count: int = 0
    entered_at_seconds: float | None = None
    first_frame_index: int | None = None

    @property
    def folder_name(self) -> str:
        return f"{self.index:02d}_{self.slug}"


@dataclass
class CaptureBundle:
    root: Path
    manifest: dict[str, Any]
    budget: SensorBudget
    rooms: list[Room] = field(default_factory=list)

    # ---------------------------------------------------------------- loading

    @classmethod
    def load(cls, path: str | Path) -> "CaptureBundle":
        root = Path(path).expanduser().resolve()
        if not root.is_dir():
            raise FileNotFoundError(f"Not a capture bundle directory: {root}")

        manifest_path = root / "manifest.json"
        if not manifest_path.exists():
            raise EmptyCapture(
                f"{root.name} has no manifest.json.\n"
                "  A capture that was started and abandoned leaves this shape behind. "
                "There is nothing here to reconstruct."
            )
        manifest = json.loads(manifest_path.read_text())
        budget = SensorBudget.from_manifest(manifest)

        rooms: list[Room] = []
        rooms_path = root / "rooms.json"
        if rooms_path.exists():
            for entry in json.loads(rooms_path.read_text()).get("rooms", []):
                rooms.append(
                    Room(
                        index=entry["index"],
                        name=entry["name"],
                        slug=entry["slug"],
                        photo_count=entry.get("photoCount", 0),
                        entered_at_seconds=entry.get("enteredAtSeconds"),
                        first_frame_index=entry.get("firstFrameIndex"),
                    )
                )

        return cls(root=root, manifest=manifest, budget=budget, rooms=rooms)

    # ------------------------------------------------------------- properties

    @property
    def tier(self) -> str:
        return self.manifest["tier"]

    @property
    def capture_id(self) -> str:
        return self.manifest.get("captureId", self.root.name)

    @property
    def device_model(self) -> str:
        return self.manifest.get("device", {}).get("marketingName", "unknown")

    # ------------------------------------------------------------------ reads

    def open(self, relpath: str, mode: str = "rb"):
        """Open a file inside the bundle, subject to the budget."""
        if relpath not in _ALWAYS_READABLE:
            self.budget.require(relpath)
        target = (self.root / relpath).resolve()
        if not target.is_relative_to(self.root):
            raise BudgetViolation(relpath, self.tier, self.budget.patterns)
        return open(target, mode)

    def read_json(self, relpath: str) -> Any:
        with self.open(relpath, "r") as fh:
            return json.load(fh)

    def iter_paths(self, pattern: str = "**/*") -> Iterator[str]:
        """Relative paths of files this tier is allowed to see."""
        for path in sorted(self.root.glob(pattern)):
            if not path.is_file():
                continue
            rel = path.relative_to(self.root).as_posix()
            if rel in _ALWAYS_READABLE or self.budget.allows(rel):
                yield rel

    def withheld_paths(self) -> list[str]:
        """Files present in the bundle that this tier may not read.

        Not used by the pipeline. It exists so a run can *report* what it chose
        not to look at, which is the difference between a claim and a receipt.
        """
        out = []
        for path in sorted(self.root.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(self.root).as_posix()
            if rel not in _ALWAYS_READABLE and not self.budget.allows(rel):
                out.append(rel)
        return out

    # ------------------------------------------------------- tier inputs

    def photos_by_room(self) -> dict[str, list[str]]:
        """Photo tier: room slug -> in-budget photo paths."""
        out: dict[str, list[str]] = {}
        for room in self.rooms:
            paths = sorted(
                p for p in self.iter_paths(f"photos/{room.folder_name}/*")
                if p.lower().endswith((".jpg", ".jpeg", ".heic", ".png"))
            )
            out[room.slug] = paths
        return out

    def validate_inputs(self) -> list[str]:
        """Problems that would make a run meaningless. Empty list means usable."""
        problems: list[str] = []
        if not self.rooms:
            problems.append("No rooms recorded; nothing to reconstruct.")

        if self.tier == "photo":
            by_room = self.photos_by_room()
            total = sum(len(v) for v in by_room.values())
            if total == 0:
                problems.append("Photo tier with zero photos in budget.")
            for room in self.rooms:
                n = len(by_room.get(room.slug, []))
                if n == 0:
                    problems.append(f"Room {room.name!r} has no photos.")
                elif n < 2:
                    problems.append(
                        f"Room {room.name!r} has {n} photo. The brief's floor is 2 per room, "
                        "and a single view cannot resolve scale or shape."
                    )
        return problems
