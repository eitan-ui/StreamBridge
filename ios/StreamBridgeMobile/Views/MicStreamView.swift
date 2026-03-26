import SwiftUI

struct MicStreamView: View {
    @EnvironmentObject var appState: AppState
    @EnvironmentObject var api: StreamBridgeAPI
    @EnvironmentObject var micService: MicCaptureService

    @State private var selectedMode: String = "talkback"
    @State private var isTalkbackPressed = false

    var body: some View {
        NavigationStack {
            VStack(spacing: 24) {
                // Mode selector
                Picker("Mode", selection: $selectedMode) {
                    Text("Talkback").tag("talkback")
                    Text("Source").tag("source")
                }
                .pickerStyle(.segmented)
                .padding(.horizontal)

                // Mode description
                Text(modeDescription)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal)

                Spacer()

                if selectedMode == "talkback" {
                    talkbackView
                } else {
                    sourceView
                }

                Spacer()

                // Input level meter
                if micService.isCapturing {
                    VStack(spacing: 4) {
                        Text("MIC INPUT")
                            .font(.caption.bold())
                            .foregroundStyle(.secondary)
                        LevelMeterView(
                            leftDb: micService.inputLevel,
                            rightDb: micService.inputLevel
                        )
                    }
                    .padding()
                }

                // Status
                HStack {
                    Circle()
                        .fill(micService.isCapturing ? Color.red : Color.gray)
                        .frame(width: 8, height: 8)
                    Text(micService.isCapturing ? "Streaming" : "Idle")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            .padding()
            .navigationTitle("Mic Stream")
        }
    }

    private var modeDescription: String {
        if selectedMode == "talkback" {
            return "Hold the button to speak. Your voice temporarily replaces the main stream."
        } else {
            return "Start streaming to register your iPhone mic as a source in StreamBridge."
        }
    }

    // MARK: - Talkback

    private var talkbackView: some View {
        VStack(spacing: 16) {
            // Big push-to-talk button
            Circle()
                .fill(isTalkbackPressed ? Color.red : Color.red.opacity(0.3))
                .frame(width: 150, height: 150)
                .overlay {
                    VStack {
                        Image(systemName: "mic.fill")
                            .font(.system(size: 40))
                            .foregroundStyle(.white)
                        Text(isTalkbackPressed ? "LIVE" : "HOLD")
                            .font(.caption.bold())
                            .foregroundStyle(.white)
                    }
                }
                .shadow(color: isTalkbackPressed ? .red.opacity(0.5) : .clear, radius: 20)
                .scaleEffect(isTalkbackPressed ? 1.05 : 1.0)
                .animation(.easeInOut(duration: 0.15), value: isTalkbackPressed)
                .gesture(
                    DragGesture(minimumDistance: 0)
                        .onChanged { _ in
                            if !isTalkbackPressed {
                                startTalkback()
                            }
                        }
                        .onEnded { _ in
                            stopTalkback()
                        }
                )
        }
    }

    // MARK: - Source

    private var sourceView: some View {
        VStack(spacing: 16) {
            Button {
                if micService.isCapturing {
                    stopSourceMode()
                } else {
                    startSourceMode()
                }
            } label: {
                VStack {
                    Image(systemName: micService.isCapturing ? "stop.circle.fill" : "mic.circle.fill")
                        .font(.system(size: 64))
                    Text(micService.isCapturing ? "Stop Streaming" : "Start Streaming")
                        .font(.headline)
                }
                .frame(width: 160, height: 160)
                .background(micService.isCapturing ? Color.red.opacity(0.2) : Color.blue.opacity(0.2))
                .cornerRadius(80)
            }
        }
    }

    // MARK: - Actions

    private func startTalkback() {
        isTalkbackPressed = true
        Task {
            try? await api.startMic(mode: "talkback")
            micService.startCapture()
        }
    }

    private func stopTalkback() {
        isTalkbackPressed = false
        micService.stopCapture()
        Task { try? await api.stopMic() }
    }

    private func startSourceMode() {
        Task {
            try? await api.startMic(mode: "source")
            micService.startCapture()
        }
    }

    private func stopSourceMode() {
        micService.stopCapture()
        Task { try? await api.stopMic() }
    }
}
