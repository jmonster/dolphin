// Copyright 2026 Dolphin Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later
// External acceptance-test observer. Never linked into Dolphin.
import AppKit
import CoreGraphics
import CoreServices
import Foundation

let args = CommandLine.arguments
guard args.count == 3 else { exit(2) }
if args[1] == "register" {
    let status = LSRegisterURL(URL(fileURLWithPath: args[2]) as CFURL, true)
    print(status)
    exit(status == 0 ? 0 : 1)
}
if args[1] == "find" || args[1] == "cleanup" {
    let target = URL(fileURLWithPath: args[2]).resolvingSymlinksInPath()
    let applications = NSWorkspace.shared.runningApplications.filter {
        $0.bundleURL?.resolvingSymlinksInPath() == target && !$0.isTerminated
    }
    if args[1] == "cleanup" {
        for application in applications { _ = application.forceTerminate() }
        exit(0)
    }
    if applications.isEmpty { exit(3) }
    guard applications.count == 1, let application = applications.first else { exit(5) }
    print(application.processIdentifier)
    exit(0)
}
guard let pid = Int32(args[2]),
      let application = NSRunningApplication(processIdentifier: pid) else { exit(3) }
if args[1] == "quit" { exit(application.terminate() ? 0 : 4) }
guard args[1] == "probe" else { exit(2) }
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
