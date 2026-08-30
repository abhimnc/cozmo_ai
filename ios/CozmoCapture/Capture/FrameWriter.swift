import ARKit
import CoreImage
import Foundation
import UIKit

/// One row of `poses.jsonl`.
///
/// `transform` and `intrinsics` are flattened **column-major**, matching simd's
/// own memory order, so `numpy.array(t).reshape(4, 4).T` on the pipeline side
/// gives the conventional row-major matrix. Stated here because getting this
/// wrong is a silent transpose bug that shows up as mirrored floor plans.
struct PoseRecord: Codable {
    let index: Int
    let timestamp: Double        // ARFrame.timestamp, device uptime clock
    let tRel: Double             // seconds since capture start
    let transform: [Float]       // 16, column-major, world <- camera
    let intrinsics: [Float]      // 9, column-major, for imageWidth x imageHeight
    let imageWidth: Int
    let imageHeight: Int
    let trackingState: String
    let trackingReason: String?
    let ambientIntensity: Double?
    let roomIndex: Int?

    enum CodingKeys: String, CodingKey {
        case index, timestamp
        case tRel = "t_rel"
        case transform, intrinsics
        case imageWidth = "image_width"
        case imageHeight = "image_height"
        case trackingState = "tracking_state"
        case trackingReason = "tracking_reason"
        case ambientIntensity = "ambient_intensity"
        case roomIndex = "room_index"
    }
}

/// Serialised disk writer for a capture.
///
/// ARKit delivers frames on its own queue at 60 Hz; JPEG encoding is far slower
/// than that. Rather than block the session or grow memory without bound, the
/// writer keeps a bounded number of encodes in flight and *drops* frames past
/// that, counting the drops. The drop count goes into the manifest: a capture
/// that thinned out under load is something the pipeline and the error budget
/// need to know about, not something to hide.
final class FrameWriter {

    private let bundle: CaptureBundle
    private let queue = DispatchQueue(label: "ai.cozmo.capture.writer", qos: .utility)
    private let ciContext = CIContext(options: [.useSoftwareRenderer: false])

    private let maxInFlight = 6
    private var inFlight = 0
    private let lock = NSLock()

    private var poseHandle: FileHandle?

    private(set) var framesWritten = 0
    private(set) var framesDropped = 0
    private(set) var photosWritten = 0

    /// JPEG quality for pipeline-readable RGB. 0.9 rather than 0.8: compression
    /// artefacts at wall/floor boundaries cost us more in edge localisation
    /// than the extra megabytes cost us anywhere.
    private let jpegQuality: CGFloat = 0.9

    init(bundle: CaptureBundle) {
        self.bundle = bundle
    }

    // MARK: - Lifecycle

    func begin() throws {
        FileManager.default.createFile(atPath: bundle.posesURL.path, contents: nil)
        poseHandle = try FileHandle(forWritingTo: bundle.posesURL)
    }

    /// Blocks until every queued write has landed. Called before the manifest is
    /// finalised so the counts in it are true.
    func finish() {
        queue.sync { }
        try? poseHandle?.close()
        poseHandle = nil
    }

    // MARK: - Continuous tiers

    /// Enqueues one keyframe. Returns false if it was dropped under back-pressure.
    @discardableResult
    func write(frame: ARFrame, index: Int, tRel: Double, roomIndex: Int?, includeDepth: Bool) -> Bool {
        lock.lock()
        guard inFlight < maxInFlight else {
            framesDropped += 1
            lock.unlock()
            return false
        }
        inFlight += 1
        lock.unlock()

        // Copy everything needed off the ARFrame before returning: ARKit recycles
        // the underlying buffers as soon as the delegate call returns.
        let pixelBuffer = frame.capturedImage
        let image = CIImage(cvPixelBuffer: pixelBuffer)
        let width = CVPixelBufferGetWidth(pixelBuffer)
        let height = CVPixelBufferGetHeight(pixelBuffer)
        let depth = includeDepth ? frame.sceneDepth ?? frame.smoothedSceneDepth : nil
        let depthBlob = depth.map { Self.floatPlane($0.depthMap) }
        let confBlob = depth?.confidenceMap.map { Self.bytePlane($0) }

        let pose = PoseRecord(
            index: index,
            timestamp: frame.timestamp,
            tRel: tRel,
            transform: Self.flatten(frame.camera.transform),
            intrinsics: Self.flatten(frame.camera.intrinsics),
            imageWidth: width,
            imageHeight: height,
            trackingState: Self.describe(frame.camera.trackingState).0,
            trackingReason: Self.describe(frame.camera.trackingState).1,
            ambientIntensity: frame.lightEstimate.map { Double($0.ambientIntensity) },
            roomIndex: roomIndex
        )

        queue.async { [weak self] in
            guard let self else { return }
            defer {
                self.lock.lock(); self.inFlight -= 1; self.lock.unlock()
            }

            let stem = String(format: "%06d", index)
            if let cg = self.ciContext.createCGImage(image, from: image.extent),
               let jpeg = UIImage(cgImage: cg).jpegData(compressionQuality: self.jpegQuality) {
                try? jpeg.write(to: self.bundle.rgbDir.appendingPathComponent("\(stem).jpg"),
                                options: .atomic)
            }
            if let depthBlob {
                try? depthBlob.data.write(to: self.bundle.depthDir.appendingPathComponent("\(stem).depth"),
                                          options: .atomic)
            }
            if let confBlob {
                try? confBlob.data.write(to: self.bundle.depthDir.appendingPathComponent("\(stem).conf"),
                                         options: .atomic)
            }
            self.appendPose(pose)
            self.framesWritten += 1
        }
        return true
    }

