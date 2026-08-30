import Foundation

/// Remembers room names across captures.
///
/// Room identity is what makes two captures comparable. The repeatability gate
/// is defined as "two captures of the same room at the same tier", and the
/// stitched plan is scored on rooms being in the right place — both of which
/// need a room to mean the same thing twice.
///
/// Typing the name freehand each time does not give that. On the first two
/// multi-room captures of this property, "Bedroom 1" was typed in both and
/// referred to two different physical rooms, which would have silently merged
/// two rooms' photos had anything joined captures by name.
///
/// So names are offered back rather than retyped, and the order is
/// most-recent-first because a re-capture usually revisits what was just shot.
enum RoomNameStore {
    private static let key = "ai.cozmo.capture.recentRoomNames"
    private static let limit = 24

    static var recent: [String] {
        UserDefaults.standard.stringArray(forKey: key) ?? []
    }

    static func remember(_ name: String) {
        let trimmed = name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        var names = recent.filter { $0.caseInsensitiveCompare(trimmed) != .orderedSame }
        names.insert(trimmed, at: 0)
        UserDefaults.standard.set(Array(names.prefix(limit)), forKey: key)
    }

    /// Offered on a fresh install, so the first capture is not a blank page.
    static let suggestions = [
        "Hall", "Living Room", "Kitchen", "Bedroom 1", "Bedroom 2", "Bedroom 3",
        "Bathroom 1", "Bathroom 2", "Puja Room", "Balcony",
    ]
}
