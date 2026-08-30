import ARKit
import SceneKit
import SwiftUI

/// Live camera preview bound to the controller's session.
///
/// The preview renders no overlays or virtual content: the operator is judging
/// coverage of real walls, and anything drawn on top competes with that.
struct ARPreview: UIViewRepresentable {
    let session: ARSession

    func makeUIView(context: Context) -> ARSCNView {
        let view = ARSCNView(frame: .zero)
        view.session = session
        view.automaticallyUpdatesLighting = true
        view.rendersContinuously = true
        return view
    }

    func updateUIView(_ uiView: ARSCNView, context: Context) {}
}
