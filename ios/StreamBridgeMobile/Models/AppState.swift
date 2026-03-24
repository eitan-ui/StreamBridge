import Foundation
import Combine

@MainActor
class AppState: ObservableObject {
    // Connection
    @Published var serverURL: String = ""
    @Published var apiToken: String = ""
    @Published var isConnected: Bool = false

    // Stream state
    @Published var streamState: String = "idle"  // idle, connecting, connected, reconnecting, error
    @Published var isStreaming: Bool = false

    // Audio levels (real-time from WebSocket)
    @Published var leftDb: Double = -100.0
    @Published var rightDb: Double = -100.0
    @Published var leftPeakDb: Double = -100.0
    @Published var rightPeakDb: Double = -100.0

    // Silence status
    @Published var silenceStatus: String = "ok"  // ok, warning, alert

    // Metadata
    @Published var codec: String = ""
    @Published var bitrate: Int = 0
    @Published var sampleRate: Int = 0
    @Published var channels: Int = 0
    @Published var metadataSummary: String = ""

    // Uptime
    @Published var uptimeSeconds: Double = 0
    @Published var uptimeFormatted: String = ""

    // Clients
    @Published var clientCount: Int = 0

    // Mic
    @Published var micActive: Bool = false
    @Published var micMode: String = ""  // talkback, source

    // Tunnel
    @Published var tunnelStatus: String = "disconnected"
    @Published var tunnelError: String? = nil
    @Published var tunnelPublicURL: String? = nil

    // Log entries
    @Published var logEntries: [LogEntry] = []

    // Sources
    @Published var sources: [StreamSource] = []

    // Config (from server)
    @Published var config: StreamConfig? = nil

    // Server profiles
    @Published var savedServers: [ServerProfile] = [] {
        didSet { saveServers() }
    }

    func addLog(_ message: String, level: String = "info") {
        let entry = LogEntry(timestamp: Date(), message: message, level: level)
        logEntries.append(entry)
        if logEntries.count > 500 {
            logEntries.removeFirst(logEntries.count - 500)
        }
    }

    // Persistence for server profiles
    private let serversKey = "savedServers"

    func loadServers() {
        guard let data = UserDefaults.standard.data(forKey: serversKey),
              let servers = try? JSONDecoder().decode([ServerProfile].self, from: data) else {
            return
        }
        savedServers = servers
    }

    func saveServers() {
        if let data = try? JSONEncoder().encode(savedServers) {
            UserDefaults.standard.set(data, forKey: serversKey)
        }
    }
}
