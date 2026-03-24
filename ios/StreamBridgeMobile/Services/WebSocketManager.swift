import Foundation
import Combine

@MainActor
class WebSocketManager: ObservableObject {
    private var webSocket: URLSessionWebSocketTask?
    private var session: URLSession?
    private var baseURL: String = ""
    private var token: String = ""
    private var isRunning = false
    private var reconnectDelay: TimeInterval = 1.0

    weak var appState: AppState?

    func connect(baseURL: String, token: String) {
        self.baseURL = baseURL
        self.token = token
        self.isRunning = true
        self.reconnectDelay = 1.0
        doConnect()
    }

    func disconnect() {
        isRunning = false
        webSocket?.cancel(with: .goingAway, reason: nil)
        webSocket = nil
    }

    private func doConnect() {
        guard isRunning else { return }

        let wsURL: String
        let httpBase = baseURL.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        if httpBase.hasPrefix("https://") {
            wsURL = httpBase.replacingOccurrences(of: "https://", with: "wss://") + "/api/v1/ws"
        } else {
            wsURL = httpBase.replacingOccurrences(of: "http://", with: "ws://") + "/api/v1/ws"
        }

        var urlString = wsURL
        if !token.isEmpty {
            urlString += "?token=\(token)"
        }

        guard let url = URL(string: urlString) else { return }

        let config = URLSessionConfiguration.default
        session = URLSession(configuration: config)
        webSocket = session?.webSocketTask(with: url)
        webSocket?.resume()

        receiveMessage()
        appState?.isConnected = true
        appState?.addLog("WebSocket connected", level: "info")
    }

    private func receiveMessage() {
        webSocket?.receive { [weak self] result in
            Task { @MainActor in
                guard let self = self, self.isRunning else { return }

                switch result {
                case .success(let message):
                    switch message {
                    case .string(let text):
                        self.handleTextMessage(text)
                    case .data(let data):
                        // Binary data (future use)
                        break
                    @unknown default:
                        break
                    }
                    self.receiveMessage()

                case .failure(let error):
                    self.appState?.isConnected = false
                    self.appState?.addLog("WebSocket disconnected: \(error.localizedDescription)", level: "error")
                    self.scheduleReconnect()
                }
            }
        }
    }

    private func handleTextMessage(_ text: String) {
        guard let data = text.data(using: .utf8),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let type = json["type"] as? String else { return }

        guard let state = appState else { return }

        switch type {
        case "levels":
            state.leftDb = json["left_db"] as? Double ?? -100.0
            state.rightDb = json["right_db"] as? Double ?? -100.0
            state.leftPeakDb = json["left_peak_db"] as? Double ?? -100.0
            state.rightPeakDb = json["right_peak_db"] as? Double ?? -100.0

        case "state_changed":
            if let newState = json["state"] as? String {
                state.streamState = newState
                state.isStreaming = newState == "connected"
            }

        case "silence_warning":
            state.silenceStatus = "warning"
        case "silence_alert":
            state.silenceStatus = "alert"
        case "silence_ok", "silence_cleared":
            state.silenceStatus = "ok"

        case "metadata":
            state.codec = json["codec"] as? String ?? ""
            state.bitrate = json["bitrate"] as? Int ?? 0
            state.sampleRate = json["sample_rate"] as? Int ?? 0
            state.channels = json["channels"] as? Int ?? 0
            state.metadataSummary = json["summary"] as? String ?? ""

        case "uptime":
            state.uptimeSeconds = json["seconds"] as? Double ?? 0
            state.uptimeFormatted = json["formatted"] as? String ?? ""

        case "client_count":
            state.clientCount = json["count"] as? Int ?? 0

        case "log":
            let msg = json["message"] as? String ?? ""
            let level = json["level"] as? String ?? "info"
            state.addLog(msg, level: level)

        case "auto_stop":
            let detType = json["detection_type"] as? String ?? "unknown"
            let reason = json["reason"] as? String ?? ""
            state.addLog("AUTO-STOP (\(detType)): \(reason)", level: "warning")

        case "tunnel_status":
            state.tunnelStatus = json["status"] as? String ?? "disconnected"
            state.tunnelError = json["error"] as? String
            state.tunnelPublicURL = json["public_url"] as? String

        default:
            break
        }
    }

    private func scheduleReconnect() {
        guard isRunning else { return }
        let delay = reconnectDelay
        reconnectDelay = min(reconnectDelay * 2, 30.0)

        Task {
            try? await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))
            guard self.isRunning else { return }
            self.appState?.addLog("Reconnecting WebSocket...", level: "info")
            self.doConnect()
        }
    }

    func sendBinaryData(_ data: Data) {
        webSocket?.send(.data(data)) { error in
            if let error = error {
                print("WebSocket send error: \(error)")
            }
        }
    }
}
