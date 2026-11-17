import Foundation
import Vision
import ImageIO

var output: [[String: Any]] = []
for file in CommandLine.arguments.dropFirst() {
    do {
        let url = URL(fileURLWithPath: file)
        guard let source = CGImageSourceCreateWithURL(url as CFURL, nil), let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else {
            throw NSError(domain: "readability", code: 1, userInfo: [NSLocalizedDescriptionKey: "无法读取文字截图"])
        }
        let request = VNRecognizeTextRequest()
        request.recognitionLevel = .accurate
        request.recognitionLanguages = ["zh-Hans", "en-US"]
        request.usesLanguageCorrection = false
        try VNImageRequestHandler(cgImage: image).perform([request])
        let words: [[String: Any]] = (request.results ?? []).compactMap { observation in
            guard let candidate = observation.topCandidates(1).first else { return nil }
            return ["text": candidate.string, "confidence": candidate.confidence, "heightPx": observation.boundingBox.height * Double(image.height)]
        }
        output.append(["file": file, "width": image.width, "height": image.height, "words": words])
    } catch { output.append(["file": file, "error": error.localizedDescription]) }
}
let data = try JSONSerialization.data(withJSONObject: output, options: [.sortedKeys])
print(String(data: data, encoding: .utf8)!)
