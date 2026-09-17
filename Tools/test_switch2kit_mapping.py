#!/usr/bin/env python3
# Copyright 2026 Dolphin Emulator Project
# SPDX-License-Identifier: GPL-2.0-or-later
"""Execute the production mapping helper with test-only UI/config boundaries.

The fake boundaries deterministically exercise dialogs and failure paths. Actual Qt
integration is compiled by the separate full macOS application jobs.
"""
import argparse
import os
from pathlib import Path
import shlex
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sanitize", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    fixture = root / "Tools/switch2kit"
    with tempfile.TemporaryDirectory(prefix="dolphin-switch2kit-mapping-") as temporary:
        work = Path(temporary)
        for name in ("QCoreApplication", "QDir", "QTemporaryFile", "Common/IniFile.h",
                     "Core/HW/GCPad.h", "Core/HW/GCPadEmu.h", "InputCommon/InputConfig.h",
                     "DolphinQt/QtUtils/ModalMessageBox.h"):
            header = work / name
            header.parent.mkdir(parents=True, exist_ok=True)
            header.write_text("// Test boundary supplied by MappingStubs.h\n")
        command = shlex.split(os.environ.get("CXX", "c++")) + [
            "-std=c++20", "-pthread", "-Wall", "-Wextra", "-Werror", "-g",
            "-I", str(work), "-I", str(root / "Source/Core"),
            "-include", str(fixture / "MappingStubs.h"),
            str(root / "Source/Core/DolphinQt/Config/Mapping/Switch2KitMapping.cpp"),
            str(fixture / "MappingTest.cpp"), "-o", str(work / "mapping-test")]
        if args.sanitize:
            command += ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"]
        subprocess.run(command, check=True, timeout=120)
        subprocess.run([str(work / "mapping-test"),
                        str(root / "Data/Sys/Profiles/GCPad"), str(work / "profiles")],
                       check=True, timeout=30)


if __name__ == "__main__":
    main()
