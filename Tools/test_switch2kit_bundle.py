#!/usr/bin/env python3
# Copyright 2026 Dolphin Emulator Project
# SPDX-License-Identifier: GPL-2.0-or-later
"""Check the exact app ZIP, then launch/quit/relaunch it with build roots denied.

This is a no-controller macOS GUI smoke test, not gameplay or clean-Mac qualification.
Only a temporary test user directory has analytics opted out to avoid a modal prompt.
No signing, Gatekeeper, Bluetooth, Accessibility, or production preferences are changed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import subprocess
import sys
import tempfile
import time


MACHO = {b"\xfe\xed\xfa\xce", b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xcf",
         b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca",
         b"\xca\xfe\xba\xbf", b"\xbf\xba\xfe\xca"}


def run(command, **kwargs):
    return subprocess.run([str(value) for value in command], check=True, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120, **kwargs).stdout


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def inspect(app, architecture):
    with (app / "Contents/Info.plist").open("rb") as stream:
        plist = plistlib.load(stream)
    executable = app / "Contents/MacOS" / plist["CFBundleExecutable"]
    sdk = app / "Contents/Frameworks/libSwitch2KitC.dylib"
    assert executable.is_file() and os.access(executable, os.X_OK), "Missing executable"
    assert sdk.is_file(), "Missing embedded Switch2Kit library"
    assert plist.get("NSBluetoothAlwaysUsageDescription", "").strip(), "Missing Bluetooth description"
    assert (app / "Contents/Resources/Sys/Profiles/GCPad/Switch2Kit GameCube.ini").is_file()
    run(["/usr/bin/codesign", "--verify", "--deep", "--strict", app])
    binaries = []
    for path in app.rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        with path.open("rb") as stream:
            if stream.read(4) not in MACHO:
                continue
        run(["/usr/bin/lipo", path, "-verify_arch", architecture])
        libraries = run(["/usr/bin/otool", "-L", path])
        # Absolute references may name Apple's system libraries, never Homebrew,
        # Xcode, the checkout, or other build-machine locations. The sandboxed
        # launch below additionally resolves dyld's actual runtime/plugin closure.
        for line in libraries.splitlines()[1:]:
            dependency = line.strip().split(" (", 1)[0]
            if dependency.startswith("/"):
                assert dependency.startswith(("/usr/lib/", "/System/Library/")), dependency
        loads = run(["/usr/bin/otool", "-l", path])
        for rpath in re.findall(r"cmd LC_RPATH\s+cmdsize \d+\s+path (.+?) \(offset", loads):
            if rpath.startswith("/"):
                assert rpath.startswith(("/usr/lib/", "/System/Library/")), rpath
        binaries.append(str(path.relative_to(app)))
    assert binaries, "No Mach-O images inspected"
    return executable, {"executable_sha256": digest(executable), "sdk_sha256": digest(sdk),
                        "minimum_macos": plist.get("LSMinimumSystemVersion"),
                        "mach_o_images": binaries, "signature_verified": True}


def smoke(executable, user, probe, policy, log, phase):
    result = {"phase": phase, "window_observed": False, "normal_exit": False,
              "forced_cleanup": False, "status": "failed"}
    with log.open("w") as output:
        environment = os.environ.copy()
        for key in list(environment):
            if key.startswith(("DYLD_", "QT_", "QML_")):
                del environment[key]
        process = subprocess.Popen(["/usr/bin/sandbox-exec", "-p", policy,
                                    str(executable), "--user", str(user)],
                                   stdout=output, stderr=subprocess.STDOUT, env=environment)
        try:
            deadline = time.monotonic() + 40
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError(f"Application exited during launch: {process.returncode}")
                observation = subprocess.run([str(probe), str(process.pid), "probe"], timeout=10)
                if observation.returncode == 0:
                    result["window_observed"] = True
                    break
                time.sleep(0.5)
            if not result["window_observed"]:
                raise RuntimeError("No visible application window")
            time.sleep(5)
            if process.poll() is not None:
                raise RuntimeError("Application exited after showing its window")
            run([probe, process.pid, "probe"])
            result["stable_seconds"] = 5
            run([probe, process.pid, "quit"])
            result["quit_requested"] = True
            code = process.wait(timeout=20)
            if code != 0:
                raise RuntimeError(f"Abnormal application exit: {code}")
            result["normal_exit"] = True
            result["status"] = "passed"
        except (RuntimeError, subprocess.SubprocessError) as error:
            result["reason"] = str(error)
            if process.poll() is None:
                subprocess.run(["/usr/bin/sample", str(process.pid), "2", "-file", str(log) + ".sample"],
                               stdout=output, stderr=subprocess.STDOUT, timeout=15)
        finally:
            if process.poll() is None:
                process.kill()  # Failure cleanup only; never counts as a successful quit.
                process.wait(timeout=10)
                result["forced_cleanup"] = True
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--architecture", required=True, choices=("arm64", "x86_64"))
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    report = {"status": "failed", "architecture": args.architecture, "runs": [],
              "scope": "exact ZIP inspection and isolated no-controller GUI launch/quit/relaunch",
              "physical_controller_tested": False, "stock_clean_mac_tested": False}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    try:
        if sys.platform != "darwin":
            raise RuntimeError("This test requires an actual macOS GUI session")
        root = Path(__file__).resolve().parents[1]
        report["archive_sha256"] = digest(args.archive)
        report["source_revision"] = run(["git", "-C", root, "rev-parse", "HEAD"]).strip()
        report["macos"] = run(["/usr/bin/sw_vers", "-productVersion"]).strip()
        # Outside the checkout and with spaces: detects build-tree paths and quoting errors.
        with tempfile.TemporaryDirectory(prefix="Dolphin Switch2Kit ", dir="/private/tmp") as temporary:
            work = Path(temporary)
            run(["/usr/bin/ditto", "-x", "-k", args.archive.resolve(), work])
            apps = list(work.glob("*.app"))
            assert len(apps) == 1, "Expected exactly one top-level app in the ZIP"
            executable, inspection = inspect(apps[0], args.architecture)
            report.update(inspection)
            probe = work / "WindowProbe"
            run(["/usr/bin/xcrun", "swiftc", root / "Tools/switch2kit/WindowProbe.swift", "-o", probe])
            blocked = ["/Applications", "/Library/Developer", "/opt/homebrew", "/usr/local", str(root)]
            policy = '(version 1) (allow default) (deny network*) (deny file-read* ' + " ".join(
                f"(subpath {json.dumps(path)})" for path in blocked) + ")"
            # Verify the sandbox actually refuses reads, rather than merely assuming it.
            refusal = subprocess.run(["/usr/bin/sandbox-exec", "-p", policy, "/bin/cat", str(__file__)],
                                     capture_output=True, timeout=10)
            assert refusal.returncode != 0, "Sandbox failed to deny checkout reads"
            report["blocked_roots_checked"] = blocked
            user = work / "Test User"
            (user / "Config").mkdir(parents=True)
            (user / "Config/Dolphin.ini").write_text(
                "[Analytics]\nEnabled = False\nPermissionAsked = True\n[AutoUpdate]\nUpdateTrack =\n")
            for phase in ("first-launch", "relaunch"):
                log = args.report.parent / f"switch2kit-{phase}.log"
                result = smoke(executable, user, probe, policy, log, phase)
                report["runs"].append(result)
                if result["status"] != "passed":
                    raise RuntimeError(result.get("reason", "GUI smoke test failed"))
            report["status"] = "passed"
    except (AssertionError, OSError, RuntimeError, subprocess.SubprocessError) as error:
        report["reason"] = str(error)
    finally:
        args.report.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
