import SwiftUI
import UniformTypeIdentifiers

/// Saved captures, with a one-tap zip export.
///
/// Getting a capture off the phone is on the critical path of the walk-in test,
/// so there are two independent routes: AirDrop/share from here, and the Files
/// app (the app declares `UIFileSharingEnabled`, so a laptop over cable works
/// even with no network).
struct BundleListView: View {
    @State private var bundles: [CaptureBundle] = []
    @State private var exportURL: URL?
    @State private var exporting = false

    var body: some View {
        List {
            if bundles.isEmpty {
                Text("No captures yet.").foregroundStyle(.secondary)
            }
            ForEach(bundles, id: \.id) { bundle in
                VStack(alignment: .leading, spacing: 4) {
                    Text(bundle.id).font(.system(.footnote, design: .monospaced))
                    HStack(spacing: 10) {
                        Label(bundle.tier.displayName, systemImage: "square.stack.3d.up")
                        Text(byteString(bundle.sizeOnDisk()))
                    }
                    .font(.caption).foregroundStyle(.secondary)
                    Button {
                        export(bundle)
                    } label: {
                        Label("Export .zip", systemImage: "square.and.arrow.up")
                    }
                    .buttonStyle(.bordered)
                    .disabled(exporting)
                }
                .padding(.vertical, 4)
            }
            .onDelete { indexes in
                for i in indexes { try? FileManager.default.removeItem(at: bundles[i].root) }
                bundles = CaptureBundle.existing()
            }
        }
        .navigationTitle("Saved captures")
        .onAppear { bundles = CaptureBundle.existing() }
        .sheet(item: Binding(get: { exportURL.map(ShareItem.init) },
                             set: { _ in exportURL = nil })) { item in
            ShareSheet(url: item.url)
        }
    }

    private func export(_ bundle: CaptureBundle) {
        exporting = true
        DispatchQueue.global(qos: .userInitiated).async {
            let url = zip(bundle)
            DispatchQueue.main.async {
                exporting = false
                exportURL = url
            }
        }
    }

    /// `NSFileCoordinator`'s `.forUploading` option produces a zip of a
    /// directory without pulling in a third-party archiver.
    private func zip(_ bundle: CaptureBundle) -> URL? {
        var error: NSError?
        var result: URL?
        NSFileCoordinator().coordinate(readingItemAt: bundle.root,
                                       options: [.forUploading],
                                       error: &error) { zipped in
            let dest = FileManager.default.temporaryDirectory
                .appendingPathComponent("\(bundle.id).zip")
            try? FileManager.default.removeItem(at: dest)
            try? FileManager.default.copyItem(at: zipped, to: dest)
            result = dest
        }
        return result
    }

    private func byteString(_ bytes: Int64) -> String {
        ByteCountFormatter.string(fromByteCount: bytes, countStyle: .file)
    }
}

private struct ShareItem: Identifiable {
    let url: URL
    var id: String { url.path }
}

private struct ShareSheet: UIViewControllerRepresentable {
    let url: URL
    func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: [url], applicationActivities: nil)
    }
    func updateUIViewController(_ vc: UIActivityViewController, context: Context) {}
}
