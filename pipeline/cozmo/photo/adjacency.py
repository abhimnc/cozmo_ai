"""Which rooms touch, from the photographs alone.

At the photo tier there are no poses and no ordering, so nothing in the input
states that the living room adjoins the hall. But this property - like most - is
connected by open archways, and an archway has a consequence: a photograph taken
in one room and pointed at an archway *contains part of the next room*. Its
floor, its far wall, sometimes its own doorways.

So two rooms that touch share visible content, and two rooms that do not cannot.
Matching image features between the photo sets of every pair of rooms turns that
into a measurement.

What this does **not** need is wall assignment, which was found structurally
blocked: naming the wall an opening sits on requires a coordinate frame shared
between views, while asking whether two rooms share a view does not.

What it does **not** give is placement. Knowing the living room adjoins the hall
does not say where. That is the remaining half of a stitch and it is not
attempted here.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import cv2
import numpy as np

# ORB rather than SIFT: it is free of patent concerns, fast enough to run every
# pair of rooms in seconds, and this is a *matching count* problem rather than a
# precise-geometry one - we need to know whether two images overlap, not where.
ORB_FEATURES = 1500

# Lowe's ratio. A match is kept only when the best candidate is clearly better
# than the second best, which is what separates a genuine correspondence from
# one of the many near-duplicates a repetitive interior produces.
RATIO = 0.75

# Minimum inliers under a fundamental-matrix fit for a pair of images to count as
# genuinely overlapping. Raw match counts are inflated by repeated texture -
# identical tiles, a patterned bedspread - and geometric verification is what
# removes them.
# Chosen from a measured precision/recall sweep on the whole-floor capture:
#
#   threshold   links  correct  false  missed   precision  recall
#          12      15        6      9       2         40%     75%
#          15       7        5      2       3         71%     62%
#          20       5        4      1       4         80%     50%
#          60       3        3      0       5        100%     38%
#
# 20 favours precision. On a floor plan a false adjacency is worse than a missing
# one - it places a room somewhere it is not, and the gate asks for *correct*
# adjacency with no overlaps - so the operating point sits above the F1 optimum
# at 15 deliberately.
MIN_INLIERS = 20

# Spatial asymmetry was tried as a discriminator and **rejected**, 31 Aug 2026.
#
# The idea: a through-view should be lopsided, the next room occupying a small
# archway-shaped patch of the near frame and a large part of the far one, while
# two look-alike rooms match broadly across both.
#
# Measured, it made adjacency worse - correct links fell from 6 to 1. The reason
# is that the strongest true links come from photographs taken *in* the archway,
# which see both rooms broadly and are therefore symmetric. The lopsided matches
# are the weak, incidental ones. The signal runs opposite to the hypothesis.
#
# `asymmetry` is still computed and reported, because it is informative to a
# reader even though it is not a usable filter.
MIN_ASYMMETRY = 0.0


@dataclass
class RoomLink:
    room_a: str
    room_b: str
    inliers: int
    asymmetry: float
    best_pair: tuple[str, str]
    confidence: float


def _features(path: str, max_width: int = 900):
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return None, None
    h, w = img.shape
    if w > max_width:
        img = cv2.resize(img, (max_width, int(h * max_width / w)), interpolation=cv2.INTER_AREA)
    orb = cv2.ORB_create(nfeatures=ORB_FEATURES)
    return orb.detectAndCompute(img, None)


def _verified_inliers(kp1, des1, kp2, des2) -> tuple[int, float]:
    """Verified matches, and how *asymmetric* their spatial extent is.

    Match count alone conflates two different things. Two rooms that touch share
    content because one is visible through the other's archway. Two rooms that
    merely look alike - this property has two bathrooms with identical tiling -
    share content because they are similar, and match just as strongly while
    sharing no wall.

    The asymmetry separates them. A through-view match is lopsided: the next room
    occupies a *small* patch of the near image - the archway - and a *large* part
    of the far image, because in that one the camera was standing in it. Two
    look-alike rooms match broadly across both frames.

    So the second return value is the ratio of matched-point spread between the
    two images. Near 1 means "these two look alike"; far from 1 means "one of
    these is a window into the other".
    """
    if des1 is None or des2 is None or len(des1) < 8 or len(des2) < 8:
        return 0, 1.0
    matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
    raw = matcher.knnMatch(des1, des2, k=2)
    good = [m for m, n in (p for p in raw if len(p) == 2) if m.distance < RATIO * n.distance]
    if len(good) < 8:
        return 0, 1.0
    src = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    # A fundamental matrix, not a homography: the two photos are taken from
    # different places, so the scene is not a plane and a homography would reject
    # correct matches.
    _, mask = cv2.findFundamentalMat(src, dst, cv2.FM_RANSAC, 3.0, 0.99)
    if mask is None:
        return 0, 1.0
    keep = mask.ravel().astype(bool)
    n = int(keep.sum())
    if n < 8:
        return n, 1.0

    def spread(points):
        pts = points[keep].reshape(-1, 2)
        return float(max(np.ptp(pts[:, 0]), 1.0) * max(np.ptp(pts[:, 1]), 1.0))

    a, b = spread(src), spread(dst)
    ratio = max(a, b) / max(min(a, b), 1.0)
    return n, ratio


def find_links(photos_by_room: dict[str, list[str]]) -> list[RoomLink]:
    """Room pairs whose photographs share verified visual content."""
    cache = {}
    for slug, paths in photos_by_room.items():
        cache[slug] = [(p, *_features(p)) for p in paths]

    links: list[RoomLink] = []
    for a, b in combinations(sorted(cache), 2):
        best, best_asym, best_pair = 0, 1.0, ("", "")
        for pa, kpa, dea in cache[a]:
            for pb, kpb, deb in cache[b]:
                n, asym = _verified_inliers(kpa, dea, kpb, deb)
                if n > best:
                    best, best_asym, best_pair = n, asym, (pa.split("/")[-1], pb.split("/")[-1])
        if best >= MIN_INLIERS:
            links.append(RoomLink(a, b, best, best_asym, best_pair,
                                  min(1.0, best / 40.0)))
    return sorted(links, key=lambda l: -l.inliers)
