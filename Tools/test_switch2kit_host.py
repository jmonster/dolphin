#!/usr/bin/env python3
# Copyright 2026 Dolphin Emulator Project
# SPDX-License-Identifier: GPL-2.0-or-later
"""Execute the real host wrapper against test-only SDL/SDK/config boundaries."""
import argparse
import os
from pathlib import Path
import shlex
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sanitize", action="store_true", help="Enable address/undefined sanitizers")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    fixture = root / "Tools/switch2kit"
    with tempfile.TemporaryDirectory(prefix="dolphin-switch2kit-host-") as temporary:
        work = Path(temporary)
        # Only boundary headers are replaced. The real production .cpp/.h are compiled.
        for name in ("SDL3/SDL.h", "Switch2KitSDL3.hpp", "Common/FileUtil.h", "Common/IniFile.h"):
            header = work / name
            header.parent.mkdir(parents=True, exist_ok=True)
            header.write_text("// Test boundary supplied by HostStubs.h\n")
        command = shlex.split(os.environ.get("CXX", "c++")) + [
            "-std=c++20", "-pthread", "-Wall", "-Wextra", "-Werror", "-g",
            "-I", str(work), "-I", str(root / "Source/Core"),
            "-include", str(fixture / "HostStubs.h"),
            str(root / "Source/Core/InputCommon/ControllerInterface/SDL/Switch2Kit.cpp"),
            str(fixture / "HostTest.cpp"), "-o", str(work / "host-test")]
        if args.sanitize:
            command += ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"]
        subprocess.run(command, check=True, timeout=120)
        subprocess.run([str(work / "host-test")], check=True, timeout=30)


if __name__ == "__main__":
    main()
