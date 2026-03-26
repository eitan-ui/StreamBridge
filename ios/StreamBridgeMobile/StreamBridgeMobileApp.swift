import SwiftUI

@main
struct StreamBridgeMobileApp: App {
    @StateObject private var appState = AppState()
    @StateObject private var api = StreamBridgeAPI()
    @StateObject private var wsManager = WebSocketManager()
    @StateObject private var connectionManager = ConnectionManager()
    @StateObject private var micService = MicCaptureService()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(appState)
                .environmentObject(api)
                .environmentObject(wsManager)
                .environmentObject(connectionManager)
                .environmentObject(micService)
                .onAppear {
                    appState.loadServers()
                    wsManager.appState = appState
                    micService.configure(webSocketManager: wsManager)
                }
        }
    }
}

struct ContentView: View {
    @EnvironmentObject var appState: AppState

    var body: some View {
        if appState.isConnected {
            MainTabView()
        } else {
            ConnectView()
        }
    }
}

struct MainTabView: View {
    var body: some View {
        TabView {
            DashboardView()
                .tabItem {
                    Image(systemName: "gauge.medium")
                    Text("Dashboard")
                }

            MicStreamView()
                .tabItem {
                    Image(systemName: "mic.fill")
                    Text("Mic")
                }

            SourcesView()
                .tabItem {
                    Image(systemName: "antenna.radiowaves.left.and.right")
                    Text("Sources")
                }

            SettingsView()
                .tabItem {
                    Image(systemName: "gearshape")
                    Text("Settings")
                }
        }
        .tint(.blue)
    }
}
