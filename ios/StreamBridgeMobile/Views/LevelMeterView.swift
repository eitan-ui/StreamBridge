import SwiftUI

struct LevelMeterView: View {
    let leftDb: Double
    let rightDb: Double

    private let minDb: Double = -60.0
    private let maxDb: Double = 0.0

    var body: some View {
        VStack(spacing: 6) {
            meterRow(label: "L", db: leftDb)
            meterRow(label: "R", db: rightDb)
        }
    }

    private func meterRow(label: String, db: Double) -> some View {
        HStack(spacing: 8) {
            Text(label)
                .font(.caption.bold().monospacedDigit())
                .foregroundStyle(.secondary)
                .frame(width: 16)

            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    // Background
                    RoundedRectangle(cornerRadius: 3)
                        .fill(Color.gray.opacity(0.2))

                    // Level bar
                    RoundedRectangle(cornerRadius: 3)
                        .fill(meterGradient)
                        .frame(width: barWidth(db: db, totalWidth: geo.size.width))
                        .animation(.linear(duration: 0.05), value: db)
                }
            }
            .frame(height: 10)

            // dB readout
            Text(db > -90 ? String(format: "%.0f", db) : "-inf")
                .font(.caption2.monospacedDigit())
                .foregroundStyle(.secondary)
                .frame(width: 36, alignment: .trailing)
        }
    }

    private var meterGradient: LinearGradient {
        LinearGradient(
            colors: [.green, .green, .yellow, .red],
            startPoint: .leading,
            endPoint: .trailing
        )
    }

    private func barWidth(db: Double, totalWidth: CGFloat) -> CGFloat {
        let clamped = max(minDb, min(maxDb, db))
        let ratio = (clamped - minDb) / (maxDb - minDb)
        return CGFloat(ratio) * totalWidth
    }
}
