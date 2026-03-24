import Foundation

class StreamBridgeAPI: ObservableObject {
    private var baseURL: String = ""
    private var token: String = ""
    private let session: URLSession

    init() {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 10
        self.session = URLSession(configuration: config)
    }

    func configure(baseURL: String, token: String) {
        self.baseURL = baseURL.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        self.token = token
    }

    // MARK: - State

    func getState() async throws -> AppStateResponse {
        return try await get("/api/v1/state")
    }

    // MARK: - Stream Control

    func startStream(url: String? = nil, device: String? = nil) async throws {
        var body: [String: String] = [:]
        if let url = url { body["url"] = url }
        if let device = device { body["device"] = device }
        let _: StatusResponse = try await post("/api/v1/stream/start", body: body)
    }

    func stopStream() async throws {
        let _: StatusResponse = try await post("/api/v1/stream/stop", body: [:] as [String: String])
    }

    // MARK: - Config

    func getConfig() async throws -> StreamConfig {
        return try await get("/api/v1/config")
    }

    func updateConfig(_ updates: [String: Any]) async throws {
        let _: StatusResponse = try await putRaw("/api/v1/config", body: updates)
    }

    // MARK: - Sources

    func getSources() async throws -> SourcesResponse {
        return try await get("/api/v1/sources")
    }

    func addSource(name: String, url: String, notes: String = "") async throws {
        let body = ["name": name, "url": url, "notes": notes]
        let _: StatusResponse = try await post("/api/v1/sources", body: body)
    }

    func updateSource(index: Int, name: String, url: String, notes: String = "") async throws {
        let body = ["name": name, "url": url, "notes": notes]
        let _: StatusResponse = try await put("/api/v1/sources/\(index)", body: body)
    }

    func deleteSource(index: Int) async throws {
        let _: StatusResponse = try await delete("/api/v1/sources/\(index)")
    }

    // MARK: - mAirList

    func sendMairListCommand(_ command: String) async throws {
        let body = ["command": command]
        let _: StatusResponse = try await post("/api/v1/mairlist/command", body: body)
    }

    func getPlaylist(number: Int) async throws -> PlaylistResponse {
        return try await get("/api/v1/mairlist/playlist/\(number)")
    }

    func playerAction(player: String, action: String) async throws {
        let body = ["action": action]
        let _: StatusResponse = try await post("/api/v1/mairlist/player/\(player)/action", body: body)
    }

    // MARK: - Alerts

    func testAlert() async throws {
        let _: StatusResponse = try await post("/api/v1/alerts/test", body: [:] as [String: String])
    }

    // MARK: - Mic

    func startMic(mode: String) async throws {
        let body = ["mode": mode]
        let _: StatusResponse = try await post("/api/v1/mic/start", body: body)
    }

    func stopMic() async throws {
        let _: StatusResponse = try await post("/api/v1/mic/stop", body: [:] as [String: String])
    }

    // MARK: - HTTP Helpers

    private func makeRequest(_ path: String, method: String) -> URLRequest {
        let url = URL(string: "\(baseURL)\(path)")!
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if !token.isEmpty {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        return request
    }

    private func get<T: Decodable>(_ path: String) async throws -> T {
        let request = makeRequest(path, method: "GET")
        let (data, response) = try await session.data(for: request)
        try checkResponse(response)
        return try JSONDecoder().decode(T.self, from: data)
    }

    private func post<T: Decodable, B: Encodable>(_ path: String, body: B) async throws -> T {
        var request = makeRequest(path, method: "POST")
        request.httpBody = try JSONEncoder().encode(body)
        let (data, response) = try await session.data(for: request)
        try checkResponse(response)
        return try JSONDecoder().decode(T.self, from: data)
    }

    private func put<T: Decodable, B: Encodable>(_ path: String, body: B) async throws -> T {
        var request = makeRequest(path, method: "PUT")
        request.httpBody = try JSONEncoder().encode(body)
        let (data, response) = try await session.data(for: request)
        try checkResponse(response)
        return try JSONDecoder().decode(T.self, from: data)
    }

    private func putRaw<T: Decodable>(_ path: String, body: [String: Any]) async throws -> T {
        var request = makeRequest(path, method: "PUT")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        let (data, response) = try await session.data(for: request)
        try checkResponse(response)
        return try JSONDecoder().decode(T.self, from: data)
    }

    private func delete<T: Decodable>(_ path: String) async throws -> T {
        let request = makeRequest(path, method: "DELETE")
        let (data, response) = try await session.data(for: request)
        try checkResponse(response)
        return try JSONDecoder().decode(T.self, from: data)
    }

    private func checkResponse(_ response: URLResponse) throws {
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        if httpResponse.statusCode == 401 {
            throw APIError.unauthorized
        }
        guard (200...299).contains(httpResponse.statusCode) else {
            throw APIError.httpError(httpResponse.statusCode)
        }
    }
}

// MARK: - Response Types

struct AppStateResponse: Codable {
    let streamState: String
    let isStreaming: Bool
    let audioLevels: AudioLevels
    let silenceStatus: String
    let metadata: MetadataResponse?
    let uptimeSeconds: Double
    let clientCount: Int
    let micActive: Bool
    let micMode: String

    enum CodingKeys: String, CodingKey {
        case streamState = "stream_state"
        case isStreaming = "is_streaming"
        case audioLevels = "audio_levels"
        case silenceStatus = "silence_status"
        case metadata
        case uptimeSeconds = "uptime_seconds"
        case clientCount = "client_count"
        case micActive = "mic_active"
        case micMode = "mic_mode"
    }
}

struct MetadataResponse: Codable {
    let codec: String
    let bitrate: Int
    let sampleRate: Int
    let channels: Int
    let summary: String

    enum CodingKeys: String, CodingKey {
        case codec, bitrate, channels, summary
        case sampleRate = "sample_rate"
    }
}

struct StatusResponse: Codable {
    let status: String
}

struct SourcesResponse: Codable {
    let sources: [StreamSource]
}

struct PlaylistResponse: Codable {
    let playlist: Int
    let items: [PlaylistItem]
}

// Use AudioLevels from Models/AudioLevels.swift — already has CodingKeys

// StreamConfig from Models/StreamConfig.swift — already Codable

enum APIError: LocalizedError {
    case invalidResponse
    case unauthorized
    case httpError(Int)

    var errorDescription: String? {
        switch self {
        case .invalidResponse: return "Invalid server response"
        case .unauthorized: return "Invalid API token"
        case .httpError(let code): return "Server error (HTTP \(code))"
        }
    }
}
