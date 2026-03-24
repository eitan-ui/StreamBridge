import Foundation

struct AudioLevels: Codable {
    var leftDb: Double = -100.0
    var rightDb: Double = -100.0
    var leftPeakDb: Double = -100.0
    var rightPeakDb: Double = -100.0

    enum CodingKeys: String, CodingKey {
        case leftDb = "left_db"
        case rightDb = "right_db"
        case leftPeakDb = "left_peak_db"
        case rightPeakDb = "right_peak_db"
    }

    var isSilence: Bool {
        leftDb < -50.0 && rightDb < -50.0
    }
}
