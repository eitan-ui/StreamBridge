import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var appState: AppState
    @EnvironmentObject var api: StreamBridgeAPI

    @State private var config: StreamConfig?
    @State private var isSaving = false
    @State private var statusMessage = ""

    var body: some View {
        NavigationStack {
            Group {
                if let config = Binding($config) {
                    Form {
                        networkSection(config)
                        audioSection(config)
                        silenceSection(config)
                        autoStopSection(config)
                        reconnectSection(config)
                        alertsSection(config)

                        Section("Schedule") {
                            HStack {
                                Text("Auto-Start")
                                Spacer()
                                Text(config.schedule.enabled.wrappedValue ? "Enabled" : "Disabled")
                                    .foregroundStyle(config.schedule.enabled.wrappedValue ? .green : .secondary)
                                    .font(.caption.bold())
                            }
                            if !config.schedule.entries.wrappedValue.isEmpty {
                                ForEach(Array(config.schedule.entries.wrappedValue.enumerated()), id: \.offset) { _, entry in
                                    HStack {
                                        Image(systemName: "clock")
                                            .foregroundStyle(.blue)
                                        Text(entry.time)
                                            .font(.body.monospacedDigit())
                                        Spacer()
                                        Text(entry.url)
                                            .font(.caption)
                                            .foregroundStyle(.secondary)
                                            .lineLimit(1)
                                            .truncationMode(.middle)
                                        if !entry.enabled {
                                            Image(systemName: "moon.fill")
                                                .foregroundStyle(.orange)
                                                .font(.caption)
                                        }
                                    }
                                }
                            } else {
                                Text("No scheduled times configured")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                            Text("Configure schedule from desktop app or web PWA")
                                .font(.caption2)
                                .foregroundStyle(.tertiary)
                        }

                        Section("Advanced") {
                            DisclosureGroup("WhatsApp") {
                                whatsappContent(config)
                            }
                            DisclosureGroup("mAirList") {
                                mairlistContent(config)
                            }
                            DisclosureGroup("Internet Tunnel (SSH)") {
                                tunnelContent(config)
                            }
                        }

                        Section {
                            Button {
                                saveConfig()
                            } label: {
                                HStack {
                                    if isSaving {
                                        ProgressView()
                                    }
                                    Text("Save Changes")
                                }
                                .frame(maxWidth: .infinity)
                            }
                            .disabled(isSaving)
                        }

                        if !statusMessage.isEmpty {
                            Section {
                                Text(statusMessage)
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                        }
                    }
                } else {
                    ProgressView("Loading settings...")
                }
            }
            .navigationTitle("Settings")
            .onAppear { loadConfig() }
            .refreshable { loadConfig() }
        }
    }

    // MARK: - Sections

    private func networkSection(_ config: Binding<StreamConfig>) -> some View {
        Section("Network") {
            HStack {
                Text("Port")
                Spacer()
                TextField("9000", value: config.port, format: .number)
                    .keyboardType(.numberPad)
                    .multilineTextAlignment(.trailing)
                    .frame(width: 80)
            }
            HStack {
                Text("FFmpeg Path")
                Spacer()
                TextField("ffmpeg", text: config.ffmpegPath)
                    .multilineTextAlignment(.trailing)
                    .frame(width: 120)
            }
        }
    }

    private func audioSection(_ config: Binding<StreamConfig>) -> some View {
        Section("Audio") {
            Picker("Opus Bitrate", selection: config.opusBitrate) {
                Text("32 kbps").tag(32)
                Text("48 kbps").tag(48)
                Text("64 kbps").tag(64)
                Text("96 kbps").tag(96)
                Text("128 kbps").tag(128)
                Text("192 kbps").tag(192)
            }
        }
    }

    private func silenceSection(_ config: Binding<StreamConfig>) -> some View {
        Section("Silence Detection") {
            HStack {
                Text("Threshold")
                Spacer()
                Text("\(config.silence.thresholdDb.wrappedValue, specifier: "%.0f") dB")
                Stepper("", value: config.silence.thresholdDb, in: -80...0, step: 1)
                    .labelsHidden()
            }
            HStack {
                Text("Warning Delay")
                Spacer()
                Text("\(config.silence.warningDelayS.wrappedValue)s")
                Stepper("", value: config.silence.warningDelayS, in: 1...300)
                    .labelsHidden()
            }
            HStack {
                Text("Alert Delay")
                Spacer()
                Text("\(config.silence.alertDelayS.wrappedValue)s")
                Stepper("", value: config.silence.alertDelayS, in: 1...600)
                    .labelsHidden()
            }
        }
    }

    private func autoStopSection(_ config: Binding<StreamConfig>) -> some View {
        Section("Auto-Stop") {
            Toggle("Enable Auto-Stop", isOn: config.silence.autoStop.enabled)
            HStack {
                Text("Delay")
                Spacer()
                Text("\(config.silence.autoStop.delayS.wrappedValue, specifier: "%.1f")s")
                Stepper("", value: config.silence.autoStop.delayS, in: 0.5...30, step: 0.5)
                    .labelsHidden()
            }
            Toggle("Tone Detection", isOn: config.silence.autoStop.toneDetectionEnabled)
            Toggle("Trigger mAirList", isOn: config.silence.autoStop.triggerMairlist)
            Toggle("Stop Stream", isOn: config.silence.autoStop.stopStream)
        }
    }

    private func reconnectSection(_ config: Binding<StreamConfig>) -> some View {
        Section("Reconnect") {
            HStack {
                Text("Initial Delay")
                Spacer()
                Text("\(config.reconnect.initialDelayS.wrappedValue, specifier: "%.1f")s")
            }
            HStack {
                Text("Max Delay")
                Spacer()
                Text("\(config.reconnect.maxDelayS.wrappedValue, specifier: "%.0f")s")
            }
            HStack {
                Text("Max Retries")
                Spacer()
                Text(config.reconnect.maxRetries.wrappedValue == 0 ? "Unlimited" : "\(config.reconnect.maxRetries.wrappedValue)")
            }
        }
    }

    private func alertsSection(_ config: Binding<StreamConfig>) -> some View {
        Section("Alerts") {
            Toggle("Sound Alerts", isOn: config.alerts.soundEnabled)
            Button("Test Alert") {
                Task { try? await api.testAlert() }
            }
        }
    }

    @ViewBuilder
    private func whatsappContent(_ config: Binding<StreamConfig>) -> some View {
        Toggle("Enable WhatsApp", isOn: config.alerts.whatsapp.enabled)
        if config.alerts.whatsapp.enabled.wrappedValue {
            Picker("Service", selection: config.alerts.whatsapp.service) {
                Text("CallMeBot").tag("callmebot")
                Text("Twilio").tag("twilio")
                Text("Custom").tag("custom")
            }
            TextField("Phone", text: config.alerts.whatsapp.phone)
                .keyboardType(.phonePad)
            TextField("API Key", text: config.alerts.whatsapp.apiKey)
        }
    }

    @ViewBuilder
    private func mairlistContent(_ config: Binding<StreamConfig>) -> some View {
        Toggle("Enable mAirList", isOn: config.mairlist.enabled)
        if config.mairlist.enabled.wrappedValue {
            HStack {
                Text("API URL")
                Spacer()
                TextField("http://localhost:9000", text: config.mairlist.apiUrl)
                    .multilineTextAlignment(.trailing)
                    .textInputAutocapitalization(.never)
            }
            HStack {
                Text("Default Command")
                Spacer()
                TextField("PLAYER A NEXT", text: config.mairlist.command)
                    .multilineTextAlignment(.trailing)
                    .textInputAutocapitalization(.characters)
            }
            HStack {
                Text("Silence Command")
                Spacer()
                TextField("PLAYER A NEXT", text: config.mairlist.silenceCommand)
                    .multilineTextAlignment(.trailing)
                    .textInputAutocapitalization(.characters)
            }
            HStack {
                Text("Tone Command")
                Spacer()
                TextField("PLAYER A NEXT", text: config.mairlist.toneCommand)
                    .multilineTextAlignment(.trailing)
                    .textInputAutocapitalization(.characters)
            }
        }
    }

    @ViewBuilder
    private func tunnelContent(_ config: Binding<StreamConfig>) -> some View {
        Toggle("Enable Tunnel", isOn: config.tunnel.enabled)
        if config.tunnel.enabled.wrappedValue {
            HStack {
                Text("VPS Host")
                Spacer()
                TextField("203.0.113.5", text: config.tunnel.host)
                    .multilineTextAlignment(.trailing)
                    .textInputAutocapitalization(.never)
            }
            HStack {
                Text("SSH Port")
                Spacer()
                TextField("22", value: config.tunnel.port, format: .number)
                    .keyboardType(.numberPad)
                    .multilineTextAlignment(.trailing)
                    .frame(width: 80)
            }
            HStack {
                Text("Username")
                Spacer()
                TextField("root", text: config.tunnel.username)
                    .multilineTextAlignment(.trailing)
                    .textInputAutocapitalization(.never)
            }
            HStack {
                Text("Remote Port")
                Spacer()
                TextField("9000", value: config.tunnel.remotePort, format: .number)
                    .keyboardType(.numberPad)
                    .multilineTextAlignment(.trailing)
                    .frame(width: 80)
            }
        }

        // Tunnel status
        if appState.tunnelStatus != "disconnected" {
            HStack {
                Text("Status")
                Spacer()
                Text(appState.tunnelStatus.uppercased())
                    .foregroundStyle(appState.tunnelStatus == "connected" ? .green :
                                    appState.tunnelStatus == "connecting" ? .yellow : .red)
                    .font(.caption.bold())
            }
            if let url = appState.tunnelPublicURL, !url.isEmpty {
                HStack {
                    Text("Public URL")
                    Spacer()
                    Text(url)
                        .font(.caption)
                        .foregroundStyle(.blue)
                        .lineLimit(1)
                        .truncationMode(.middle)
                }
            }
        }

        HStack {
            Button("Start") {
                Task { try? await api.tunnelStart() }
            }
            Spacer()
            Button("Stop") {
                Task { try? await api.tunnelStop() }
            }
            .foregroundStyle(.red)
        }
    }

    // MARK: - Actions

    private func loadConfig() {
        Task {
            config = try? await api.getConfig()
        }
    }

    private func saveConfig() {
        guard let cfg = config else { return }
        isSaving = true
        Task {
            do {
                let updates: [String: Any] = [
                    "port": cfg.port,
                    "opus_bitrate": cfg.opusBitrate,
                    "ffmpeg_path": cfg.ffmpegPath,
                    "silence": [
                        "threshold_db": cfg.silence.thresholdDb,
                        "warning_delay_s": cfg.silence.warningDelayS,
                        "alert_delay_s": cfg.silence.alertDelayS,
                        "auto_stop": [
                            "enabled": cfg.silence.autoStop.enabled,
                            "delay_s": cfg.silence.autoStop.delayS,
                            "tone_detection_enabled": cfg.silence.autoStop.toneDetectionEnabled,
                            "tone_max_crest_db": cfg.silence.autoStop.toneMaxCrestDb,
                            "trigger_mairlist": cfg.silence.autoStop.triggerMairlist,
                            "stop_stream": cfg.silence.autoStop.stopStream,
                        ],
                    ],
                    "reconnect": [
                        "initial_delay_s": cfg.reconnect.initialDelayS,
                        "max_delay_s": cfg.reconnect.maxDelayS,
                        "max_retries": cfg.reconnect.maxRetries,
                    ],
                    "alerts": [
                        "sound_enabled": cfg.alerts.soundEnabled,
                        "whatsapp": [
                            "enabled": cfg.alerts.whatsapp.enabled,
                            "service": cfg.alerts.whatsapp.service,
                            "phone": cfg.alerts.whatsapp.phone,
                            "api_key": cfg.alerts.whatsapp.apiKey,
                        ],
                    ],
                    "mairlist": [
                        "enabled": cfg.mairlist.enabled,
                        "api_url": cfg.mairlist.apiUrl,
                        "command": cfg.mairlist.command,
                        "silence_command": cfg.mairlist.silenceCommand,
                        "tone_command": cfg.mairlist.toneCommand,
                    ],
                    "schedule": [
                        "enabled": cfg.schedule.enabled,
                        "entries": cfg.schedule.entries.map { [
                            "time": $0.time,
                            "url": $0.url,
                            "enabled": $0.enabled,
                        ] as [String: Any] },
                    ] as [String: Any],
                    "tunnel": [
                        "enabled": cfg.tunnel.enabled,
                        "host": cfg.tunnel.host,
                        "port": cfg.tunnel.port,
                        "username": cfg.tunnel.username,
                        "key_path": cfg.tunnel.keyPath,
                        "remote_port": cfg.tunnel.remotePort,
                    ],
                ]
                try await api.updateConfig(updates)
                statusMessage = "Settings saved"
            } catch {
                statusMessage = "Error: \(error.localizedDescription)"
            }
            isSaving = false
        }
    }
}
