import Foundation

struct PlaylistItem: Codable, Identifiable {
    var id: Int { index }
    let index: Int
    var title: String
    var artist: String
    var duration: String
    var cueIn: String
    var cueOut: String
    var fadeIn: String
    var fadeOut: String
    var startNext: String
    var hardFixTime: String
    var softFixTime: String
    var itemType: String

    enum CodingKeys: String, CodingKey {
        case index, title, artist, duration
        case cueIn = "cue_in"
        case cueOut = "cue_out"
        case fadeIn = "fade_in"
        case fadeOut = "fade_out"
        case startNext = "start_next"
        case hardFixTime = "hard_fix_time"
        case softFixTime = "soft_fix_time"
        case itemType = "item_type"
    }
}
