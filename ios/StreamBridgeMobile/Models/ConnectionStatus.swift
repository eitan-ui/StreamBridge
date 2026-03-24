import Foundation

enum ConnectionStatus: String {
    case disconnected
    case connecting
    case connected
    case error
}

struct ServerProfile: Codable, Identifiable, Hashable {
    var id = UUID()
    var name: String
    var host: String
    var port: Int = 9000
    var token: String = ""

    var baseURL: String {
        "http://\(host):\(port)"
    }
}

struct LogEntry: Identifiable {
    let id = UUID()
    let timestamp: Date
    let message: String
    let level: String  // info, warning, error

    var timeString: String {
        let formatter = DateFormatter()
        formatter.dateFormat = "HH:mm:ss"
        return formatter.string(from: timestamp)
    }
}
