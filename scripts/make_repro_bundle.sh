#!/usr/bin/env bash
# Package the raw captures for hand-off.
#
# They are excluded from git - about a gigabyte, dominated by a 486 MB video -
# so the repo stays clonable while the reproduction bundle travels separately.
# Unpacking it into benchmark/raw makes every documented command work unchanged.

set -euo pipefail
cd "$(dirname "$0")/.."

OUT="${1:-cozmo_raw_captures.zip}"
echo "==> packaging benchmark/raw into $OUT"
zip -qr "$OUT" benchmark/raw -x '*/.cache_*' -x '*.DS_Store'
echo "==> $(du -h "$OUT" | cut -f1)"
echo
echo "To use it:"
echo "  unzip $OUT -d <repo root>"
echo "  cozmo run benchmark/raw/capture_20260831_031153_photo"
