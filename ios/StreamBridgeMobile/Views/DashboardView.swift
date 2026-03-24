import SwiftUI

struct DashboardView: View {
    @EnvironmentObject var appState: AppState
    @EnvironmentObject var api: StreamBridgeAPI

    @State private var selectedSourceIndex: Int? = nil
    @State private var streamURL: String = ""

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {
                    // Status card
                    statusCard

                    // Tunnel badge
                    if appState.tunnelStatus != "disconnected" {
                        tunnelBadge
                    }

                    // Level meters
                    LevelMeterView(
                        leftDb: appState.leftDb,
                        rightDb: appState.rightDb
                    )
                    .padding(.horizontal)

                    // Info row
                    infoRow

                    // Controls
                    controlButtons

                    // Source selector
                    sourceSelector

                    // Quick mic button
                    quickMicButton

                    // Log preview
                    NavigationLink(destination: LogView()) {
                        logPreview
                    }
                    .buttonStyle(.plain)
                }
                .padding()
            }
            .navigationTitle("StreamBridge")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        appState.isConnected = false
                    } label: {
                        Image(systemName: "xmark.circle")
                    }
                }
            }
        }
    }

    // MARK: - Status Card

    private var statusCard: some View {
        HStack {
            // Status LED
            Circle()
                .fill(statusColor)
                .frame(width: 12, height: 12)
                .shadow(color: statusColor.opacity(0.6), radius: 4)

            Text(appState.streamState.uppercased())
                .font(.headline.bold())
                .foregroundStyle(statusColor)

            Spacer()

            // Silence indicator
            silenceIndicator

            Spacer()

            // Uptime
            if !appState.uptimeFormatted.isEmpty {
                Text(appState.uptimeFormatted)
                    .font(.caption.monospacedDigit())
                    .foregroundStyle(.secondary)
            }
        }
        .padding()
        .background(.ultraThinMaterial)
        .cornerRadius(12)
    }

    private var statusColor: Color {
        switch appState.streamState {
        case "connected": return .green
        case "connecting", "reconnecting": return .yellow
        case "error": return .red
        default: return .gray
        }
    }

    private var silenceIndicator: some View {
        HStack(spacing: 4) {
            Circle()
                .fill(silenceColor)
                .frame(width: 8, height: 8)
            Text(silenceText)
                .font(.caption)
                .foregroundStyle(silenceColor)
        }
    }

    private var silenceColor: Color {
        switch appState.silenceStatus {
        case "warning": return .yellow
        case "alert": return .red
        default: return .green
        }
    }

    private var silenceText: String {
        switch appState.silenceStatus {
        case "warning": return "Silence"
        case "alert": return "ALERT"
        default: return "Audio OK"
        }
    }

    // MARK: - Tunnel Badge

    private var tunnelBadge: some View {
        HStack(spacing: 6) {
            Image(systemName: tunnelIcon)
                .foregroundStyle(tunnelColor)
            Text(tunnelText)
                .font(.caption)
                .foregroundStyle(tunnelColor)
            Spacer()
            if let url = appState.tunnelPublicURL, !url.isEmpty {
                Button {
                    UIPasteboard.general.string = url
                    appState.addLog("Tunnel URL copied", level: "info")
                } label: {
                    Image(systemName: "doc.on.doc")
                        .font(.caption)
                }
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(tunnelColor.opacity(0.1))
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(tunnelColor.opacity(0.3), lineWidth: 1)
        )
        .cornerRadius(8)
    }

    private var tunnelColor: Color {
        switch appState.tunnelStatus {
        case "connected": return .green
        case "connecting": return .yellow
        case "error": return .red
        default: return .gray
        }
    }

    private var tunnelIcon: String {
        switch appState.tunnelStatus {
        case "connected": return "checkmark.shield.fill"
        case "connecting": return "arrow.triangle.2.circlepath"
        case "error": return "exclamationmark.triangle.fill"
        default: return "globe"
        }
    }

    private var tunnelText: String {
        switch appState.tunnelStatus {
        case "connected":
            return "Tunnel: \(appState.tunnelPublicURL ?? "Connected")"
        case "connecting":
            return "Tunnel connecting..."
        case "error":
            return "Tunnel error: \(appState.tunnelError ?? "")"
        default:
            return "Tunnel offline"
        }
    }

    // MARK: - Info Row

    private var infoRow: some View {
        HStack {
            if !appState.metadataSummary.isEmpty {
                Text(appState.metadataSummary)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            Spacer()
            Text("\(appState.clientCount) clients")
                .font(.caption)
                .foregroundStyle(.blue)
        }
        .padding(.horizontal)
    }

    // MARK: - Controls

    private var controlButtons: some View {
        HStack(spacing: 12) {
            Button {
                Task {
                    let url = streamURL.isEmpty ? (
                        selectedSourceIndex != nil ?
                        appState.sources[selectedSourceIndex!].url : ""
                    ) : streamURL
                    try? await api.startStream(url: url)
                }
            } label: {
                HStack {
                    Image(systemName: "play.fill")
                    Text("START")
                }
                .frame(maxWidth: .infinity)
                .padding()
                .background(appState.isStreaming ? Color.green.opacity(0.3) : Color.green)
                .foregroundStyle(.white)
                .cornerRadius(12)
            }
            .disabled(appState.isStreaming)

            Button {
                Task { try? await api.stopStream() }
            } label: {
                HStack {
                    Image(systemName: "stop.fill")
                    Text("STOP")
                }
                .frame(maxWidth: .infinity)
                .padding()
                .background(appState.isStreaming ? Color.red : Color.red.opacity(0.3))
                .foregroundStyle(.white)
                .cornerRadius(12)
            }
            .disabled(!appState.isStreaming)
        }
    }

    // MARK: - Source Selector

    private var sourceSelector: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("SOURCE")
                .font(.caption.bold())
                .foregroundStyle(.secondary)

            TextField("Stream URL", text: $streamURL)
                .textFieldStyle(.roundedBorder)
                .textInputAutocapitalization(.never)

            if !appState.sources.isEmpty {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(appState.sources) { source in
                            Button {
                                selectedSourceIndex = source.index
                                streamURL = source.url
                            } label: {
                                Text(source.name)
                                    .font(.caption)
                                    .padding(.horizontal, 12)
                                    .padding(.vertical, 6)
                                    .background(
                                        selectedSourceIndex == source.index ?
                                        Color.blue : Color.gray.opacity(0.2)
                                    )
                                    .foregroundStyle(
                                        selectedSourceIndex == source.index ?
                                        .white : .primary
                                    )
                                    .cornerRadius(8)
                            }
                        }
                    }
                }
            }
        }
    }

    // MARK: - Quick Mic

    private var quickMicButton: some View {
        NavigationLink(destination: MicStreamView()) {
            HStack {
                Image(systemName: "mic.fill")
                Text("Mic Talkback")
                Spacer()
                Image(systemName: "chevron.right")
            }
            .padding()
            .background(.ultraThinMaterial)
            .cornerRadius(12)
        }
        .buttonStyle(.plain)
    }

    // MARK: - Log Preview

    private var logPreview: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text("EVENT LOG")
                    .font(.caption.bold())
                    .foregroundStyle(.secondary)
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            ForEach(appState.logEntries.suffix(3)) { entry in
                HStack {
                    Text(entry.timeString)
                        .font(.caption2.monospacedDigit())
                        .foregroundStyle(.secondary)
                    Text(entry.message)
                        .font(.caption2)
                        .foregroundStyle(logColor(entry.level))
                        .lineLimit(1)
                }
            }
        }
        .padding()
        .background(.ultraThinMaterial)
        .cornerRadius(12)
    }

    private func logColor(_ level: String) -> Color {
        switch level {
        case "error": return .red
        case "warning": return .yellow
        default: return .secondary
        }
    }
}
