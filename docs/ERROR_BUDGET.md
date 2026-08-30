# Error budget

Measured contributions, not estimates. Every row here traces to a capture in
`benchmark/raw/` and a script that recomputes it. Rows stay out until measured.

## Photo tier

### EXIF focal-length rounding — **measured, 0.49% worst case**

The photo tier may read `photos/**` only, so it recovers focal length from
EXIF `FocalLengthIn35mmFilm`, which is an integer. We write that integer by
rounding ARKit's live estimate, deliberately (see `DECISIONS.md`). The cost:

| Capture | Photos | Mean fx error | Worst fx error |
|---|---|---|---|
| `capture_20260830_173700_photo` | 8 | −0.36% | 0.49% |

Against a ±8% wall-length gate this is negligible — roughly 1/16th of the
budget. Rounding is not where the photo tier will fail.

### **OPEN: the 35 mm-equivalent convention is ambiguous, and it is worth ~4%**

Our EXIF says `FocalLengthIn35mmFilm = 27` for the iPhone 13 wide camera,
computed as `fx · 36 / imageWidth` — the horizontal convention against a 36 mm
full-frame width. Apple markets the same lens as **26 mm**, which is a different
convention (diagonal, on a 3:2 frame).

This matters because the brief's floor tier is "any picture in". If a grader
supplies stills from the **stock Camera app**, their EXIF will carry Apple's
number, not ours. A pipeline that assumes the horizontal convention would
compute `fx = 26 · 4032 / 36 = 2912` against a true ~3045 — a **−4.4% scale
error**, over half the ±8% gate consumed before any geometry runs.

Consequences to handle in the pipeline:

1. Never trust a single convention. Derive focal length from EXIF, then
   cross-check it against vanishing-point or plane-consistency geometry
   recovered from the images themselves, and widen the interval when they
   disagree.
2. Treat a photo set of unknown provenance as having a focal-length prior with
   a ±5% spread, not a point value. This is precisely the kind of thin input
   where the brief expects intervals to widen rather than for us to sound
   confident.

**To do:** shoot the same room with the stock Camera app on the same phone and
read its EXIF, to pin down Apple's convention empirically rather than by
argument.

## Ground-truth side

### Ceiling flatness — **withdrawn**

An earlier reading of the Living room gave wall heights of 325.4/325.9 cm, a
0.5 cm corner-to-corner spread, and that was written up here as a floor on
achievable ceiling accuracy. The operator's corrected measurement (2026-08-31)
gives a uniform 329.4 cm, so the spread was an artefact of the superseded
numbers rather than a property of the room. The full 1.5 cm gate is available.
Recorded rather than deleted because the reasoning still applies to any room
whose ceiling genuinely is not flat, and we should check for it per room.

## Known capture-side issues

- A capture saved with zero photos still writes a manifest and survives the
  launch purge, which only removes manifest-less directories
  (`capture_20260830_172252_photo` is one). The pipeline must reject an empty
  capture with a clear message rather than producing an empty plan.
- `ambient_intensity` reads 0 on the first frame of a session; ARKit's light
  estimate is not ready yet. Relevant to the low-light failure mode, where that
  field is the trigger.
