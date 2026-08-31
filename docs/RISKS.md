# Open risks

| # | Risk | Impact | Status |
|---|------|--------|--------|
| 1 | Only device paired is an **iPhone 13** — no rear LiDAR (Pro-only) and older than the iPhone 15 floor the spec sets for the photo/video tiers. Cannot develop, benchmark, or rehearse the LiDAR tier on it. | Blocks LiDAR-tier gates, the head-to-head (specified at LiDAR tier), and part of the walk-in test | **OPEN — needs a Pro-class iPhone 15/16/17** |
| 1b | **No Developer Disk Image for iOS 26.3.1 under Xcode 16.4.** Device is paired, wired, Developer Mode enabled; `xcodebuild -destination id=<device>` fails on the unmounted DDI. Blocks the debugger, not necessarily installation. | Cannot build-and-run from Xcode | **OPEN — update to Xcode 26.x, or install standalone via `devicectl` and run without the debugger** |
| 1c | **No Apple ID in Xcode's Accounts.** A codesigning identity exists in the keychain (`9VGYA957Q3`) but no signed-in account, so `-allowProvisioningUpdates` cannot create a profile for `com.cozmoai.capture`. | Nothing signed can be installed on any device | **OPEN — sign in: Xcode > Settings > Accounts** |
| 2 | **TestFlight unreachable before the deadline.** Apple Developer Program enrolment was submitted and is **Pending** as of 31 Aug 10:50 IST; Apple's approval typically takes 24-48 h and cannot be expedited. A Release archive builds cleanly and is ready to upload the moment enrolment completes. | Capture-route score (5%); install at the walk-in test needs Xcode and a cable rather than a link | **BLOCKED externally** — not a decision left unmade |
| 3 | Round 1 gate list is referenced ("Round 1 gates apply") but not in this document | Compliance matrix cannot be completed | OPEN — request the Round 1 spec |
| 4 | No deadline stated in the brief | Planning | OPEN — confirm |
