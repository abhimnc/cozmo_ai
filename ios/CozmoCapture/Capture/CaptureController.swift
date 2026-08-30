import ARKit
import Combine
import Foundation
import UIKit

/// Drives one capture from start to finished bundle.
///
/// One ARSession serves all three tiers. What differs is only what reaches the
/// pipeline-readable part of the bundle:
///
/// - LiDAR: selected keyframes with depth, plus poses and intrinsics.
/// - Video: a single continuous clip. Poses are recorded to `_reference/` and
///   withheld, because the spec defines poses as a LiDAR-tier signal and a
///   video tier that quietly consumed ARKit's poses would not be a video tier.
/// - Photo: high-resolution stills in per-room folders, nothing else.
///
/// The whole property is captured in one session on the continuous tiers, so
/// every room shares a coordinate frame and stitching starts from real
/// adjacency rather than from guesswork.
final class CaptureController: NSObject, ObservableObject, ARSessionDelegate {

    enum Phase: Equatable {
        case idle
        case running(CaptureTier)
        case finishing
        case finished(String)   // bundle id

        var isRunning: Bool { if case .running = self { return true }; return false }
    }

    // MARK: Published state

    @Published private(set) var phase: Phase = .idle
    @Published private(set) var rooms: [RoomMarker] = []
    @Published private(set) var framesWritten = 0
    @Published private(set) var framesDropped = 0
    @Published private(set) var trackingLabel = "starting"
    @Published private(set) var trackingIsHealthy = false
    @Published private(set) var elapsed: TimeInterval = 0
    @Published private(set) var lastError: String?

    let capabilities = DeviceCapabilities.probe()
    let session = ARSession()

    // MARK: Internals

    private let sessionQueue = DispatchQueue(label: "ai.cozmo.capture.session")
    private var bundle: CaptureBundle?
    private var writer: FrameWriter?
    private var videoRecorder: VideoRecorder?
    private var tier: CaptureTier = .lidar

    private var startedAt = Date()
    private var sessionEpoch: TimeInterval?
    private var frameIndex = 0
    private var lastKeyframePose: simd_float4x4?
    private var lastKeyframeTime: TimeInterval = -.infinity
    private var uiTick: TimeInterval = 0
    private var timer: Timer?

    /// Keyframe policy. Tuned for wall coverage rather than for smooth video:
    /// a 5 cm / 5° gate gives usable stereo baselines, and the 1 s floor keeps
    /// writing while the operator stands still reading a wall, which is exactly
    /// when repeated observations of the same surface are cheapest.
    private let minTranslation: Float = 0.05
    private let minRotationRadians: Float = 5 * .pi / 180
    private let maxKeyframeRate: TimeInterval = 1.0 / 10.0
    private let forcedKeyframeInterval: TimeInterval = 1.0

    // MARK: - Start

    func start(tier: CaptureTier) {
        guard capabilities.supports(tier) else {
            lastError = capabilities.unsupportedTierReasons[tier.rawValue]
                ?? "This device cannot run the \(tier.displayName) tier."
            return
        }
        do {
            let bundle = try CaptureBundle.create(tier: tier)
            let writer = FrameWriter(bundle: bundle)
            if tier == .lidar { try writer.begin() }

            self.bundle = bundle
            self.writer = writer
            self.tier = tier
            self.rooms = []
            self.frameIndex = 0
            self.framesWritten = 0
            self.framesDropped = 0
            self.lastKeyframePose = nil
            self.lastKeyframeTime = -.infinity
            self.sessionEpoch = nil
            self.startedAt = Date()
            self.lastError = nil

            session.delegate = self
            session.delegateQueue = sessionQueue
            session.run(configuration(for: tier), options: [.resetTracking, .removeExistingAnchors])

            phase = .running(tier)
            startClock()
        } catch {
            lastError = "Could not start capture: \(error.localizedDescription)"
        }
    }

