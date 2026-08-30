import ARKit
import Foundation
import UIKit

/// Probes what this specific handset can actually do, and emits the row that
/// belongs in the submitted device matrix.
///
/// Capability is decided by asking ARKit, not by matching model strings: a
/// model table goes stale, `supportsFrameSemantics` does not.
struct DeviceCapabilities: Codable {
    let modelIdentifier: String
    let marketingName: String
    let systemVersion: String

    let worldTrackingSupported: Bool
    let sceneDepthSupported: Bool
    let smoothedSceneDepthSupported: Bool
    let sceneMeshSupported: Bool

    let captureResolution: String
    let depthResolution: String?

    let supportedTiers: [CaptureTier]
    /// Tiers the spec allows but this handset cannot honestly run.
    let unsupportedTierReasons: [String: String]

    static func probe() -> DeviceCapabilities {
        let model = Self.modelIdentifier()
        let worldTracking = ARWorldTrackingConfiguration.isSupported
        let depth = ARWorldTrackingConfiguration.supportsFrameSemantics(.sceneDepth)
        let smoothed = ARWorldTrackingConfiguration.supportsFrameSemantics(.smoothedSceneDepth)
        let mesh = ARWorldTrackingConfiguration.supportsSceneReconstruction(.meshWithClassification)

        let format = ARWorldTrackingConfiguration.recommendedVideoFormatForHighResolutionFrameCapturing
            ?? ARWorldTrackingConfiguration.supportedVideoFormats.first
        let resolution = format.map { "\(Int($0.imageResolution.width))x\(Int($0.imageResolution.height))@\($0.framesPerSecond)" }
            ?? "unknown"

        var tiers: [CaptureTier] = [.photo]
        var reasons: [String: String] = [:]

        if worldTracking {
            tiers.append(.video)
        } else {
            reasons[CaptureTier.video.rawValue] = "ARWorldTrackingConfiguration unsupported on this device."
        }

        if depth {
            tiers.append(.lidar)
        } else {
            reasons[CaptureTier.lidar.rawValue] =
                "No rear LiDAR: ARKit reports sceneDepth unsupported. LiDAR tier requires a Pro-class iPhone."
        }

        return DeviceCapabilities(
            modelIdentifier: model,
            marketingName: Self.marketingName(for: model),
            systemVersion: UIDevice.current.systemVersion,
            worldTrackingSupported: worldTracking,
            sceneDepthSupported: depth,
            smoothedSceneDepthSupported: smoothed,
            sceneMeshSupported: mesh,
            captureResolution: resolution,
            depthResolution: depth ? "256x192" : nil,
            supportedTiers: tiers,
            unsupportedTierReasons: reasons
        )
    }

    func supports(_ tier: CaptureTier) -> Bool { supportedTiers.contains(tier) }

    // MARK: - Model identification

    static func modelIdentifier() -> String {
        // The simulator reports the host architecture, so prefer its own hint.
        if let simulated = ProcessInfo.processInfo.environment["SIMULATOR_MODEL_IDENTIFIER"] {
            return simulated
        }
        var systemInfo = utsname()
        uname(&systemInfo)
        return withUnsafeBytes(of: &systemInfo.machine) { raw in
            let bytes = raw.prefix { $0 != 0 }
            return String(decoding: bytes, as: UTF8.self)
        }
    }

    /// Only covers handsets in scope for this brief; anything else falls back
    /// to the raw identifier rather than guessing.
    private static let names: [String: String] = [
        "iPhone13,1": "iPhone 12 mini",   "iPhone13,2": "iPhone 12",
        "iPhone13,3": "iPhone 12 Pro",    "iPhone13,4": "iPhone 12 Pro Max",
        "iPhone14,4": "iPhone 13 mini",   "iPhone14,5": "iPhone 13",
        "iPhone14,2": "iPhone 13 Pro",    "iPhone14,3": "iPhone 13 Pro Max",
        "iPhone14,7": "iPhone 14",        "iPhone14,8": "iPhone 14 Plus",
        "iPhone15,2": "iPhone 14 Pro",    "iPhone15,3": "iPhone 14 Pro Max",
        "iPhone15,4": "iPhone 15",        "iPhone15,5": "iPhone 15 Plus",
        "iPhone16,1": "iPhone 15 Pro",    "iPhone16,2": "iPhone 15 Pro Max",
        "iPhone17,3": "iPhone 16",        "iPhone17,4": "iPhone 16 Plus",
        "iPhone17,1": "iPhone 16 Pro",    "iPhone17,2": "iPhone 16 Pro Max",
        "iPhone17,5": "iPhone 16e",
    ]

    static func marketingName(for identifier: String) -> String {
        names[identifier] ?? identifier
    }
}
