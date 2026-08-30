"""Line segment detection.

Indoor scenes are dominated by straight edges along three orthogonal
directions — wall/floor junctions, door frames, ceiling lines. Those segments
are the raw material for everything the photo tier recovers, because their
vanishing points give camera orientation and, crucially, an estimate of focal
length that owes nothing to EXIF.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class Segments:
    """Segments in the coordinate frame of a possibly downscaled image."""

    points: np.ndarray          # (N, 4) as x1, y1, x2, y2
    scale: float                # downscaled = original * scale
    width: int                  # downscaled width
    height: int

    def __len__(self) -> int:
        return len(self.points)

    @property
    def midpoints(self) -> np.ndarray:
        return np.column_stack([
            (self.points[:, 0] + self.points[:, 2]) / 2,
            (self.points[:, 1] + self.points[:, 3]) / 2,
        ])

    @property
    def directions(self) -> np.ndarray:
        d = np.column_stack([
            self.points[:, 2] - self.points[:, 0],
            self.points[:, 3] - self.points[:, 1],
        ])
        return d / (np.linalg.norm(d, axis=1, keepdims=True) + 1e-12)

    @property
    def lengths(self) -> np.ndarray:
        return np.hypot(self.points[:, 2] - self.points[:, 0],
                        self.points[:, 3] - self.points[:, 1])

    def homogeneous_lines(self) -> np.ndarray:
        """Each segment as a homogeneous line through its two endpoints."""
        p1 = np.column_stack([self.points[:, 0], self.points[:, 1], np.ones(len(self.points))])
        p2 = np.column_stack([self.points[:, 2], self.points[:, 3], np.ones(len(self.points))])
        return np.cross(p1, p2)


def detect(image_path: str, max_width: int = 1600, min_length_frac: float = 0.03) -> Segments:
    """Detect line segments, working on a downscaled copy for speed.

    Vanishing-point geometry is scale-covariant, so a focal length recovered in
    downscaled pixels converts back by a single multiplication. Detecting at
    full 12 MP resolution costs time and finds mostly texture edges — the long
    structural lines that matter survive downscaling intact.

    Short segments are dropped: their direction is dominated by pixel noise, and
    a badly-oriented short segment votes just as hard as a good long one.
    """
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(image_path)

    h0, w0 = img.shape
    scale = min(1.0, max_width / float(w0))
    if scale < 1.0:
        img = cv2.resize(img, (int(round(w0 * scale)), int(round(h0 * scale))),
                         interpolation=cv2.INTER_AREA)
    h, w = img.shape

    detector = cv2.createLineSegmentDetector(cv2.LSD_REFINE_STD)
    raw = detector.detect(img)[0]
    if raw is None or len(raw) == 0:
        return Segments(np.empty((0, 4)), scale, w, h)

    pts = raw.reshape(-1, 4).astype(np.float64)
    lengths = np.hypot(pts[:, 2] - pts[:, 0], pts[:, 3] - pts[:, 1])
    keep = lengths >= min_length_frac * w
    return Segments(pts[keep], scale, w, h)