    /// Poses at thin tiers go here: recorded for our own error analysis, outside
    /// the pipeline's sensor budget.
    func writeReferencePose(_ pose: PoseRecord) {
        queue.async { [weak self] in
            guard let self else { return }
            let url = self.bundle.referenceDir.appendingPathComponent("poses.jsonl")
            self.append(pose, to: url)
        }
    }

    // MARK: - Photo tier

    func writePhoto(_ data: Data, room: RoomMarker, sequence: Int) {
        queue.async { [weak self] in
            guard let self else { return }
            let dir = self.bundle.photosDir.appendingPathComponent(room.folderName, isDirectory: true)
            try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
            let url = dir.appendingPathComponent(String(format: "%04d.jpg", sequence))
            try? data.write(to: url, options: .atomic)
            self.photosWritten += 1
        }
    }

    // MARK: - JSON helpers

    private func appendPose(_ pose: PoseRecord) {
        guard let handle = poseHandle, var line = try? JSONEncoder().encode(pose) else { return }
        line.append(0x0A)
        try? handle.write(contentsOf: line)
    }

    private func append<T: Encodable>(_ value: T, to url: URL) {
        guard var line = try? JSONEncoder().encode(value) else { return }
        line.append(0x0A)
        if let handle = try? FileHandle(forWritingTo: url) {
            defer { try? handle.close() }
            _ = try? handle.seekToEnd()
            try? handle.write(contentsOf: line)
        } else {
            try? line.write(to: url, options: .atomic)
        }
    }

    func writeJSON<T: Encodable>(_ value: T, to url: URL) {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        encoder.dateEncodingStrategy = .iso8601
        if let data = try? encoder.encode(value) {
            try? data.write(to: url, options: .atomic)
        }
    }

    // MARK: - Pixel buffer extraction

    /// Copies a Float32 plane out row by row: `bytesPerRow` is padded for
    /// alignment and is not `width * 4`, so a flat memcpy would shear the map.
    private static func floatPlane(_ buffer: CVPixelBuffer) -> (data: Data, width: Int, height: Int) {
        CVPixelBufferLockBaseAddress(buffer, .readOnly)
        defer { CVPixelBufferUnlockBaseAddress(buffer, .readOnly) }
        let w = CVPixelBufferGetWidth(buffer)
        let h = CVPixelBufferGetHeight(buffer)
        let stride = CVPixelBufferGetBytesPerRow(buffer)
        var out = Data(capacity: w * h * 4)
        guard let base = CVPixelBufferGetBaseAddress(buffer) else { return (out, w, h) }
        for row in 0..<h {
            out.append(Data(bytes: base.advanced(by: row * stride), count: w * 4))
        }
        return (out, w, h)
    }

    private static func bytePlane(_ buffer: CVPixelBuffer) -> (data: Data, width: Int, height: Int) {
        CVPixelBufferLockBaseAddress(buffer, .readOnly)
        defer { CVPixelBufferUnlockBaseAddress(buffer, .readOnly) }
        let w = CVPixelBufferGetWidth(buffer)
        let h = CVPixelBufferGetHeight(buffer)
        let stride = CVPixelBufferGetBytesPerRow(buffer)
        var out = Data(capacity: w * h)
        guard let base = CVPixelBufferGetBaseAddress(buffer) else { return (out, w, h) }
        for row in 0..<h {
            out.append(Data(bytes: base.advanced(by: row * stride), count: w))
        }
        return (out, w, h)
    }

    // MARK: - simd

    static func flatten(_ m: simd_float4x4) -> [Float] {
        [m.columns.0, m.columns.1, m.columns.2, m.columns.3].flatMap { [$0.x, $0.y, $0.z, $0.w] }
    }

    static func flatten(_ m: simd_float3x3) -> [Float] {
        [m.columns.0, m.columns.1, m.columns.2].flatMap { [$0.x, $0.y, $0.z] }
    }

    static func describe(_ state: ARCamera.TrackingState) -> (String, String?) {
        switch state {
        case .notAvailable: return ("not_available", nil)
        case .normal: return ("normal", nil)
        case .limited(let reason):
            switch reason {
            case .initializing: return ("limited", "initializing")
            case .excessiveMotion: return ("limited", "excessive_motion")
            case .insufficientFeatures: return ("limited", "insufficient_features")
            case .relocalizing: return ("limited", "relocalizing")
            @unknown default: return ("limited", "unknown")
            }
        }
    }
}