    private func configuration(for tier: CaptureTier) -> ARWorldTrackingConfiguration {
        let config = ARWorldTrackingConfiguration()

        // Gravity alignment puts +Y along the gravity vector. Ceiling height then
        // falls out of a Y-extent rather than out of fitting two planes and
        // hoping they are parallel — which is most of why the 1.5 cm gate is
        // reachable at all. Heading is deliberately not used: indoor magnetometer
        // readings are noisy and we need no absolute bearing.
        config.worldAlignment = .gravity
        config.planeDetection = [.horizontal, .vertical]
        config.isAutoFocusEnabled = true
        config.environmentTexturing = .none

        if tier == .lidar {
            if ARWorldTrackingConfiguration.supportsFrameSemantics(.sceneDepth) {
                config.frameSemantics.insert(.sceneDepth)
            }
            if ARWorldTrackingConfiguration.supportsFrameSemantics(.smoothedSceneDepth) {
                config.frameSemantics.insert(.smoothedSceneDepth)
            }
            if ARWorldTrackingConfiguration.supportsSceneReconstruction(.meshWithClassification) {
                config.sceneReconstruction = .meshWithClassification
            }
        }
        if tier == .photo,
           let hiRes = ARWorldTrackingConfiguration.recommendedVideoFormatForHighResolutionFrameCapturing {
            config.videoFormat = hiRes
        }
        return config
    }

    // MARK: - Rooms

    func markRoom(named name: String) {
        let trimmed = name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        let marker = RoomMarker(
            index: rooms.count + 1,
            name: trimmed,
            slug: RoomMarker.slugify(trimmed),
            enteredAtSeconds: tier.isContinuous ? elapsed : nil,
            firstFrameIndex: tier.isContinuous ? frameIndex : nil,
            photoCount: 0
        )
        rooms.append(marker)
    }

    var currentRoom: RoomMarker? { rooms.last }

    // MARK: - Photo tier

    func capturePhoto() {
        guard tier == .photo, let writer, var room = rooms.last else {
            lastError = "Name the room before taking photos."
            return
        }
        let sequence = room.photoCount + 1
        session.captureHighResolutionFrame { [weak self] frame, error in
            guard let self else { return }
            guard let frame else {
                DispatchQueue.main.async {
                    self.lastError = "Photo failed: \(error?.localizedDescription ?? "unknown")"
                }
                return
            }
            let image = CIImage(cvPixelBuffer: frame.capturedImage)
            let context = CIContext()
            guard let cg = context.createCGImage(image, from: image.extent),
                  let jpeg = UIImage(cgImage: cg, scale: 1, orientation: .right)
                      .jpegData(compressionQuality: 0.95) else { return }

            writer.writePhoto(jpeg, room: room, sequence: sequence)
            // Recorded, but out of the photo tier's sensor budget: this is how we
            // measure what the photo path gave up, not something it may consume.
            writer.writeReferencePose(PoseRecord(
                index: sequence,
                timestamp: frame.timestamp,
                tRel: self.elapsed,
                transform: FrameWriter.flatten(frame.camera.transform),
                intrinsics: FrameWriter.flatten(frame.camera.intrinsics),
                imageWidth: CVPixelBufferGetWidth(frame.capturedImage),
                imageHeight: CVPixelBufferGetHeight(frame.capturedImage),
                trackingState: FrameWriter.describe(frame.camera.trackingState).0,
                trackingReason: FrameWriter.describe(frame.camera.trackingState).1,
                ambientIntensity: frame.lightEstimate.map { Double($0.ambientIntensity) },
                roomIndex: room.index))

            DispatchQueue.main.async {
                room.photoCount = sequence
                if let i = self.rooms.firstIndex(where: { $0.index == room.index }) {
                    self.rooms[i].photoCount = sequence
                }
            }
        }
    }

    // MARK: - ARSessionDelegate

    func session(_ session: ARSession, didUpdate frame: ARFrame) {
        if sessionEpoch == nil { sessionEpoch = frame.timestamp }
        let tRel = frame.timestamp - (sessionEpoch ?? frame.timestamp)

        switch tier {
        case .photo:
            break

        case .video:
            if videoRecorder == nil, let bundle {
                let recorder = VideoRecorder()
                let w = CVPixelBufferGetWidth(frame.capturedImage)
                let h = CVPixelBufferGetHeight(frame.capturedImage)
                try? recorder.start(url: bundle.videoURL, width: w, height: h)
                videoRecorder = recorder
            }
            videoRecorder?.append(frame.capturedImage, timestamp: tRel)
            if shouldKeyframe(frame, tRel: tRel) {
                writer?.writeReferencePose(referencePose(from: frame, tRel: tRel))
            }

        case .lidar:
            guard shouldKeyframe(frame, tRel: tRel) else { break }
            let accepted = writer?.write(frame: frame,
                                         index: frameIndex,
                                         tRel: tRel,
                                         roomIndex: rooms.last?.index,
                                         includeDepth: true) ?? false
            if accepted { frameIndex += 1 }
        }

        publishThrottled(frame: frame, tRel: tRel)
    }

