import SwiftUI

struct RootView: View {
    @EnvironmentObject private var controller: CaptureController
    @State private var launchTier: CaptureTier?

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    deviceCard
                    Text("Choose a capture tier")
                        .font(.headline)
                    ForEach(CaptureTier.allCases) { tier in
                        tierButton(tier)
                    }
                    NavigationLink {
                        BundleListView()
                    } label: {
                        Label("Saved captures", systemImage: "folder")
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding()
                            .background(Color.white.opacity(0.06), in: RoundedRectangle(cornerRadius: 12))
                    }
                    .buttonStyle(.plain)
                }
                .padding()
            }
            .navigationTitle("Cozmo Capture")
            .fullScreenCover(item: $launchTier) { tier in
                CaptureView(tier: tier)
                    .environmentObject(controller)
            }
            .alert("Cannot start", isPresented: .constant(controller.lastError != nil && launchTier == nil)) {
                Button("OK") { controller.reset() }
            } message: {
                Text(controller.lastError ?? "")
            }
        }
    }

    private var deviceCard: some View {
        let caps = controller.capabilities
        return VStack(alignment: .leading, spacing: 6) {
            Text(caps.marketingName).font(.headline)
            Text("iOS \(caps.systemVersion) · \(caps.captureResolution)")
                .font(.caption).foregroundStyle(.secondary)
            Divider().padding(.vertical, 4)
            ForEach(CaptureTier.allCases) { tier in
                HStack(alignment: .top, spacing: 8) {
                    Image(systemName: caps.supports(tier) ? "checkmark.circle.fill" : "xmark.circle.fill")
                        .foregroundStyle(caps.supports(tier) ? .green : .orange)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(tier.displayName).font(.subheadline)
                        if !caps.supports(tier), let why = caps.unsupportedTierReasons[tier.rawValue] {
                            Text(why).font(.caption2).foregroundStyle(.secondary)
                        }
                    }
                }
            }
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.white.opacity(0.06), in: RoundedRectangle(cornerRadius: 12))
    }

    private func tierButton(_ tier: CaptureTier) -> some View {
        let enabled = controller.capabilities.supports(tier)
        return Button {
            launchTier = tier
        } label: {
            HStack {
                VStack(alignment: .leading, spacing: 3) {
                    Text(tier.displayName).font(.headline)
                    Text(tier.shortSubtitle).font(.caption).foregroundStyle(.secondary)
                }
                Spacer()
                Image(systemName: "chevron.right").foregroundStyle(.secondary)
            }
            .padding()
            .frame(maxWidth: .infinity)
            .background(Color.white.opacity(enabled ? 0.10 : 0.03),
                        in: RoundedRectangle(cornerRadius: 12))
        }
        .buttonStyle(.plain)
        .disabled(!enabled)
        .opacity(enabled ? 1 : 0.5)
    }
}
