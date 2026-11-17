// macOS 14+，只调用系统 Vision；不上传图片、不下载第三方模型。
import Foundation
import Vision
import CoreImage
import ImageIO

do {
    guard CommandLine.arguments.count == 3 else {
        throw NSError(domain: "cutout", code: 1, userInfo: [NSLocalizedDescriptionKey: "需要输入图和输出 PNG"])
    }
    guard #available(macOS 14.0, *) else {
        throw NSError(domain: "cutout", code: 2, userInfo: [NSLocalizedDescriptionKey: "本地抠图需要 macOS 14+"])
    }
    let handler = VNImageRequestHandler(url: URL(fileURLWithPath: CommandLine.arguments[1]))
    let request = VNGenerateForegroundInstanceMaskRequest()
    try handler.perform([request])
    guard let observation = request.results?.first, !observation.allInstances.isEmpty else {
        throw NSError(domain: "cutout", code: 3, userInfo: [NSLocalizedDescriptionKey: "没有可分离的前景主体；请裁切主体后重试"])
    }
    let pixels = try observation.generateMaskedImage(ofInstances: observation.allInstances, from: handler, croppedToInstancesExtent: false)
    let image = CIImage(cvPixelBuffer: pixels)
    let colorSpace = CGColorSpace(name: CGColorSpace.sRGB)!
    try CIContext().writePNGRepresentation(of: image, to: URL(fileURLWithPath: CommandLine.arguments[2]), format: .RGBA8, colorSpace: colorSpace)
    print("{\"backend\":\"apple-vision\",\"instances\":\(observation.allInstances.count)}")
} catch {
    FileHandle.standardError.write(Data((error.localizedDescription + "\n").utf8))
    exit(1)
}
