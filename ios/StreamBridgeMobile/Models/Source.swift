import Foundation

struct StreamSource: Codable, Identifiable {
    var id: Int { index }
    let index: Int
    var name: String
    var url: String
    var notes: String = ""
}
