# Capture protocol — one page

**Route 1.** One app, three tiers, no third-party tools. The person capturing
does not need to know which tier the pipeline prefers; they tap the tier they
were asked for and follow the screen.

## Install (about 5 minutes, cable required)

**TestFlight is not available.** Apple Developer Program enrolment was submitted
and remains Pending; a Release archive builds and signs, and the moment enrolment
clears the upload is one Xcode step away. Until then, installation is by cable:

1. Connect the iPhone to a Mac with Xcode.
2. From `ios/`, run:
   `xcodebuild -project CozmoCapture.xcodeproj -scheme CozmoCapture -destination 'id=<udid>' -allowProvisioningUpdates build`
   (`xcrun devicectl list devices` gives the UDID.)
3. On the phone: Settings → General → VPN & Device Management → trust the
   developer certificate.
4. Open the app. Allow camera access when asked.
5. The home screen names your device and shows a green tick beside every tier
   this handset can run. If a tier is greyed out, the app says why.

## Photo tier

1. Tap **Photos**.
2. Tap **Next room**, type the room name (e.g. `Living Room`), tap Add.
3. Take **2 to 8 photos** of that room, standing in different corners.
   Each photo should show where the walls meet the floor.
4. Repeat from step 2 for every room, including hallways.
5. Tap **Finish** → **Save capture**.

Avoid: shooting all photos from one spot, framing only the middle of a wall,
photographing a mirror head-on.

## Video tier

1. Tap **Video walkthrough**.
2. Stand in a doorway. Hold the phone upright at chest height.
3. Walk the whole property in **one continuous take**, slowly — about one step
   per second. Do not stop recording between rooms.
4. Tap **Mark room** each time you walk into a new room, and name it.
5. Finish where you started. Tap **Finish** → **Save capture**.

Avoid: fast panning, walking backwards, covering the camera, stopping and
restarting the recording.

## LiDAR tier (Pro devices only)

Same walk as the video tier, plus: sweep the phone slowly up and down each wall
so the depth sensor sees floor-to-ceiling. Finish where you started so the scan
can close the loop.

## Handing the capture to the pipeline

- **Saved captures** → **Export .zip** → AirDrop to the laptop, or
- Plug the phone into the laptop and drag the capture folder out of the Files
  app (the app publishes its captures there; no network needed).

Then, on the laptop:

```
cozmo run <path-to-capture>
```

One command. Everything else is automatic.

## What good looks like

The app shows a tracking indicator while you capture. If it turns orange
(`excessive_motion`, `insufficient_features`) slow down and point at a
textured surface until it goes green again. It also counts dropped frames —
a handful is normal, hundreds means the walk was too fast.
