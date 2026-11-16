import AppKit
import CoreGraphics
import Foundation
import Darwin

// rec-shot stops both native recording and this logger with SIGINT; flush samples.
nonisolated(unsafe) var shouldStop = false
signal(SIGINT) { _ in shouldStop = true }
signal(SIGTERM) { _ in shouldStop = true }

// Read-only polling. No event tap, event synthesis or permission request.
let argv = Array(CommandLine.arguments.dropFirst())
if argv.first == "--geometry" {
    let windows = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]] ?? []
    let own = windows.filter { ($0[kCGWindowOwnerName as String] as? String) == "Google Chrome" && ($0[kCGWindowName as String] as? String) == "Example Domain" }
    let rows = own.map { ["window_id": $0[kCGWindowNumber as String] ?? 0, "bounds_points": $0[kCGWindowBounds as String] ?? [:]] }
    let screens = NSScreen.screens.map { s -> [String: Any] in
        ["origin": [s.frame.origin.x,s.frame.origin.y], "size_points": [s.frame.width,s.frame.height], "backing_scale": s.backingScaleFactor]
    }
    let data = try JSONSerialization.data(withJSONObject: ["own_test_windows":rows,"screens":screens], options:.sortedKeys)
    FileHandle.standardOutput.write(data);exit(0)
}
guard argv.count >= 3, let duration = Double(argv[0]), duration > 0, let epoch = Double(argv[2]) else {
    fputs("usage: cursorlog <seconds> <out.json> <recording-launch-unix-seconds> [x,y,w,h]\n", stderr);exit(2)
}
let out = URL(fileURLWithPath:argv[1])
let region = argv.count > 3 ? argv[3].split(separator:",").compactMap { Double($0) } : []
if !region.isEmpty && region.count != 4 {fputs("invalid region\n",stderr);exit(2)}
let originX = region.isEmpty ? 0 : region[0]
let originY = region.isEmpty ? 0 : region[1]
let wallAnchor = Date().timeIntervalSince1970
let monoAnchor = ProcessInfo.processInfo.systemUptime
var rows = [[String:Any]]()
var next = monoAnchor
while true {
    let mono=ProcessInfo.processInfo.systemUptime
    let t=wallAnchor + mono - monoAnchor - epoch
    if t >= duration || shouldStop {break}
    if t>=0, let point=CGEvent(source:nil)?.location {
        rows.append(["t":t,"x":point.x-originX,"y":point.y-originY,"buttons":NSEvent.pressedMouseButtons])
    }
    next += 1.0/60.0
    let delay=next-ProcessInfo.processInfo.systemUptime
    if delay>0 {usleep(useconds_t(delay*1_000_000))}
}
let payload:[String:Any] = ["schema_version":1,"sample_hz":60,"coordinate_space":"capture-region points, top-left origin","recording_launch_epoch":epoch,"video_start_offset_seconds":0,"alignment":"Shared process-launch clock. The screencapture CLI exposes no first-frame timestamp; calibrate video_start_offset_seconds against a visible click if precise alignment is needed.","region_points":region,"samples":rows]
let data=try JSONSerialization.data(withJSONObject:payload,options:[.sortedKeys])
try data.write(to:out,options:.atomic)

