import Foundation
import Network
import Combine

@MainActor
class ConnectionManager: ObservableObject {
    @Published var discoveredServers: [DiscoveredServer] = []
    @Published var isScanning = false

    private var browser: NWBrowser?

    struct DiscoveredServer: Identifiable, Hashable {
        let id = UUID()
        let name: String
        let host: String
        let port: Int
    }

    func startScanning() {
        isScanning = true
        discoveredServers.removeAll()

        let parameters = NWParameters()
        parameters.includePeerToPeer = true

        browser = NWBrowser(for: .bonjour(type: "_streambridge._tcp", domain: nil), using: parameters)

        browser?.browseResultsChangedHandler = { [weak self] results, changes in
            Task { @MainActor in
                guard let self = self else { return }
                var servers: [DiscoveredServer] = []
                for result in results {
                    if case .service(let name, _, _, _) = result.endpoint {
                        // Resolve the service to get host/port
                        servers.append(DiscoveredServer(
                            name: name,
                            host: name + ".local",
                            port: 9000
                        ))
                    }
                }
                self.discoveredServers = servers
            }
        }

        browser?.stateUpdateHandler = { [weak self] state in
            Task { @MainActor in
                switch state {
                case .failed(_):
                    self?.isScanning = false
                case .cancelled:
                    self?.isScanning = false
                default:
                    break
                }
            }
        }

        browser?.start(queue: .main)

        // Auto-stop after 10 seconds
        Task {
            try? await Task.sleep(nanoseconds: 10_000_000_000)
            self.stopScanning()
        }
    }

    func stopScanning() {
        browser?.cancel()
        browser = nil
        isScanning = false
    }
}
