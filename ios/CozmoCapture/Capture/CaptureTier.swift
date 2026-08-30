import Foundation

/// The three mandatory input tiers.
///
/// The tier is not a label on a richer capture — it decides what actually
/// reaches disk in the pipeline-readable part of the bundle. Everything the
/// device *could* have recorded at a thinner tier is still written, but under
/// `_reference/`, which the pipeline refuses to open for that tier. That is
/// what lets us claim honestly that the photo tier is a photo tier.
enum CaptureTier: String, Codable, CaseIterable, Identifiable {
    case photo
    case video
    case lidar

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .photo: return "Photos"
        case .video: return "Video walkthrough"
        case .lidar: return "LiDAR scan"
        }
    }

    var shortSubtitle: String {
        switch self {
        case .photo: return "2–8 stills per room"
        case .video: return "One continuous clip"
        case .lidar: return "Depth + poses, Pro devices"
        }
    }

    /// What a non-engineer is told to do. Mirrors the one-page protocol.
    var instructions: String {
        switch self {
        case .photo:
            return """
            Name the room, then take 2 to 8 photos of it from different corners.
            Stand back far enough to see where the walls meet the floor.
            Then tap Next room and repeat, until every room is done.
            """
        case .video:
            return """
            Start in a doorway. Walk slowly through the whole property in one
            continuous take, holding the phone upright at chest height.
            Tap the room button each time you enter a new room.
            Keep walking until you are back where you started, then stop.
            """
        case .lidar:
            return """
            Start in a doorway. Walk slowly through the whole property, sweeping
            the phone across each wall from floor to ceiling.
            Tap the room button each time you enter a new room.
            Finish where you started so the scan can close the loop.
            """
        }
    }

    /// Paths inside the bundle the pipeline may read at this tier.
    /// Written into the manifest so the rule is enforced on the pipeline side
    /// rather than merely promised in a report.
    var sensorBudget: [String] {
        switch self {
        case .photo:
            return ["manifest.json", "rooms.json", "photos/**"]
        case .video:
            return ["manifest.json", "rooms.json", "video.mov", "video_meta.json"]
        case .lidar:
            return ["manifest.json", "rooms.json", "rgb/**", "depth/**",
                    "poses.jsonl", "intrinsics.json", "anchors.json"]
        }
    }

    /// Human-readable justification, carried into the technical report.
    var budgetRationale: String {
        switch self {
        case .photo:
            return "Stills only. No depth, no poses, no frame ordering guarantees."
        case .video:
            return "RGB frames only. Poses are recorded but withheld — the pipeline must recover its own motion."
        case .lidar:
            return "Depth, poses and intrinsics, as the spec defines this tier."
        }
    }

    /// Continuous tiers share one coordinate frame across the whole property;
    /// the photo tier has no continuity at all and arrives as per-room folders.
    var isContinuous: Bool { self != .photo }
}
