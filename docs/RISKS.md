# Open risks

| # | Risk | Impact | Status |
|---|------|--------|--------|
| 1 | Only device paired is an **iPhone 13** — no rear LiDAR (Pro-only) and older than the iPhone 15 floor the spec sets for the photo/video tiers. Cannot develop, benchmark, or rehearse the LiDAR tier on it. | Blocks LiDAR-tier gates, the head-to-head (specified at LiDAR tier), and part of the walk-in test | **OPEN — needs a Pro-class iPhone 15/16/17** |
| 1b | **No Developer Disk Image for iOS 26.3.1 under Xcode 16.4.** Device is paired, wired, Developer Mode enabled; `xcodebuild -destination id=<device>` fails on the unmounted DDI. Blocks the debugger, not necessarily installation. | Cannot build-and-run from Xcode | **OPEN — update to Xcode 26.x, or install standalone via `devicectl` and run without the debugger** |
| 1c | **No Apple ID in Xcode's Accounts.** A codesigning identity exists in the keychain (`9VGYA957Q3`) but no signed-in account, so `-allowProvisioningUpdates` cannot create a profile for `com.cozmoai.capture`. | Nothing signed can be installed on any device | **OPEN — sign in: Xcode > Settings > Accounts** |
| 2 | ~~TestFlight unavailable~~ **Resolved 1 Sep 2026.** Build uploaded to App Store Connect (delivery `9e1e5685-64d8-45a3-a686-231f3e0ff1f9`), validated with no errors. Required a chain: Developer Program enrolment, an Apple Distribution certificate, macOS 15.3 → 26.6.2, Xcode 16.4 → 26.6, and the iOS 26.5 platform. | — | **RESOLVED** |
| 3 | Round 1 gate list is referenced ("Round 1 gates apply") but not in this document | Compliance matrix cannot be completed | OPEN — request the Round 1 spec |
| 4 | No deadline stated in the brief | Planning | OPEN — confirm |
