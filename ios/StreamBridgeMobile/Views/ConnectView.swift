import SwiftUI

struct ConnectView: View {
    @EnvironmentObject var appState: AppState
    @EnvironmentObject var api: StreamBridgeAPI
    @EnvironmentObject var wsManager: WebSocketManager
    @EnvironmentObject var connectionManager: ConnectionManager

    @State private var host: String = ""
    @State private var port: String = "9000"
    @State private var token: String = ""
    @State private var serverName: String = ""
    @State private var isConnecting = false
    @State private var errorMessage: String?
    @State private var showSaveSheet = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 24) {
                    // Logo / Header
                    VStack(spacing: 8) {
                        Image(systemName: "waveform.circle.fill")
                            .font(.system(size: 64))
                            .foregroundStyle(.blue)
                        Text("StreamBridge")
                            .font(.title.bold())
                        Text("Remote Control")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }
                    .padding(.top, 20)

                    // Saved servers
                    if !appState.savedServers.isEmpty {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("SAVED SERVERS")
                                .font(.caption.bold())
                                .foregroundStyle(.secondary)

                            ForEach(appState.savedServers) { server in
                                Button {
                                    host = server.host
                                    port = "\(server.port)"
                                    token = server.token
                                    connectToServer()
                                } label: {
                                    HStack {
                                        Image(systemName: "server.rack")
                                            .foregroundStyle(.blue)
                                        VStack(alignment: .leading) {
                                            Text(server.name)
                                                .font(.headline)
                                            Text("\(server.host):\(server.port)")
                                                .font(.caption)
                                                .foregroundStyle(.secondary)
                                        }
                                        Spacer()
                                        Image(systemName: "chevron.right")
                                            .foregroundStyle(.secondary)
                                    }
                                    .padding()
                                    .background(.ultraThinMaterial)
                                    .cornerRadius(12)
                                }
                                .buttonStyle(.plain)
                            }
                        }
                        .padding(.horizontal)
                    }

                    // Manual connection
                    VStack(alignment: .leading, spacing: 12) {
                        Text("CONNECT MANUALLY")
                            .font(.caption.bold())
                            .foregroundStyle(.secondary)

                        TextField("Server IP or hostname", text: $host)
                            .textFieldStyle(.roundedBorder)
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()

                        TextField("Port", text: $port)
                            .textFieldStyle(.roundedBorder)
                            .keyboardType(.numberPad)

                        TextField("API Token (optional)", text: $token)
                            .textFieldStyle(.roundedBorder)
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()

                        if let error = errorMessage {
                            Text(error)
                                .font(.caption)
                                .foregroundStyle(.red)
                        }

                        HStack(spacing: 12) {
                            Button {
                                connectToServer()
                            } label: {
                                HStack {
                                    if isConnecting {
                                        ProgressView()
                                            .tint(.white)
                                    }
                                    Text(isConnecting ? "Connecting..." : "Connect")
                                }
                                .frame(maxWidth: .infinity)
                                .padding()
                                .background(.blue)
                                .foregroundStyle(.white)
                                .cornerRadius(12)
                            }
                            .disabled(host.isEmpty || isConnecting)

                            Button {
                                showSaveSheet = true
                            } label: {
                                Image(systemName: "square.and.arrow.down")
                                    .padding()
                                    .background(.ultraThinMaterial)
                                    .cornerRadius(12)
                            }
                            .disabled(host.isEmpty)
                        }
                    }
                    .padding(.horizontal)

                    // Bonjour discovery
                    VStack(alignment: .leading, spacing: 8) {
                        HStack {
                            Text("LOCAL NETWORK")
                                .font(.caption.bold())
                                .foregroundStyle(.secondary)
                            Spacer()
                            if connectionManager.isScanning {
                                ProgressView()
                            }
                        }

                        Button {
                            connectionManager.startScanning()
                        } label: {
                            HStack {
                                Image(systemName: "wifi")
                                Text("Scan Local Network")
                            }
                            .frame(maxWidth: .infinity)
                            .padding()
                            .background(.ultraThinMaterial)
                            .cornerRadius(12)
                        }
                        .disabled(connectionManager.isScanning)

                        ForEach(connectionManager.discoveredServers) { server in
                            Button {
                                host = server.host
                                port = "\(server.port)"
                                connectToServer()
                            } label: {
                                HStack {
                                    Image(systemName: "bonjour")
                                        .foregroundStyle(.green)
                                    VStack(alignment: .leading) {
                                        Text(server.name)
                                            .font(.headline)
                                        Text("\(server.host):\(server.port)")
                                            .font(.caption)
                                            .foregroundStyle(.secondary)
                                    }
                                    Spacer()
                                }
                                .padding()
                                .background(.ultraThinMaterial)
                                .cornerRadius(12)
                            }
                            .buttonStyle(.plain)
                        }
                    }
                    .padding(.horizontal)

                    Spacer()
                }
            }
            .navigationTitle("")
            .alert("Save Server", isPresented: $showSaveSheet) {
                TextField("Server name", text: $serverName)
                Button("Save") {
                    let profile = ServerProfile(
                        name: serverName.isEmpty ? host : serverName,
                        host: host,
                        port: Int(port) ?? 9000,
                        token: token
                    )
                    appState.savedServers.append(profile)
                    serverName = ""
                }
                Button("Cancel", role: .cancel) {}
            }
        }
    }

    private func connectToServer() {
        guard !host.isEmpty else { return }
        isConnecting = true
        errorMessage = nil

        let portNum = Int(port) ?? 9000
        let baseURL = "http://\(host):\(portNum)"

        api.configure(baseURL: baseURL, token: token)

        Task {
            do {
                let state = try await api.getState()
                appState.serverURL = baseURL
                appState.apiToken = token
                appState.streamState = state.streamState
                appState.isStreaming = state.isStreaming
                appState.clientCount = state.clientCount

                // Connect WebSocket
                wsManager.connect(baseURL: baseURL, token: token)

                // Load config + sources
                if let config = try? await api.getConfig() {
                    appState.config = config
                }
                if let sourcesResp = try? await api.getSources() {
                    appState.sources = sourcesResp.sources
                }

                isConnecting = false
            } catch {
                errorMessage = error.localizedDescription
                isConnecting = false
            }
        }
    }
}