    func session(_ session: ARSession, didFailWithError error: Error) {
        DispatchQueue.main.async { self.lastError = error.localizedDescription }
    }

    // MARK: - Keyframe selection

    private func shouldKeyframe(_ frame: ARFrame, tRel: TimeInterval) -> Bool {
        guard tRel - lastKeyframeTime >= maxKeyframeRate else { return false }
        let pose = frame.camera.transform
        guard let last = lastKeyframePose else {
            lastKeyframePose = pose
            lastKeyframeTime = tRel
            return true
        }
        let moved = simd_distance(pose.columns.3, last.columns.3)
        let rotated = Self.angle(between: last, and: pose)
        let stale = tRel - lastKeyframeTime >= forcedKeyframeInterval
        guard moved >= minTranslation || rotated >= minRotationRadians || stale else { return false }
        lastKeyframePose = pose
        lastKeyframeTime = tRel
        return true
    }

    /// Geodesic angle between two rotations, via the trace of Ra^T Rb.
    private static func angle(between a: simd_float4x4, and b: simd_float4x4) -> Float {
        let ra = simd_float3x3(simd_make_float3(a.columns.0), simd_make_float3(a.columns.1), simd_make_float3(a.columns.2))
        let rb = simd_float3x3(simd_make_float3(b.columns.0), simd_make_float3(b.columns.1), simd_make_float3(b.columns.2))
        let r = ra.transpose * rb
        let trace = r.columns.0.x + r.columns.1.y + r.columns.2.z
        return acos(min(1, max(-1, (trace - 1) / 2)))
    }

    private func referencePose(from frame: ARFrame, tRel: TimeInterval) -> PoseRecord {
        PoseRecord(index: frameIndex,
                   timestamp: frame.timestamp,
                   tRel: tRel,
                   transform: FrameWriter.flatten(frame.camera.transform),
                   intrinsics: FrameWriter.flatten(frame.camera.intrinsics),
                   imageWidth: CVPixelBufferGetWidth(frame.capturedImage),
                   imageHeight: CVPixelBufferGetHeight(frame.capturedImage),
                   trackingState: FrameWriter.describe(frame.camera.trackingState).0,
                   trackingReason: FrameWriter.describe(frame.camera.trackingState).1,
                   ambientIntensity: frame.lightEstimate.map { Double($0.ambientIntensity) },
                   roomIndex: rooms.last?.index)
    }

    // MARK: - UI plumbing

    private func publishThrottled(frame: ARFrame, tRel: TimeInterval) {
        guard tRel - uiTick > 0.2 else { return }
        uiTick = tRel
        let (state, reason) = FrameWriter.describe(frame.camera.trackingState)
        let written = writer?.framesWritten ?? 0
        let dropped = writer?.framesDropped ?? 0
        DispatchQueue.main.async {
            self.trackingIsHealthy = (state == "normal")
            self.trackingLabel = reason.map { "\(state) · \($0)" } ?? state
            self.framesWritten = written
            self.framesDropped = dropped
        }
    }

    private func startClock() {
        timer?.invalidate()
        let started = Date()
        timer = Timer.scheduledTimer(withTimeInterval: 0.25, repeats: true) { [weak self] _ in
            self?.elapsed = Date().timeIntervalSince(started)
        }
    }

    // MARK: - Finish

