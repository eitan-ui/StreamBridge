import Foundation

struct StreamConfig: Codable {
    var port: Int = 9000
    var audioInputDevice: String = ""
    var opusBitrate: Int = 128
    var ffmpegPath: String = "ffmpeg"
    var silence: SilenceConfig = SilenceConfig()
    var reconnect: ReconnectConfig = ReconnectConfig()
    var alerts: AlertConfig = AlertConfig()
    var mairlist: MairListConfig = MairListConfig()
    var api: ApiConfig = ApiConfig()
    var tunnel: TunnelConfig = TunnelConfig()
    var schedule: ScheduleConfig = ScheduleConfig()

    enum CodingKeys: String, CodingKey {
        case port
        case audioInputDevice = "audio_input_device"
        case opusBitrate = "opus_bitrate"
        case ffmpegPath = "ffmpeg_path"
        case silence, reconnect, alerts, mairlist, api, tunnel, schedule
    }
}

struct SilenceConfig: Codable {
    var thresholdDb: Double = -50.0
    var warningDelayS: Int = 10
    var alertDelayS: Int = 30
    var autoStop: SilenceAutoStopConfig = SilenceAutoStopConfig()

    enum CodingKeys: String, CodingKey {
        case thresholdDb = "threshold_db"
        case warningDelayS = "warning_delay_s"
        case alertDelayS = "alert_delay_s"
        case autoStop = "auto_stop"
    }
}

struct SilenceAutoStopConfig: Codable {
    var enabled: Bool = false
    var delayS: Double = 2.0
    var toneDetectionEnabled: Bool = false
    var toneMaxCrestDb: Double = 6.0
    var triggerMairlist: Bool = true
    var stopStream: Bool = true

    enum CodingKeys: String, CodingKey {
        case enabled
        case delayS = "delay_s"
        case toneDetectionEnabled = "tone_detection_enabled"
        case toneMaxCrestDb = "tone_max_crest_db"
        case triggerMairlist = "trigger_mairlist"
        case stopStream = "stop_stream"
    }
}

struct ReconnectConfig: Codable {
    var initialDelayS: Double = 2.0
    var maxDelayS: Double = 60.0
    var maxRetries: Int = 0

    enum CodingKeys: String, CodingKey {
        case initialDelayS = "initial_delay_s"
        case maxDelayS = "max_delay_s"
        case maxRetries = "max_retries"
    }
}

struct AlertConfig: Codable {
    var soundEnabled: Bool = true
    var whatsapp: WhatsAppConfig = WhatsAppConfig()

    enum CodingKeys: String, CodingKey {
        case soundEnabled = "sound_enabled"
        case whatsapp
    }
}

struct WhatsAppConfig: Codable {
    var enabled: Bool = false
    var service: String = "callmebot"
    var phone: String = ""
    var apiKey: String = ""
    var customUrl: String = ""

    enum CodingKeys: String, CodingKey {
        case enabled, service, phone
        case apiKey = "api_key"
        case customUrl = "custom_url"
    }
}

struct MairListConfig: Codable {
    var enabled: Bool = false
    var apiUrl: String = "http://localhost:9000"
    var command: String = "PLAYER A NEXT"
    var silenceCommand: String = "PLAYER A NEXT"
    var toneCommand: String = "PLAYER A NEXT"

    enum CodingKeys: String, CodingKey {
        case enabled
        case apiUrl = "api_url"
        case command
        case silenceCommand = "silence_command"
        case toneCommand = "tone_command"
    }
}

struct ApiConfig: Codable {
    var allowRemote: Bool = false

    enum CodingKeys: String, CodingKey {
        case allowRemote = "allow_remote"
    }
}

struct TunnelConfig: Codable {
    var enabled: Bool = false
    var host: String = ""
    var port: Int = 22
    var username: String = ""
    var keyPath: String = ""
    var remotePort: Int = 9000

    enum CodingKeys: String, CodingKey {
        case enabled, host, port, username
        case keyPath = "key_path"
        case remotePort = "remote_port"
    }
}

struct ScheduleEntry: Codable {
    var time: String = ""
    var url: String = ""
    var enabled: Bool = true
}

struct ScheduleConfig: Codable {
    var enabled: Bool = false
    var entries: [ScheduleEntry] = []
}
