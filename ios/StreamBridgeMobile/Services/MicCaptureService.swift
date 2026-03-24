import Foundation
import AVFoundation
import Combine

@MainActor
class MicCaptureService: ObservableObject {
    @Published var isCapturing = false
    @Published var inputLevel: Double = -100.0

    private var audioEngine: AVAudioEngine?
    private var inputNode: AVAudioInputNode?
    private var converter: AVAudioConverter?
    private weak var webSocketManager: WebSocketManager?

    func configure(webSocketManager: WebSocketManager) {
        self.webSocketManager = webSocketManager
    }

    func startCapture() {
        guard !isCapturing else { return }

        // Request mic permission
        AVAudioApplication.requestRecordPermission { [weak self] granted in
            Task { @MainActor in
                guard granted else {
                    self?.inputLevel = -100.0
                    return
                }
                self?.beginCapture()
            }
        }
    }

    private func beginCapture() {
        do {
            let session = AVAudioSession.sharedInstance()
            try session.setCategory(.playAndRecord, mode: .default)
            try session.setActive(true)

            audioEngine = AVAudioEngine()
            guard let engine = audioEngine else { return }

            let inputNode = engine.inputNode
            let inputFormat = inputNode.outputFormat(forBus: 0)

            // Target format: 44100Hz, mono, Float32
            guard let targetFormat = AVAudioFormat(
                commonFormat: .pcmFormatFloat32,
                sampleRate: 44100,
                channels: 1,
                interleaved: false
            ) else { return }

            // Install tap on input
            inputNode.installTap(onBus: 0, bufferSize: 4096, format: inputFormat) { [weak self] buffer, time in
                Task { @MainActor in
                    self?.processAudioBuffer(buffer, format: inputFormat)
                }
            }

            try engine.start()
            isCapturing = true
        } catch {
            print("Audio capture failed: \(error)")
        }
    }

    private func processAudioBuffer(_ buffer: AVAudioPCMBuffer, format: AVAudioFormat) {
        // Calculate input level
        guard let channelData = buffer.floatChannelData else { return }
        let frames = buffer.frameLength
        var sum: Float = 0
        for i in 0..<Int(frames) {
            let sample = channelData[0][i]
            sum += sample * sample
        }
        let rms = sqrt(sum / Float(frames))
        let db = 20 * log10(max(rms, 1e-7))
        inputLevel = Double(db)

        // Convert to PCM Int16 and send via WebSocket
        let pcmData = convertToPCM16(buffer)
        if let data = pcmData {
            webSocketManager?.sendBinaryData(data)
        }
    }

    private func convertToPCM16(_ buffer: AVAudioPCMBuffer) -> Data? {
        guard let channelData = buffer.floatChannelData else { return nil }
        let frames = Int(buffer.frameLength)
        var data = Data(capacity: frames * 2)

        for i in 0..<frames {
            let sample = max(-1.0, min(1.0, channelData[0][i]))
            var int16Sample = Int16(sample * 32767.0)
            data.append(Data(bytes: &int16Sample, count: 2))
        }
        return data
    }

    func stopCapture() {
        audioEngine?.stop()
        audioEngine?.inputNode.removeTap(onBus: 0)
        audioEngine = nil
        isCapturing = false
        inputLevel = -100.0

        try? AVAudioSession.sharedInstance().setActive(false)
    }
}
