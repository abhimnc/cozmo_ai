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


def cmd_calibrate(args: argparse.Namespace) -> int:
    """Compare EXIF focal length against one recovered from image geometry."""
    from .photo.calibrate import estimate

    try:
        bundle = CaptureBundle.load(args.bundle)
    except (EmptyCapture, FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if bundle.tier != "photo":
        print(f"error: calibrate is a photo-tier command; this capture is {bundle.tier!r}.",
              file=sys.stderr)
        return 2

    photos = bundle.photos_by_room()
    rows = []
    print(f"{'photo':<26} {'segs':>5} {'exif px':>9} {'geom px':>9} {'diff':>8} {'expl':>6}  verdict")
    for room in bundle.rooms:
        for rel in photos.get(room.slug, []):
            est = estimate(str(bundle.root / rel))
            rows.append(est)
            geom = f"{est.focal_geometry_px:9.1f}" if est.focal_geometry_px else "        -"
            exif = f"{est.focal_exif_px:9.1f}" if est.focal_exif_px else "        -"
            err = f"{est.relative_error * 100:+7.2f}%" if est.relative_error is not None else "       -"
            verdict = "ok" if est.focal_geometry_px else f"rejected: {est.rejected}"
            expl = f"{est.inlier_fraction * 100:5.0f}%" if est.inlier_fraction else "     -"
            print(f"{rel.split('/')[-1]:<26} {est.n_segments:>5} {exif} {geom} {err} {expl}  {verdict}")

    usable = [r.relative_error for r in rows if r.relative_error is not None]
    if usable:
        import statistics
        print(f"\n{len(usable)} of {len(rows)} photos yielded a usable geometric focal length")
        print(f"  median disagreement with EXIF  {statistics.median(usable) * 100:+.2f}%")
        if len(usable) > 1:
            print(f"  spread (stdev)                 {statistics.stdev(usable) * 100:.2f}%")
        print("\n  The photo-tier wall-length gate is +/-8%. A systematic offset here is a")
        print("  scale bias that lands directly on every measured length.")
    else:
        print("\nNo photo yielded a geometric focal length.")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """One command per capture: bundle in, plan.json and plan.svg out."""
    import time
    from .plan import build_plan, estimate_rooms, write_outputs

    started = time.time()
    try:
        bundle = CaptureBundle.load(args.bundle)
    except (EmptyCapture, FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    problems = bundle.validate_inputs()
    if problems and bundle.tier == "photo":
        print("error: capture is not usable", file=sys.stderr)
        for p in problems:
            print(f"  ! {p}", file=sys.stderr)
        return 2

    views_by_room = _views_for(bundle)
    estimates = estimate_rooms(bundle, views_by_room)

    command = f"cozmo run {args.bundle}"
    plan = build_plan(bundle, estimates, command, time.time() - started)
    out_dir = args.output or (Path("out") / bundle.capture_id)
    json_path, svg_path = write_outputs(plan, out_dir)

    print(f"capture  {bundle.capture_id}  ({bundle.tier} tier)")
    for est in estimates:
        if est.depth_m:
            print(f"  {est.name:<16} {est.views_used}/{est.views_total} views   "
                  f"{est.depth_m.value:.2f} x {est.width_m.value:.2f} m")
        else:
            print(f"  {est.name:<16} 0/{est.views_total} views   no estimate")
    print(f"\nplan   {json_path}")
    print(f"render {svg_path}")
    print(f"time   {time.time() - started:.1f}s")
    return 0


def _views_for(bundle: CaptureBundle):
    """Per-room image analyses, whatever the tier stores them as."""
    from .photo.room import analyse
    out = {}
    if bundle.tier == "photo":
        for slug, paths in bundle.photos_by_room().items():
            out[slug] = [analyse(str(bundle.root / p)) for p in paths]
    elif bundle.tier == "video":
        from .video.frames import frames_by_room
        # Decoded frames carry no EXIF; the device model supplies the lens.
        focal35 = 27.0 if "iPhone" in bundle.device_model else None
        for slug, paths in frames_by_room(bundle).items():
            out[slug] = [analyse(p, focal_35mm=focal35) for p in paths]
    elif bundle.tier == "lidar":
        from .lidar.frames import frames_by_room
        for slug, paths in frames_by_room(bundle).items():
            out[slug] = [analyse(p) for p in paths]
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cozmo", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_inspect = sub.add_parser("inspect", help="Load a capture and show what this tier may read.")
    p_inspect.add_argument("bundle", type=Path)
    p_inspect.add_argument("--prove-budget", action="store_true",
                           help="Attempt out-of-budget reads and confirm each is refused.")
    p_inspect.set_defaults(func=cmd_inspect)

    p_cal = sub.add_parser("calibrate",
                           help="Compare EXIF focal length against image geometry (photo tier).")
    p_cal.add_argument("bundle", type=Path)
    p_cal.set_defaults(func=cmd_calibrate)

    p_run = sub.add_parser("run", help="Produce a plan from one capture.")
    p_run.add_argument("bundle", type=Path)
    p_run.add_argument("-o", "--output", type=Path, default=None,
                       help="Output directory (default: out/<capture_id>).")
    p_run.set_defaults(func=cmd_run)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
