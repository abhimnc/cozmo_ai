"""Command line entry point.

``cozmo inspect`` works today: it loads a bundle, applies the tier's sensor
budget and reports both what it can see and what it is withholding from itself.
``cozmo run`` is the one-command-per-capture entry the brief requires; the
geometry stages behind it are not written yet, and it says so plainly rather
than emitting a plausible-looking empty plan.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .budget import BudgetViolation
from .bundle import CaptureBundle, EmptyCapture


def _human(n: int, one: str, many: str | None = None) -> str:
    return f"{n} {one if n == 1 else (many or one + 's')}"


def cmd_inspect(args: argparse.Namespace) -> int:
    try:
        bundle = CaptureBundle.load(args.bundle)
    except (EmptyCapture, FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"capture   {bundle.capture_id}")
    print(f"tier      {bundle.tier}")
    print(f"device    {bundle.device_model}")
    print(f"rooms     {_human(len(bundle.rooms), 'room')}")

    print("\nsensor budget (readable at this tier)")
    for pattern in bundle.budget.patterns:
        print(f"  + {pattern}")
    rationale = bundle.manifest.get("budgetRationale")
    if rationale:
        print(f"  {rationale}")

    in_budget = list(bundle.iter_paths())
    withheld = bundle.withheld_paths()
    print(f"\nvisible   {_human(len(in_budget), 'file')}")
    print(f"withheld  {_human(len(withheld), 'file')}")
    for path in withheld:
        print(f"  - {path}")

    if bundle.tier == "photo":
        print("\nphotos per room")
        for room in bundle.rooms:
            paths = bundle.photos_by_room().get(room.slug, [])
            flag = "" if len(paths) >= 2 else "   <- below the 2-photo floor"
            print(f"  {room.index:02d} {room.name:<18} {len(paths):>2}{flag}")

    problems = bundle.validate_inputs()
    if problems:
        print("\nproblems")
        for p in problems:
            print(f"  ! {p}")

    if args.prove_budget:
        print("\nbudget enforcement check")
        for candidate in ("_reference/poses.jsonl", "_reference/planes.json", "poses.jsonl"):
            try:
                bundle.open(candidate).close()
            except BudgetViolation:
                print(f"  refused {candidate}")
            except FileNotFoundError:
                print(f"  absent  {candidate}")
            else:
                print(f"  ALLOWED {candidate}   <- budget did not hold")
                return 1

    return 1 if problems else 0


def cmd_run(args: argparse.Namespace) -> int:
    try:
        bundle = CaptureBundle.load(args.bundle)
    except (EmptyCapture, FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    problems = bundle.validate_inputs()
    if problems:
        print("error: capture is not usable", file=sys.stderr)
        for p in problems:
            print(f"  ! {p}", file=sys.stderr)
        return 2

    print(f"error: no geometry stage is implemented yet for the {bundle.tier!r} tier.",
          file=sys.stderr)
    print("  The bundle loads and the sensor budget holds; reconstruction is the next build.",
          file=sys.stderr)
    return 3


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cozmo", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_inspect = sub.add_parser("inspect", help="Load a capture and show what this tier may read.")
    p_inspect.add_argument("bundle", type=Path)
    p_inspect.add_argument("--prove-budget", action="store_true",
                           help="Attempt out-of-budget reads and confirm each is refused.")
    p_inspect.set_defaults(func=cmd_inspect)

    p_run = sub.add_parser("run", help="Produce a plan from one capture.")
    p_run.add_argument("bundle", type=Path)
    p_run.add_argument("-o", "--output", type=Path, default=None)
    p_run.set_defaults(func=cmd_run)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
