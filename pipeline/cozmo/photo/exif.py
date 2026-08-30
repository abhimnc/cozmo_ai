"""Camera parameters recoverable from a photo alone.

At the photo tier, EXIF is the only place a focal length can come from. That
makes reading it correctly a scale question, not a metadata question: focal
length maps directly onto how large the room is.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import BinaryIO

from PIL import Image, ExifTags

_TAG = {v: k for k, v in ExifTags.TAGS.items()}

# 35 mm "full frame" is 36 x 24 mm. The horizontal convention divides by 36.
FULL_FRAME_WIDTH_MM = 36.0


@dataclass
class PhotoCamera:
    width: int
    height: int
    make: str | None
    model: str | None
    focal_35mm: float | None

    @property
    def focal_px_horizontal(self) -> float | None:
        """Focal length in pixels, assuming the horizontal 35 mm convention.

        Deliberately *one* interpretation rather than the answer. Apple markets
        the iPhone 13 wide lens as 26 mm while this convention gives 27, and the
        difference is about 4% of scale — half the photo tier's whole budget.
        The pipeline therefore treats this as a prior to be checked against
        image geometry, never as a measurement. See docs/ERROR_BUDGET.md.
        """
        if self.focal_35mm is None:
            return None
        return self.focal_35mm * self.width / FULL_FRAME_WIDTH_MM

    @property
    def principal_point(self) -> tuple[float, float]:
        """Assumed at the image centre.

        True for ARKit's rectified frames to well under a percent, and there is
        nothing at this tier with which to estimate it otherwise.
        """
        return (self.width / 2.0, self.height / 2.0)


def read_camera(path: str | BinaryIO) -> PhotoCamera:
    with Image.open(path) as img:
        width, height = img.size
        exif = img.getexif()
        ifd = exif.get_ifd(_TAG["ExifOffset"]) if _TAG.get("ExifOffset") in exif else {}

    def get(tag: str):
        tid = _TAG.get(tag)
        if tid is None:
            return None
        return exif.get(tid) or ifd.get(tid)

    focal35 = get("FocalLengthIn35mmFilm")
    return PhotoCamera(
        width=width,
        height=height,
        make=get("Make"),
        model=get("Model"),
        focal_35mm=float(focal35) if focal35 else None,
    )
