// Person mask + face box for make_portrait.py, using the Vision framework that
// ships with macOS, so there's no model to download.
//
//   swift scripts/cutout.swift <photo> <mask.png>
//
// Writes a grayscale mask (white = person) the same size as the photo and
// prints the largest face as JSON in top-left normalised coords.
import AppKit
import CoreImage
import Foundation
import Vision

let args = CommandLine.arguments
guard args.count == 3 else {
    FileHandle.standardError.write("usage: swift cutout.swift <photo> <mask.png>\n".data(using: .utf8)!)
    exit(2)
}

guard let photo = CIImage(contentsOf: URL(fileURLWithPath: args[1]), options: [.applyOrientationProperty: true]) else {
    FileHandle.standardError.write("could not read \(args[1])\n".data(using: .utf8)!)
    exit(1)
}

let person = VNGeneratePersonSegmentationRequest()
person.qualityLevel = .accurate
person.outputPixelFormat = kCVPixelFormatType_OneComponent8
let faces = VNDetectFaceRectanglesRequest()

try VNImageRequestHandler(ciImage: photo).perform([person, faces])

guard let buffer = person.results?.first?.pixelBuffer else {
    FileHandle.standardError.write("no person found in the photo\n".data(using: .utf8)!)
    exit(1)
}

// the mask comes back at a lower resolution, stretch it over the photo
var mask = CIImage(cvPixelBuffer: buffer)
mask = mask.transformed(by: CGAffineTransform(scaleX: photo.extent.width / mask.extent.width,
                                              y: photo.extent.height / mask.extent.height))
try CIContext().writePNGRepresentation(of: mask, to: URL(fileURLWithPath: args[2]),
                                       format: .L8, colorSpace: CGColorSpaceCreateDeviceGray())

// Vision's origin is bottom-left, flip to top-left for PIL
if let face = faces.results?.max(by: { $0.boundingBox.width < $1.boundingBox.width }) {
    let b = face.boundingBox
    print("{\"face\": [\(b.minX), \(1 - b.maxY), \(b.width), \(b.height)]}")
} else {
    print("{\"face\": null}")
}
