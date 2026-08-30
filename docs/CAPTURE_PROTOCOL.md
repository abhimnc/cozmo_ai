# Capture protocol — one page

**Route 1.** One app, three tiers, no third-party tools. The person capturing
does not need to know which tier the pipeline prefers; they tap the tier they
were asked for and follow the screen.

## Install (target: under 10 minutes)

1. Open the TestFlight invitation link on the iPhone. Install **Cozmo Capture**.
2. Open the app. Allow camera access when asked.
3. The home screen names your device and shows a green tick beside every tier
   this handset can run. If a tier is greyed out, the app says why.

*Fallback with no TestFlight:* connect the iPhone by cable, `xcodebuild ... install`
from `ios/`, then Settings → General → VPN & Device Management → trust the
developer certificate. Under two minutes with the cable already in hand.

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
