#!/usr/bin/env python3
# Copyright 2026 Dolphin Emulator Project
# SPDX-License-Identifier: GPL-2.0-or-later
"""Static integration regressions; not a Swift, Bluetooth, or gameplay test."""
import configparser
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Switch2KitIntegrationTests(unittest.TestCase):
    def read(self, name):
        return (ROOT / name).read_text()

    def test_gamecube_face_buttons(self):
        profile = self.profile()
        self.assertEqual([profile[f"Buttons/{button}"] for button in "ABXY"],
                         ["`Button S`", "`Button W`", "`Button E`", "`Button N`"])
        self.assertEqual(profile["Buttons/Z"], "`Shoulder R`")
        self.assertEqual(profile["Buttons/Start"], "`Start`")

    def profile(self, name="Switch2Kit GameCube"):
        parser = configparser.ConfigParser()
        parser.optionxform = str
        parser.read(ROOT / "Data/Sys/Profiles/GCPad" / (name + ".ini"))
        return parser["Profile"]

    def test_independent_trigger_travel_and_click(self):
        profile = self.profile()
        for side, button in (("L", 3), ("R", 4)):
            self.assertEqual(profile[f"Triggers/{side}"], f"`Misc {button}`")
            self.assertEqual(profile[f"Triggers/{side}-Analog"], f"`Trigger {side}`")
        self.assertEqual(profile["Rumble/Motor"], "`Motor`")
        self.assertNotIn("Device", profile)  # Never bind another person's SDL ordinal.

    def test_axis_and_dpad_names(self):
        profile = self.profile()
        for group, stick in (("Main Stick", "Left"), ("C-Stick", "Right")):
            for direction, axis in (("Up", "Y+"), ("Down", "Y-"),
                                    ("Left", "X-"), ("Right", "X+")):
                self.assertEqual(profile[f"{group}/{direction}"], f"`{stick} {axis}`")
        for direction, button in (("Up", "N"), ("Down", "S"), ("Left", "W"), ("Right", "E")):
            self.assertEqual(profile[f"D-Pad/{direction}"], f"`Pad {button}`")

    def test_pro_preset(self):
        pro = self.profile("Switch2Kit Pro Controller 2")
        self.assertEqual([pro[f"Buttons/{button}"] for button in "ABXY"],
                         ["`Button E`", "`Button S`", "`Button N`", "`Button W`"])
        gc = self.profile()
        for key in gc:
            if key not in [f"Buttons/{b}" for b in "ABXY"]:
                self.assertEqual(pro[key], gc[key])
        self.assertNotIn("Device", pro)

    def test_mapping_requires_user_action_and_is_guarded(self):
        widget = self.read("Source/Core/DolphinQt/Config/GamecubeControllersWidget.cpp")
        refresh = widget.split("void GamecubeControllersWidget::RefreshSwitch2KitDevices()", 1)[1]
        refresh = refresh.split("void GamecubeControllersWidget::OnSwitch2KitDeviceSelected", 1)[0]
        self.assertNotIn("Switch2KitMapping::Apply", refresh)
        self.assertIn("QSignalBlocker", refresh)
        self.assertIn("&QComboBox::activated", widget)
        self.assertIn("already_assigned", widget)
        cmake = self.read("Source/Core/DolphinQt/CMakeLists.txt")
        guarded = cmake.split("if(ENABLE_SWITCH2KIT)", 1)[1].split("endif()", 1)[0]
        self.assertIn("Config/Mapping/Switch2KitMapping.cpp", guarded)

    def test_disabled_build_has_no_dependency(self):
        # Real CMake execution: with OFF, the module must not inspect Swift/SDK/SDL.
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "off.cmake"
            script.write_text('set(ENABLE_SWITCH2KIT OFF CACHE BOOL "")\n'
                              f'include("{ROOT / "CMake/DolphinSwitch2Kit.cmake"}")\n')
            subprocess.run(["cmake", "-P", str(script)], check=True, capture_output=True)

    def test_platform_and_backend_configuration(self):
        # Exercise the actual CMake guard. The probe dependency records whether
        # SDK evaluation is reached; no message wording or documentation is tested.
        cases = (("Linux", False, False, True, True, "11.0", False, True),
                 ("Windows", False, True, True, True, "11.0", False, True),
                 ("Darwin", True, False, True, True, "15.0", False, True),
                 ("FreeBSD", False, False, True, True, "15.0", False, False),
                 ("Linux", False, False, False, True, "15.0", False, False),
                 ("Linux", False, False, True, False, "15.0", False, False),
                 ("Darwin", True, False, True, True, "11.0", False, False),
                 ("Linux", False, False, True, True, "15.0", True, False))
        for system, apple, windows, sdl, qt, target, android, accepted in cases:
            with self.subTest(system=system, sdl=sdl, qt=qt, target=target, android=android):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    sdk = root / "Externals/Switch2Kit/Integrations/SDL3"
                    sdk.mkdir(parents=True)
                    (sdk / "probe.cpp").write_text("int probe;\n")
                    marker = root / "sdk-entered"
                    (sdk / "CMakeLists.txt").write_text(
                        'add_library(inputcommon STATIC probe.cpp)\n'
                        'add_library(Switch2Kit::SDL3 INTERFACE IMPORTED GLOBAL)\n'
                        f'file(WRITE "{marker.as_posix()}" "entered")\n')
                    source = root / "ControllerInterface/SDL"
                    source.mkdir(parents=True)
                    (source / "Switch2Kit.cpp").write_text("int host;\n")
                    (source / "Switch2Kit.h").write_text("#pragma once\n")
                    values = {"ENABLE_SWITCH2KIT": "ON", "APPLE": int(apple), "WIN32": int(windows),
                              "CMAKE_SYSTEM_NAME": system, "ANDROID": int(android),
                              "ENABLE_SDL": int(sdl), "ENABLE_QT": int(qt),
                              "CMAKE_OSX_DEPLOYMENT_TARGET": target}
                    (root / "CMakeLists.txt").write_text(
                        "cmake_minimum_required(VERSION 3.25)\nproject(Guard LANGUAGES CXX)\n" +
                        "".join(f"set({key} {value})\n" for key, value in values.items()) +
                        f'include("{(ROOT / "CMake/DolphinSwitch2Kit.cmake").as_posix()}")\n')
                    result = subprocess.run(["cmake", "-S", str(root), "-B", str(root / "build")],
                                            capture_output=True, text=True)
                    self.assertEqual(marker.exists(), accepted, result.stdout + result.stderr)
                    self.assertEqual(result.returncode == 0, accepted, result.stdout + result.stderr)

    def test_windows_ci_uses_swift_compatible_runner(self):
        workflow = self.read(".github/workflows/switch2kit-windows.yml")
        # Swift 6.2.1 uses Clang 19; VS 2026's STL requires Clang 20.
        # Keep these pins paired until a newer toolchain is qualified together.
        self.assertIn("    runs-on: windows-2022\n", workflow)
        self.assertIn("swift-version: swift-6.2.1-release", workflow)
        self.assertIn("swift-build: 6.2.1-RELEASE", workflow)

    def test_windows_build_selects_only_visual_studio_2022(self):
        script = self.read("Tools/build-switch2kit-windows.ps1")
        selection = next(line for line in script.splitlines()
                         if line.startswith("$vs = & $vswhere "))
        self.assertIn("-version '[17.0,18.0)'", selection)
        self.assertIn("-requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64", selection)
        self.assertIn("if ($LASTEXITCODE -ne 0 -or -not $vs) { throw", script)
        self.assertLess(script.index(selection), script.index("VsDevCmd.bat"))

    def test_windows_fix_keeps_native_build_and_launch_required(self):
        script = self.read("Tools/build-switch2kit-windows.ps1")
        workflow = self.read(".github/workflows/switch2kit-windows.yml")
        self.assertIn("-DENABLE_SWITCH2KIT=ON", script)
        self.assertIn("--target dolphin-emu", script)
        self.assertIn("Switch2KitC.dll", script)
        self.assertIn("./Tools/build-switch2kit-windows.ps1", workflow)
        self.assertIn("./Tools/test_switch2kit_windows_launch.ps1", workflow)
        self.assertNotIn("continue-on-error", workflow)
        self.assertNotIn("_ALLOW_COMPILER_AND_STL_VERSION_MISMATCH", script + workflow)

    def test_ordered_lifecycle_and_bundle(self):
        backend = self.read("Source/Core/InputCommon/ControllerInterface/SDL/SDL.cpp")
        self.assertLess(backend.index("ShutdownSwitch2Kit();"), backend.index("SDL_Quit();"))
        self.assertLess(backend.index("UpdateSwitch2Kit();"), backend.index("SDL_UpdateGamepads();"))
        native = self.read("Source/Core/InputCommon/ControllerInterface/SDL/Switch2Kit.cpp")
        shutdown = native.split("void ShutdownSwitch2Kit()", 1)[1].split("Switch2KitStatus", 1)[0]
        self.assertLess(shutdown.index("s_adapter.reset();"), shutdown.index("s2k_destroy("))
        self.assertIn("s2k_read(s_context, nullptr, 0,", native)
        qt = self.read("Source/Core/DolphinQt/CMakeLists.txt")
        self.assertLess(qt.index("switch2kit_embed(dolphin-emu)"),
                        qt.index("dolphin_postprocess_bundle(dolphin-emu)"))
        self.assertLess(qt.index("switch2kit_embed(dolphin-emu)"), qt.index("Tools/mac-codesign.sh"))
        self.assertIn("${SWITCH2KIT_BLUETOOTH_USAGE}", self.read("Source/Core/DolphinQt/Info.plist.in"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