    func finish(note: String?, completion: @escaping (CaptureBundle?) -> Void) {
        guard let bundle, let writer else { completion(nil); return }
        phase = .finishing
        timer?.invalidate()

        let anchors = session.currentFrame?.anchors ?? []
        let referenceCamera = session.currentFrame?.camera
        session.pause()

        let wrapUp: (Double?) -> Void = { [weak self] duration in
            guard let self else { return }
            writer.finish()

            writer.writeJSON(RoomsFile(rooms: self.rooms), to: bundle.roomsURL)

            if self.tier == .lidar, let camera = referenceCamera {
                writer.writeJSON(IntrinsicsFile(camera: camera), to: bundle.intrinsicsURL)
                writer.writeJSON(PlaneAnchorFile(anchors: anchors), to: bundle.anchorsURL)
            } else {
                writer.writeJSON(PlaneAnchorFile(anchors: anchors),
                                 to: bundle.referenceDir.appendingPathComponent("planes.json"))
            }
            if self.tier == .video, let duration {
                writer.writeJSON(VideoMeta(width: Int(self.videoRecorder?.size.width ?? 0),
                                           height: Int(self.videoRecorder?.size.height ?? 0),
                                           frameCount: self.videoRecorder?.frameCount ?? 0,
                                           durationSeconds: duration),
                                 to: bundle.videoMetaURL)
            }

            var manifest = CaptureManifest(
                captureId: bundle.id,
                tier: self.tier,
                startedAt: self.startedAt,
                endedAt: Date(),
                appVersion: Bundle.main.appVersionString,
                device: self.capabilities,
                sensorBudget: self.tier.sensorBudget,
                budgetRationale: self.tier.budgetRationale,
                worldAlignment: "gravity",
                operatorNote: note)
            manifest.frameCount = writer.framesWritten
            manifest.photoCount = writer.photosWritten
            manifest.durationSeconds = duration ?? Date().timeIntervalSince(self.startedAt)
            writer.writeJSON(manifest, to: bundle.manifestURL)

            DispatchQueue.main.async {
                self.phase = .finished(bundle.id)
                self.bundle = nil
                self.writer = nil
                self.videoRecorder = nil
                completion(bundle)
            }
        }

        if let recorder = videoRecorder, recorder.isRecording {
            recorder.finish { duration in wrapUp(duration) }
        } else {
            wrapUp(nil)
        }
    }

    func reset() {
        phase = .idle
        rooms = []
        lastError = nil
        elapsed = 0
    }
}

// MARK: - Side files

struct IntrinsicsFile: Codable {
    var schemaVersion: Int = CaptureBundle.schemaVersion
    /// Column-major 3x3, for `imageWidth` x `imageHeight`.
    var intrinsics: [Float]
    var imageWidth: Int
    var imageHeight: Int
    /// ARKit hands back rectified frames, so there is no distortion model to
    /// apply downstream. Recorded explicitly so nobody re-derives one later.
    var distortionModel: String = "none_arkit_rectified"

    init(camera: ARCamera) {
        self.intrinsics = FrameWriter.flatten(camera.intrinsics)
        self.imageWidth = Int(camera.imageResolution.width)
        self.imageHeight = Int(camera.imageResolution.height)
    }
}

struct PlaneAnchorFile: Codable {
    struct Plane: Codable {
        let identifier: String
        let alignment: String
        let classification: String
        let transform: [Float]
        let centre: [Float]
        let extentX: Float
        let extentZ: Float
    }
    var schemaVersion: Int = CaptureBundle.schemaVersion
    var planes: [Plane]

    init(anchors: [ARAnchor]) {
        planes = anchors.compactMap { anchor in
            guard let p = anchor as? ARPlaneAnchor else { return nil }
            return Plane(identifier: p.identifier.uuidString,
                         alignment: p.alignment == .horizontal ? "horizontal" : "vertical",
                         classification: "\(p.classification)",
                         transform: FrameWriter.flatten(p.transform),
                         centre: [p.center.x, p.center.y, p.center.z],
                         extentX: p.planeExtent.width,
                         extentZ: p.planeExtent.height)
        }
    }
}

struct VideoMeta: Codable {
    var schemaVersion: Int = CaptureBundle.schemaVersion
    var width: Int
    var height: Int
    var frameCount: Int
    var durationSeconds: Double
}

extension Bundle {
    var appVersionString: String {
        let v = infoDictionary?["CFBundleShortVersionString"] as? String ?? "0"
        let b = infoDictionary?["CFBundleVersion"] as? String ?? "0"
        return "\(v) (\(b))"
    }
}
