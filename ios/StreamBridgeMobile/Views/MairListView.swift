import SwiftUI

struct MairListView: View {
    @EnvironmentObject var appState: AppState
    @EnvironmentObject var api: StreamBridgeAPI

    @State private var playlistNumber: Int = 1
    @State private var selectedPlayer: String = "A"
    @State private var playlistItems: [PlaylistItem] = []
    @State private var isLoading = false
    @State private var statusMessage: String = ""

    private let players = ["A", "B", "C", "D"]

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Player transport
                transportControls

                Divider()

                // Playlist controls
                playlistHeader

                Divider()

                // Playlist items
                if isLoading {
                    ProgressView("Loading playlist...")
                        .frame(maxHeight: .infinity)
                } else if playlistItems.isEmpty {
                    ContentUnavailableView(
                        "No Playlist",
                        systemImage: "music.note.list",
                        description: Text("Tap Refresh to load playlist from mAirList")
                    )
                } else {
                    playlistTable
                }

                // Status bar
                if !statusMessage.isEmpty {
                    Text(statusMessage)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .padding(.horizontal)
                        .padding(.vertical, 4)
                }
            }
            .navigationTitle("mAirList")
        }
    }

    // MARK: - Transport

    private var transportControls: some View {
        VStack(spacing: 12) {
            // Player selector
            Picker("Player", selection: $selectedPlayer) {
                ForEach(players, id: \.self) { p in
                    Text("Player \(p)").tag(p)
                }
            }
            .pickerStyle(.segmented)
            .padding(.horizontal)

            // Transport buttons
            HStack(spacing: 16) {
                transportButton("backward.end.fill", action: "PREVIOUS")
                transportButton("stop.fill", action: "STOP")
                transportButton("pause.fill", action: "PAUSE")
                transportButton("play.fill", action: "START", color: .green)
                transportButton("forward.end.fill", action: "NEXT")
            }
            .padding(.horizontal)

            // Custom command
            HStack {
                Button {
                    Task {
                        try? await api.sendMairListCommand("PLAYLIST \(playlistNumber) START")
                        statusMessage = "Playlist \(playlistNumber) started"
                    }
                } label: {
                    Text("PLAYLIST START")
                        .font(.caption.bold())
                        .padding(.horizontal, 12)
                        .padding(.vertical, 6)
                        .background(.blue)
                        .foregroundStyle(.white)
                        .cornerRadius(6)
                }
            }
        }
        .padding(.vertical, 12)
    }

    private func transportButton(_ icon: String, action: String, color: Color = .primary) -> some View {
        Button {
            Task {
                try? await api.playerAction(player: selectedPlayer, action: action)
                statusMessage = "\(action) sent to Player \(selectedPlayer)"
            }
        } label: {
            Image(systemName: icon)
                .font(.title2)
                .foregroundStyle(color)
                .frame(width: 44, height: 44)
                .background(.ultraThinMaterial)
                .cornerRadius(8)
        }
    }

    // MARK: - Playlist Header

    private var playlistHeader: some View {
        HStack {
            Text("Playlist")
                .font(.headline)

            Stepper(value: $playlistNumber, in: 1...10) {
                Text("\(playlistNumber)")
                    .font(.headline.monospacedDigit())
            }
            .frame(width: 140)

            Spacer()

            Button {
                loadPlaylist()
            } label: {
                Image(systemName: "arrow.clockwise")
            }
        }
        .padding()
    }

    // MARK: - Playlist Table

    private var playlistTable: some View {
        List(playlistItems) { item in
            VStack(alignment: .leading, spacing: 4) {
                HStack {
                    Text("\(item.index + 1)")
                        .font(.caption.bold().monospacedDigit())
                        .foregroundStyle(.secondary)
                        .frame(width: 24)

                    VStack(alignment: .leading) {
                        Text(item.title)
                            .font(.subheadline.bold())
                            .lineLimit(1)
                        if !item.artist.isEmpty {
                            Text(item.artist)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                                .lineLimit(1)
                        }
                    }

                    Spacer()

                    Text(item.duration)
                        .font(.caption.monospacedDigit())
                        .foregroundStyle(.secondary)
                }

                // Timing info
                HStack(spacing: 8) {
                    timingBadge("In", value: item.cueIn)
                    timingBadge("Out", value: item.cueOut)
                    timingBadge("Fade", value: item.fadeOut)
                    if !item.hardFixTime.isEmpty {
                        timingBadge("Fix", value: item.hardFixTime, color: .red)
                    }
                    if !item.itemType.isEmpty {
                        Text(item.itemType)
                            .font(.caption2)
                            .padding(.horizontal, 4)
                            .padding(.vertical, 1)
                            .background(.blue.opacity(0.2))
                            .cornerRadius(3)
                    }
                }
            }
            .padding(.vertical, 2)
        }
        .listStyle(.plain)
    }

    private func timingBadge(_ label: String, value: String, color: Color = .secondary) -> some View {
        let display = value.hasPrefix("00:00:00") ? "" : value
        return Group {
            if !display.isEmpty {
                Text("\(label): \(display)")
                    .font(.caption2.monospacedDigit())
                    .foregroundStyle(color)
            }
        }
    }

    // MARK: - Actions

    private func loadPlaylist() {
        isLoading = true
        Task {
            do {
                let response = try await api.getPlaylist(number: playlistNumber)
                playlistItems = response.items
                statusMessage = "\(response.items.count) items loaded"
            } catch {
                statusMessage = "Failed: \(error.localizedDescription)"
            }
            isLoading = false
        }
    }
}
