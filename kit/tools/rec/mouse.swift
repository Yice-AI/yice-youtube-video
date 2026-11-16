// mouse move X Y [ms]   – smooth eased move (global logical points)
// mouse click X Y [ms]  – move then left click
// mouse pos             – print current position
import Foundation
import CoreGraphics

func cur() -> CGPoint { CGEvent(source: nil)?.location ?? .zero }
func post(_ t: CGEventType, _ p: CGPoint) {
    CGEvent(mouseEventSource: nil, mouseType: t, mouseCursorPosition: p, mouseButton: .left)?.post(tap: .cghidEventTap)
}
func move(to p: CGPoint, ms: Double) {
    let a = cur(); let steps = max(1, Int(ms / 1000 * 120))
    for i in 1...steps {
        let t = Double(i) / Double(steps)
        let e = t < 0.5 ? 4*t*t*t : 1 - pow(-2*t + 2, 3) / 2   // easeInOutCubic
        post(.mouseMoved, CGPoint(x: a.x + (p.x - a.x) * e, y: a.y + (p.y - a.y) * e))
        usleep(useconds_t(1_000_000 / 120))
    }
}
let args = CommandLine.arguments
guard args.count >= 2 else { print("usage: mouse move|click X Y [ms] | pos"); exit(1) }
switch args[1] {
case "pos": let p = cur(); print(Int(p.x), Int(p.y))
case "move", "click":
    let p = CGPoint(x: Double(args[2])!, y: Double(args[3])!)
    move(to: p, ms: args.count > 4 ? Double(args[4])! : 600)
    if args[1] == "click" {
        usleep(120_000); post(.leftMouseDown, p); usleep(90_000); post(.leftMouseUp, p)
    }
default: exit(1)
}
