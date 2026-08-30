import Foundation

/// On-disk layout of one capture. This is the contract between the app and the
/// pipeline, and the thing the grader will hand us at the walk-in test, so it
/// is versioned from the first commit.
///
///     capture_<yyyyMMdd_HHmmss>_<tier>/
///       manifest.json      always
///       rooms.json         always
///       photos/<nn>_<slug>/0001.jpg      photo tier
///       video.mov, video_meta.json       video tier
///       rgb/000001.jpg                   lidar tier
///       depth/000001.depth, 000001.conf  lidar tier
///       poses.jsonl, intrinsics.json     lidar tier
///       _reference/                      never in any sensor budget
///
struct CaptureBundle {
    static let schemaVersion = 1

    let id: String
    let tier: CaptureTier
    let root: URL

    var manifestURL: URL { root.appendingPathComponent("manifest.json") }
    var roomsURL: URL { root.appendingPathComponent("rooms.json") }
    var photosDir: URL { root.appendingPathComponent("photos", isDirectory: true) }
    var rgbDir: URL { root.appendingPathComponent("rgb", isDirectory: true) }
    var depthDir: URL { root.appendingPathComponent("depth", isDirectory: true) }
    var posesURL: URL { root.appendingPathComponent("poses.jsonl") }
    var intrinsicsURL: URL { root.appendingPathComponent("intrinsics.json") }
    var anchorsURL: URL { root.appendingPathComponent("anchors.json") }
    var videoURL: URL { root.appendingPathComponent("video.mov") }
    var videoMetaURL: URL { root.appendingPathComponent("video_meta.json") }
    var referenceDir: URL { root.appendingPathComponent("_reference", isDirectory: true) }

    static var capturesRoot: URL {
        let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        return docs.appendingPathComponent("Captures", isDirectory: true)
    }

    /// Creates the bundle directory and the subdirectories this tier needs.
    static func create(tier: CaptureTier) throws -> CaptureBundle {
        let stamp = DateFormatter.bundleStamp.string(from: Date())
        let id = "capture_\(stamp)_\(tier.rawValue)"
        let root = capturesRoot.appendingPathComponent(id, isDirectory: true)

        let fm = FileManager.default
        try fm.createDirectory(at: root, withIntermediateDirectories: true)
        try fm.createDirectory(at: root.appendingPathComponent("_reference"),
                               withIntermediateDirectories: true)
        switch tier {
        case .photo:
            try fm.createDirectory(at: root.appendingPathComponent("photos"),
                                   withIntermediateDirectories: true)
        case .video:
            break
        case .lidar:
            try fm.createDirectory(at: root.appendingPathComponent("rgb"),
                                   withIntermediateDirectories: true)
            try fm.createDirectory(at: root.appendingPathComponent("depth"),
                                   withIntermediateDirectories: true)
        }
        return CaptureBundle(id: id, tier: tier, root: root)
    }

    static func existing() -> [CaptureBundle] {
        let fm = FileManager.default
        guard let entries = try? fm.contentsOfDirectory(at: capturesRoot,
                                                        includingPropertiesForKeys: [.contentModificationDateKey],
                                                        options: [.skipsHiddenFiles]) else { return [] }
        return entries
            .filter { $0.hasDirectoryPath }
            .compactMap { url -> CaptureBundle? in
                guard let data = try? Data(contentsOf: url.appendingPathComponent("manifest.json")),
                      let manifest = try? JSONDecoder().decode(CaptureManifest.self, from: data)
                else { return nil }
                return CaptureBundle(id: manifest.captureId, tier: manifest.tier, root: url)
            }
            .sorted { $0.id > $1.id }
    }

    func sizeOnDisk() -> Int64 {
        guard let e = FileManager.default.enumerator(at: root,
                                                     includingPropertiesForKeys: [.fileSizeKey]) else { return 0 }
        var total: Int64 = 0
        for case let url as URL in e {
            total += Int64((try? url.resourceValues(forKeys: [.fileSizeKey]).fileSize) ?? 0)
        }
        return total
    }
}

// MARK: - Manifest

struct CaptureManifest: Codable {
    var schemaVersion: Int = CaptureBundle.schemaVersion
    var captureId: String
    var tier: CaptureTier
    var startedAt: Date
    var endedAt: Date?

    var appVersion: String
    var device: DeviceCapabilities

    /// Relative paths the pipeline may read at this tier. Enforced pipeline-side.
    var sensorBudget: [String]
    var budgetRationale: String

    /// `gravity` keeps +Y along the gravity vector, which is what makes ceiling
    /// height a direct measurement rather than a plane-fit by-product.
    var worldAlignment: String?

    var frameCount: Int = 0
    var photoCount: Int = 0
    var durationSeconds: Double?

    /// Free-text note the operator can add at the end of a capture.
    var operatorNote: String?
}

// MARK: - Rooms

/// A room boundary. On continuous tiers this is a timestamp marker inside one
/// session; on the photo tier it is a folder.
struct RoomMarker: Codable, Identifiable {
    var id: String { slug }
    var index: Int
    var name: String
    var slug: String
    /// Seconds since the start of the capture. Nil on the photo tier.
    var enteredAtSeconds: Double?
    /// First frame index attributed to this room. Nil on the photo tier.
    var firstFrameIndex: Int?
    var photoCount: Int = 0

    static func slugify(_ name: String) -> String {
        let lowered = name.lowercased()
        let mapped = lowered.map { ch -> Character in
            (ch.isLetter || ch.isNumber) ? ch : "_"
        }
        let collapsed = String(mapped)
            .split(separator: "_", omittingEmptySubsequences: true)
            .joined(separator: "_")
        return collapsed.isEmpty ? "room" : collapsed
    }

    /// Directory name used at the photo tier: `01_living_room`.
    var folderName: String { String(format: "%02d_%@", index, slug) }
}

struct RoomsFile: Codable {
    var schemaVersion: Int = CaptureBundle.schemaVersion
    var rooms: [RoomMarker]
}

extension DateFormatter {
    static let bundleStamp: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "yyyyMMdd_HHmmss"
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = TimeZone.current
        return f
    }()
}
