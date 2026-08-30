import AVFoundation
import ARKit

/// Writes the video-tier walkthrough clip straight from ARKit's captured frames.
///
/// The clip is the *only* thing the pipeline sees at this tier, so it is written
/// at the session's native resolution with a high bitrate: the video tier already
/// gives up depth and poses, and throwing away texture detail on top of that
/// would put the ±3% wall-length gate out of reach for no good reason.
final class VideoRecorder {

    private var writer: AVAssetWriter?
    private var input: AVAssetWriterInput?
    private var adaptor: AVAssetWriterInputPixelBufferAdaptor?
    private var startTime: CMTime?
    private var lastTime: CMTime?
    private(set) var frameCount = 0
    private(set) var size: CGSize = .zero

    var isRecording: Bool { writer != nil }

    func start(url: URL, width: Int, height: Int) throws {
        try? FileManager.default.removeItem(at: url)
        let writer = try AVAssetWriter(outputURL: url, fileType: .mov)

        let bitrate = max(12_000_000, width * height * 4)
        let settings: [String: Any] = [
            AVVideoCodecKey: AVVideoCodecType.h264,
            AVVideoWidthKey: width,
            AVVideoHeightKey: height,
            AVVideoCompressionPropertiesKey: [
                AVVideoAverageBitRateKey: bitrate,
                AVVideoMaxKeyFrameIntervalKey: 30,
                AVVideoProfileLevelKey: AVVideoProfileLevelH264HighAutoLevel,
            ],
        ]
        let input = AVAssetWriterInput(mediaType: .video, outputSettings: settings)
        input.expectsMediaDataInRealTime = true
        // ARKit hands us landscape buffers while the operator holds the phone
        // upright; rotate in the container rather than resampling every frame.
        input.transform = CGAffineTransform(rotationAngle: .pi / 2)

        let adaptor = AVAssetWriterInputPixelBufferAdaptor(
            assetWriterInput: input,
            sourcePixelBufferAttributes: [
                kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_420YpCbCr8BiPlanarFullRange,
                kCVPixelBufferWidthKey as String: width,
                kCVPixelBufferHeightKey as String: height,
            ])

        guard writer.canAdd(input) else {
            throw NSError(domain: "ai.cozmo.video", code: 1,
                          userInfo: [NSLocalizedDescriptionKey: "Asset writer rejected the video input."])
        }
        writer.add(input)
        guard writer.startWriting() else {
            throw writer.error ?? NSError(domain: "ai.cozmo.video", code: 2)
        }

        self.writer = writer
        self.input = input
        self.adaptor = adaptor
        self.size = CGSize(width: width, height: height)
        self.frameCount = 0
        self.startTime = nil
    }

    func append(_ buffer: CVPixelBuffer, timestamp: TimeInterval) {
        guard let writer, let input, let adaptor else { return }
        let time = CMTime(seconds: timestamp, preferredTimescale: 1_000_000)
        if startTime == nil {
            writer.startSession(atSourceTime: time)
            startTime = time
        }
        guard input.isReadyForMoreMediaData else { return }
        adaptor.append(buffer, withPresentationTime: time)
        lastTime = time
        frameCount += 1
    }

    /// Returns the clip duration once the file is closed. Duration is measured
    /// from the presentation timestamps we actually appended rather than asked
    /// of the writer, so a dropped tail cannot inflate it.
    func finish(completion: @escaping (Double) -> Void) {
        guard let writer, let input else { completion(0); return }
        input.markAsFinished()
        let span: Double = {
            guard let s = startTime, let l = lastTime else { return 0 }
            return max(0, (l - s).seconds)
        }()
        writer.finishWriting { [weak self] in
            self?.writer = nil
            self?.input = nil
            self?.adaptor = nil
            completion(span)
        }
    }
}
