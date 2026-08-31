# Installing Cozmo Capture on a new iPhone from a new Mac

Two scenarios, and they take very different amounts of time. Read the first
paragraph of each before choosing.

---

## Scenario A — our Mac, your iPhone (the defense case)

**About 2 minutes.** Everything is already installed and signed in; only the
phone is new.

1. Connect the iPhone by cable. Unlock it. Tap **Trust** if asked.
2. On the phone: **Settings → Privacy & Security → Developer Mode → on**.
   The phone restarts and asks you to confirm after unlocking.
3. On the Mac: `./scripts/install_on_device.sh`
   *Measured at 11 seconds cold on an M4 MacBook Air.*
4. On the phone: **Settings → General → VPN & Device Management** → tap the
   developer certificate → **Trust**.
5. Open **Cozmo Capture**. Allow camera access.

The home screen names the device and shows a green tick beside every tier that
handset can run, with a written reason beside any it cannot.

**This is the route to use at the defense.** The rest of this page is for
rebuilding from nothing.

---

## Scenario B — a genuinely new Mac

**Realistically 60–90 minutes, and almost all of it is downloading Xcode.**
That is not something the project can shorten; Xcode is ~8 GB and Apple's
download speed governs. Budget for it rather than being surprised.

### 1. Xcode (~40–70 min, mostly download)

Install **Xcode** from the Mac App Store. It must be new enough for the iOS
version on the phone — an Xcode that predates the phone's iOS cannot deploy to
it at all.

Then, in Terminal:

```bash
sudo xcodebuild -license accept
sudo xcode-select -s /Applications/Xcode.app/Contents/Developer
```

### 2. Sign in to Xcode (~2 min)

**Xcode → Settings (⌘,) → Accounts → `+` → Apple ID.** A free Apple ID is
sufficient for a dev build. No paid membership is required.

### 3. Tooling and repo (~3 min)

```bash
brew install xcodegen
git clone https://github.com/abhimnc/cozmo_ai && cd cozmo_ai
```

### 4. Set the signing team (~1 min)

```bash
cd ios
cp Signing.local.xcconfig.example Signing.local.xcconfig
security find-identity -v -p codesigning     # the 10 characters in parentheses
```

Put that team ID into `Signing.local.xcconfig`. Leaving it empty also works —
Xcode then asks which team to use on first open.

### 5. **Change the bundle identifier** (~1 min) — easy to miss

`com.cozmoai.capture` is registered to this project's team. **A different Apple
ID cannot use it**, and the failure message ("bundle identifier is not
available") does not make the cause obvious.

In `ios/project.yml`, change:

```yaml
PRODUCT_BUNDLE_IDENTIFIER: com.cozmoai.capture
```

to something unique to you, e.g. `com.yourname.cozmocapture`. Then
`cd ios && xcodegen generate`.

### 6. Prepare the phone (~3 min, includes a restart)

- **Settings → Privacy & Security → Developer Mode → on**, then restart and
  confirm. *(This entry only appears once the phone has been connected to a Mac
  running Xcode at least once.)*
- Connect by cable, unlock, tap **Trust This Computer**.

### 7. Install (~1 min)

```bash
./scripts/install_on_device.sh
```

Then trust the certificate on the phone: **Settings → General → VPN & Device
Management** → the developer certificate → **Trust**.

---

## Limits of a free Apple ID

Worth knowing before relying on it:

| | Free account | Paid (£79/$99 a year) |
|---|---|---|
| App expires after | **7 days** | 1 year |
| Apps installed at once | 3 | unlimited |
| TestFlight | no | yes |

The 7-day expiry stops the app *launching*; it does not delete captures already
on the phone. Re-running the install script restores it.

*TestFlight is not offered here because Apple Developer Program enrolment for
this project was submitted on 31 Aug 2026 and remains Pending. The brief accepts
"a TestFlight build **or** a dev build", and this is the dev build.*

---

## When it does not work

| Symptom | Cause | Fix |
|---|---|---|
| "Unable to find a destination matching…" | Phone locked, asleep, or on a charge-only cable | Unlock; use a data cable |
| "bundle identifier is not available" | Bundle ID belongs to another team | Step 5 above |
| "No Account for Team …" | No Apple ID in Xcode | Step 2 above |
| Device shows `unavailable` in `xcrun devicectl list devices` | Not trusted, or Developer Mode off | Step 6 above |
| App installs but will not open | Certificate not trusted, or 7 days elapsed | Trust it; or re-run the script |
| "…is not supported by this version of Xcode" | Xcode older than the phone's iOS | Update Xcode |

`./scripts/install_on_device.sh` checks for the first and fourth of these and
prints what to do, rather than surfacing the raw build error.
