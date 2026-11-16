import Foundation
import Vision
import ImageIO
import CoreGraphics

// Input/boxes use image pixels, top-left origin. This program never captures a screen.
struct TextBox: Codable {
    let text: String
    let box: [Double]
    let confidence: Float
}
struct OCRResult: Codable {
    let width: Int
    let height: Int
    let coordinate_space: String
    let results: [TextBox]
}
enum OCRError: Error { case invalidArguments, invalidImage, invalidRegion }

func recognize(_ arguments: [String]) throws -> OCRResult {
    guard arguments.count == 1 || (arguments.count == 3 && arguments[1] == "--region") else {
        throw OCRError.invalidArguments
    }
    let url = URL(fileURLWithPath: arguments[0])
    guard let source = CGImageSourceCreateWithURL(url as CFURL, nil),
          let original = CGImageSourceCreateImageAtIndex(source, 0, nil) else {
        throw OCRError.invalidImage
    }
    var region = CGRect(x: 0, y: 0, width: original.width, height: original.height)
    if arguments.count == 3 {
        let values = arguments[2].split(separator: ",").compactMap { Double($0) }
        guard values.count == 4, values.allSatisfy({ $0.isFinite }),
              values[0] >= 0, values[1] >= 0, values[2] > 0, values[3] > 0 else {
            throw OCRError.invalidRegion
        }
        region = CGRect(x: values[0], y: values[1], width: values[2], height: values[3]).integral
        guard CGRect(x: 0, y: 0, width: original.width, height: original.height).contains(region) else {
            throw OCRError.invalidRegion
        }
    }
    guard let image = original.cropping(to: region) else { throw OCRError.invalidRegion }
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.recognitionLanguages = ["zh-Hans", "en-US"]
    request.usesLanguageCorrection = false
    try VNImageRequestHandler(cgImage: image, options: [:]).perform([request])
    let rows = (request.results ?? []).compactMap { observation -> TextBox? in
        guard let candidate = observation.topCandidates(1).first else { return nil }
        let b = observation.boundingBox
        return TextBox(text: candidate.string,
                       box: [region.minX + b.minX * region.width,
                             region.minY + (1 - b.maxY) * region.height,
                             b.width * region.width, b.height * region.height],
                       confidence: candidate.confidence)
    }.sorted { a, b in
        if abs(a.box[1] - b.box[1]) < min(a.box[3], b.box[3]) / 2 { return a.box[0] < b.box[0] }
        return a.box[1] < b.box[1]
    }
    return OCRResult(width: original.width, height: original.height,
                     coordinate_space: "image pixels, top-left origin", results: rows)
}

do {
    let result = try recognize(Array(CommandLine.arguments.dropFirst()))
    let encoder = JSONEncoder()
    encoder.outputFormatting = [.sortedKeys]
    FileHandle.standardOutput.write(try encoder.encode(result))
    FileHandle.standardOutput.write(Data("\n".utf8))
} catch {
    fputs("ocr: \(error). Usage: ocr image.png [--region x,y,w,h]\n", stderr)
    exit(2)
}
