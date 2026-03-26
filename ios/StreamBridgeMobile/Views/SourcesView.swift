import SwiftUI

struct SourcesView: View {
    @EnvironmentObject var appState: AppState
    @EnvironmentObject var api: StreamBridgeAPI

    @State private var showAddSheet = false
    @State private var editingSource: StreamSource? = nil
    @State private var newName = ""
    @State private var newURL = ""
    @State private var newNotes = ""

    var body: some View {
        NavigationStack {
            Group {
                if appState.sources.isEmpty {
                    ContentUnavailableView(
                        "No Sources",
                        systemImage: "antenna.radiowaves.left.and.right",
                        description: Text("Add stream sources to quickly switch between them")
                    )
                } else {
                    List {
                        ForEach(appState.sources) { source in
                            Button {
                                editingSource = source
                                newName = source.name
                                newURL = source.url
                                newNotes = source.notes
                            } label: {
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(source.name)
                                        .font(.headline)
                                    Text(source.url)
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                        .lineLimit(1)
                                        .truncationMode(.middle)
                                    if !source.notes.isEmpty {
                                        Text(source.notes)
                                            .font(.caption2)
                                            .foregroundStyle(.tertiary)
                                    }
                                }
                            }
                            .buttonStyle(.plain)
                        }
                        .onDelete(perform: deleteSources)
                    }
                    .listStyle(.insetGrouped)
                }
            }
            .navigationTitle("Sources")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        newName = ""
                        newURL = ""
                        newNotes = ""
                        showAddSheet = true
                    } label: {
                        Image(systemName: "plus")
                    }
                }
                ToolbarItem(placement: .topBarLeading) {
                    Button {
                        refreshSources()
                    } label: {
                        Image(systemName: "arrow.clockwise")
                    }
                }
            }
            .sheet(isPresented: $showAddSheet) {
                sourceForm(title: "Add Source") {
                    Task {
                        try? await api.addSource(name: newName, url: newURL, notes: newNotes)
                        refreshSources()
                        showAddSheet = false
                    }
                }
            }
            .sheet(item: $editingSource) { source in
                sourceForm(title: "Edit Source") {
                    Task {
                        try? await api.updateSource(
                            index: source.index,
                            name: newName, url: newURL, notes: newNotes
                        )
                        refreshSources()
                        editingSource = nil
                    }
                }
            }
        }
    }

    private func sourceForm(title: String, onSave: @escaping () -> Void) -> some View {
        NavigationStack {
            Form {
                TextField("Name", text: $newName)
                TextField("Stream URL", text: $newURL)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                TextField("Notes (optional)", text: $newNotes)
            }
            .navigationTitle(title)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        showAddSheet = false
                        editingSource = nil
                    }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        onSave()
                    }
                    .disabled(newName.isEmpty || newURL.isEmpty)
                }
            }
        }
    }

    private func deleteSources(at offsets: IndexSet) {
        for index in offsets {
            let source = appState.sources[index]
            Task {
                try? await api.deleteSource(index: source.index)
                refreshSources()
            }
        }
    }

    private func refreshSources() {
        Task {
            if let resp = try? await api.getSources() {
                appState.sources = resp.sources
            }
        }
    }
}
