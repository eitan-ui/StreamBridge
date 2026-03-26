import SwiftUI

struct LogView: View {
    @EnvironmentObject var appState: AppState
    @State private var filterLevel: String = "all"

    private var filteredEntries: [LogEntry] {
        if filterLevel == "all" {
            return appState.logEntries
        }
        return appState.logEntries.filter { $0.level == filterLevel }
    }

    var body: some View {
        VStack(spacing: 0) {
            // Filter bar
            Picker("Filter", selection: $filterLevel) {
                Text("All").tag("all")
                Text("Info").tag("info")
                Text("Warning").tag("warning")
                Text("Error").tag("error")
            }
            .pickerStyle(.segmented)
            .padding()

            // Log entries
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 4) {
                        ForEach(filteredEntries) { entry in
                            HStack(alignment: .top, spacing: 6) {
                                Text(entry.timeString)
                                    .font(.caption2.monospacedDigit())
                                    .foregroundStyle(.secondary)
                                    .frame(width: 60, alignment: .leading)

                                Circle()
                                    .fill(logColor(entry.level))
                                    .frame(width: 6, height: 6)
                                    .padding(.top, 4)

                                Text(entry.message)
                                    .font(.caption)
                                    .foregroundStyle(logColor(entry.level))
                            }
                            .padding(.horizontal)
                            .padding(.vertical, 4)
                            .id(entry.id)
                        }
                    }
                }
                .onChange(of: appState.logEntries.count) { _, _ in
                    if let last = filteredEntries.last {
                        proxy.scrollTo(last.id, anchor: .bottom)
                    }
                }
            }
        }
        .navigationTitle("Event Log")
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button("Clear") {
                    appState.logEntries.removeAll()
                }
            }
        }
    }

    private func logColor(_ level: String) -> Color {
        switch level {
        case "error": return .red
        case "warning": return .yellow
        default: return .secondary
        }
    }
}
