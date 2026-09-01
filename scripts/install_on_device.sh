#!/usr/bin/env bash
# Install Cozmo Capture on a connected iPhone.
#
# The brief allows "a TestFlight build or a dev build we can install on our
# device in under 10 minutes". This is that dev build. Plug the phone in, run
# this, trust the certificate once on the phone.
#
#   ./scripts/install_on_device.sh
#
# Requires: macOS with Xcode, an Apple ID signed in to Xcode (a free account is
# enough), and the phone unlocked with Developer Mode on.

set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> finding a connected iPhone"
# BSD awk has no 3-argument match(), so this stays in grep. The UDID form is
# 8 hex, a dash, 16 hex - distinct from a simulator's dashed UUID.
UDID=$(xcrun xctrace list devices 2>/dev/null \
  | sed -n '/^== Devices ==/,/^== Simulators ==/p' \
  | grep -oE '\([0-9A-Fa-f]{8}-[0-9A-Fa-f]{16}\)' | head -1 | tr -d '()' || true)

if [ -z "${UDID:-}" ]; then
  echo "No iPhone found. Connect one by cable, unlock it, and trust this Mac." >&2
  exit 1
fi
echo "    device $UDID"

# Paired but unreachable is the common case and the raw xcodebuild error for it
# is unhelpful, so say what to do instead.
STATE=$(xcrun devicectl list devices 2>/dev/null | grep -i "$UDID" | awk '{print $(NF-1)}' || true)
if xcrun devicectl list devices 2>/dev/null | grep -qi "unavailable"; then
  echo
  echo "The iPhone is paired but not reachable. Check:" >&2
  echo "  - connected by cable, and the cable carries data" >&2
  echo "  - phone unlocked, and 'Trust This Computer' accepted" >&2
  echo "  - Settings > Privacy & Security > Developer Mode is on" >&2
  exit 1
fi

if ! command -v xcodegen >/dev/null 2>&1; then
  echo "==> xcodegen missing; install with: brew install xcodegen" >&2
  exit 1
fi

echo "==> generating the project"
( cd ios && xcodegen generate >/dev/null )

echo "==> building and installing (first run is slower; later runs reuse the build)"
# Capture the whole log: the presence of the app on the device is not proof the
# build succeeded, because a previous install is still there. An earlier version
# of this script printed "confirmed installed" after a failed build for exactly
# that reason.
BUILD_LOG=$(mktemp)
xcodebuild -project ios/CozmoCapture.xcodeproj \
           -scheme CozmoCapture \
           -destination "id=$UDID" \
           -allowProvisioningUpdates \
           build > "$BUILD_LOG" 2>&1 || true

grep -E "error:|BUILD (SUCCEEDED|FAILED)" "$BUILD_LOG" | head -8 || true

if ! grep -q "BUILD SUCCEEDED" "$BUILD_LOG"; then
  echo >&2
  echo "Build failed - the app on the device is unchanged." >&2
  echo "Full log: $BUILD_LOG" >&2
  exit 1
fi
rm -f "$BUILD_LOG"

if ! xcrun devicectl device info apps --device "$UDID" 2>/dev/null | grep -q com.cozmoai.capture; then
  echo "Build succeeded but the app is not on the device." >&2
  exit 1
fi
echo "==> confirmed installed: com.cozmoai.capture"

cat <<'DONE'

==> On the phone, once only:
    Settings > General > VPN & Device Management > trust the developer certificate

    Then open Cozmo Capture. The home screen names the device and shows a green
    tick beside every tier that handset can run.
DONE
