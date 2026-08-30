import SwiftUI

@main
struct CozmoCaptureApp: App {
    @StateObject private var controller = CaptureController()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(controller)
                .preferredColorScheme(.dark)
                .onAppear { CaptureBundle.purgeIncomplete() }
        }
    }
}
