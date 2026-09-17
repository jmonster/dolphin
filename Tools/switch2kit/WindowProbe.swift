// Copyright 2026 Dolphin Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later
// External CI observer; never linked into Dolphin. No Accessibility or screen capture.
import AppKit
import CoreGraphics
import Foundation

let arguments = CommandLine.arguments
guard arguments.count == 3, let pid = Int32(arguments[1]) else {
    fputs("usage: WindowProbe PID probe|quit\n", stderr)
    exit(2)
}
guard let application = NSRunningApplication(processIdentifier: pid) else { exit(3) }
if arguments[2] == "quit" {
    // Requests normal application termination, not SIGTERM/forceTerminate.
    exit(application.terminate() ? 0 : 4)
}
guard arguments[2] == "probe" else { exit(2) }
let windows = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements],
                                        kCGNullWindowID) as? [[String: Any]] ?? []
let visible = windows.contains { window in
    guard (window[kCGWindowOwnerPID as String] as? NSNumber)?.int32Value == pid,
          (window[kCGWindowLayer as String] as? NSNumber)?.intValue == 0,
          let bounds = window[kCGWindowBounds as String] as? [String: Any],
          let width = bounds["Width"] as? NSNumber,
          let height = bounds["Height"] as? NSNumber else { return false }
    return width.doubleValue >= 100 && height.doubleValue >= 100
}
exit(visible && !application.isTerminated ? 0 : 5)
