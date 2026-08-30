import SwiftUI

struct CaptureView: View {
    let tier: CaptureTier

    @EnvironmentObject private var controller: CaptureController
    @Environment(\.dismiss) private var dismiss

    @State private var showingRoomPrompt = false
    @State private var roomName = ""
    @State private var note = ""
    @State private var showingFinishSheet = false
    @State private var showingInstructions = true

    var body: some View {
        ZStack {
            ARPreview(session: controller.session).ignoresSafeArea()
            VStack {
                hud
                Spacer()
                if !controller.rooms.isEmpty { roomStrip }
                controls
            }
            .padding()
        }
        .onAppear {
            if !controller.phase.isRunning { controller.start(tier: tier) }
        }
        .sheet(isPresented: $showingInstructions) {
            instructionSheet.presentationDetents([.medium])
        }
        .alert("Room name", isPresented: $showingRoomPrompt) {
            TextField("e.g. Living Room", text: $roomName)
            Button("Add") { controller.markRoom(named: roomName); roomName = "" }
            Button("Cancel", role: .cancel) { roomName = "" }
        } message: {
            Text(tier == .photo
                 ? "Photos you take next are filed under this room."
                 : "Marks the moment you entered this room.")
        }
        .sheet(isPresented: $showingFinishSheet) { finishSheet.presentationDetents([.medium]) }
    }

    // MARK: Pieces

    private var hud: some View {
        HStack(alignment: .top) {
            VStack(alignment: .leading, spacing: 4) {
                Text(tier.displayName).font(.headline)
                Text(timeString(controller.elapsed))
                    .font(.system(.title3, design: .monospaced))
                Label(controller.trackingLabel,
                      systemImage: controller.trackingIsHealthy ? "dot.radiowaves.left.and.right" : "exclamationmark.triangle.fill")
                    .font(.caption)
                    .foregroundStyle(controller.trackingIsHealthy ? .green : .orange)
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 4) {
                if tier == .photo {
                    Text("\(controller.rooms.reduce(0) { $0 + $1.photoCount }) photos").font(.caption)
                } else {
                    Text("\(controller.framesWritten) frames").font(.caption)
                    if controller.framesDropped > 0 {
                        Text("\(controller.framesDropped) dropped")
                            .font(.caption2).foregroundStyle(.orange)
                    }
                }
                Button { showingInstructions = true } label: {
                    Image(systemName: "questionmark.circle")
                }
            }
        }
        .padding(12)
        .background(.black.opacity(0.55), in: RoundedRectangle(cornerRadius: 12))
    }

    private var roomStrip: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(controller.rooms) { room in
                    VStack(spacing: 2) {
                        Text(room.name).font(.caption).bold()
                        if tier == .photo {
                            Text("\(room.photoCount) photo\(room.photoCount == 1 ? "" : "s")")
                                .font(.caption2)
                                .foregroundStyle(room.photoCount >= 2 ? .green : .orange)
                        }
                    }
                    .padding(.horizontal, 10).padding(.vertical, 6)
                    .background(.black.opacity(0.55), in: Capsule())
                }
            }
        }
    }

    private var controls: some View {
        HStack(spacing: 16) {
            Button { showingRoomPrompt = true } label: {
                Label(tier == .photo ? "Next room" : "Mark room", systemImage: "plus.square.on.square")
                    .padding(.horizontal, 14).padding(.vertical, 12)
                    .background(.black.opacity(0.6), in: Capsule())
            }

            if tier == .photo {
                Button { controller.capturePhoto() } label: {
                    Circle().strokeBorder(.white, lineWidth: 4)
                        .frame(width: 72, height: 72)
                        .background(Circle().fill(.white.opacity(0.25)))
                }
                .disabled(controller.rooms.isEmpty)
                .opacity(controller.rooms.isEmpty ? 0.4 : 1)
            }

            Spacer()

            Button(role: .destructive) { showingFinishSheet = true } label: {
                Label("Finish", systemImage: "stop.fill")
                    .padding(.horizontal, 14).padding(.vertical, 12)
                    .background(.red.opacity(0.85), in: Capsule())
            }
        }
        .foregroundStyle(.white)
    }

    private var instructionSheet: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text(tier.displayName).font(.title2).bold()
            Text(tier.instructions).font(.body)
            if tier == .photo {
                Text("2 to 8 photos per room. Fewer than 2 and the room cannot be reconstructed at all.")
                    .font(.footnote).foregroundStyle(.secondary)
            }
            Spacer()
            Button("Start") { showingInstructions = false }
                .buttonStyle(.borderedProminent)
                .frame(maxWidth: .infinity)
        }
        .padding()
    }

    private var finishSheet: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Finish capture").font(.title2).bold()
            Text("\(controller.rooms.count) room\(controller.rooms.count == 1 ? "" : "s") marked.")
                .foregroundStyle(.secondary)
            TextField("Note (optional) — lighting, mirrors, anything odd", text: $note, axis: .vertical)
                .textFieldStyle(.roundedBorder)
                .lineLimit(2...4)
            Spacer()
            Button("Save capture") {
                controller.finish(note: note.isEmpty ? nil : note) { _ in
                    showingFinishSheet = false
                    dismiss()
                    controller.reset()
                }
            }
            .buttonStyle(.borderedProminent)
            .frame(maxWidth: .infinity)
            Button("Keep scanning") { showingFinishSheet = false }
                .frame(maxWidth: .infinity)
            Button("Discard capture", role: .destructive) {
                controller.discard()
                showingFinishSheet = false
                dismiss()
            }
            .frame(maxWidth: .infinity)
        }
        .padding()
    }

    private func timeString(_ t: TimeInterval) -> String {
        String(format: "%02d:%02d", Int(t) / 60, Int(t) % 60)
    }
}
