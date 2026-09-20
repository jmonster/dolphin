#!/usr/bin/env python3
# Copyright 2026 Dolphin Emulator Project
# SPDX-License-Identifier: GPL-2.0-or-later
"""Static UI/startup guards; execute test_switch2kit_host.py for host behavior."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class AutomaticConnectionWiringTests(unittest.TestCase):
    def read(self, path):
        return (ROOT / path).read_text()

    def test_startup_is_guarded_once_and_after_window_initialization(self):
        main = self.read("Source/Core/DolphinQt/Main.cpp")
        hook = "QTimer::singleShot(0, &win, [] { ciface::SDL::StartSwitch2KitAutoConnect(); });"
        self.assertEqual(main.count(hook), 1)
        self.assertLess(main.index("MainWindow win{"), main.index(hook))
        self.assertLess(main.index(hook), main.index("retval = app.exec();"))
        guarded = main.rsplit("#ifdef HAVE_SWITCH2KIT", 1)[1].split("#endif", 1)[0]
        self.assertIn(hook, guarded)
        self.assertIn('#ifdef HAVE_SWITCH2KIT\n#include <QTimer>', main)

    def test_checkbox_updates_do_not_start_or_remap_controllers(self):
        pane = self.read("Source/Core/DolphinQt/Config/ControllersPane.cpp")
        self.assertIn("&QCheckBox::toggled", pane)
        self.assertIn("SetSwitch2KitAutoConnect(enabled)", pane)
        self.assertNotIn("StartSwitch2KitAutoConnect", pane)
        update = pane.split("const auto update_status =", 1)[1].split("auto* const timer", 1)[0]
        self.assertIn("QSignalBlocker", update)
        self.assertIn("state.scanning && state.auto_connect", update)
        for action in ("FindSwitch2Controllers", "StopSwitch2Controllers",
                       "SetSwitch2KitAutoConnect", "Mapping::Apply"):
            self.assertNotIn(action, update)

    def test_section_initialization_does_not_change_connection_policy(self):
        pane = self.read("Source/Core/DolphinQt/Config/ControllersPane.cpp")
        initialization = pane.split("connect(find,", 1)[0]
        for action in ("FindSwitch2Controllers(", "StopSwitch2Controllers(",
                       "SetSwitch2KitAutoConnect(", "StartSwitch2KitAutoConnect(", "Mapping::Apply"):
            self.assertNotIn(action, initialization)

    def test_user_actions_refresh_the_displayed_backend_state(self):
        pane = self.read("Source/Core/DolphinQt/Config/ControllersPane.cpp")
        # Reflect explicit stop and saved-setting failures before the next timer tick.
        for action in ("FindSwitch2Controllers()", "StopSwitch2Controllers()",
                       "SetSwitch2KitAutoConnect(enabled)"):
            self.assertIn(f"{action};\n    update_status();", pane)

    def test_polling_and_initialization_never_start_bluetooth(self):
        native = self.read("Source/Core/InputCommon/ControllerInterface/SDL/Switch2Kit.cpp")
        initialize = native.split("void InitializeSwitch2Kit()", 1)[1].split("int Find", 1)[0]
        polling = native.split("void UpdateSwitch2Kit()", 1)[1].split("void Stop", 1)[0]
        for body in (initialize, polling):
            for forbidden in ("s2k_create(", "s2k_start(", "s2k_discover(", "StartSwitch2KitLocked("):
                self.assertNotIn(forbidden, body)
        self.assertNotIn("SaveAutoConnect", polling)
        self.assertNotIn("LoadAutoConnect", polling)
        stop = native.split("void StopSwitch2Controllers()", 1)[1].split("void Shutdown", 1)[0]
        self.assertIn("s_auto_start_pending = false;", stop)
        self.assertIn("s_started = false;", stop)

    def test_normal_test_build_does_not_require_the_backend(self):
        # Evaluate the real parent registration with empty upstream targets;
        # this checks CTest membership, not an emulator build or native behavior.
        def catalogue(source, build, *flags):
            subprocess.run(['cmake', '-S', str(source), '-B', str(build), *flags],
                           check=True, capture_output=True, timeout=15)
            result = subprocess.run(['ctest', '--test-dir', str(build), '--show-only=json-v1'],
                                    check=True, capture_output=True, text=True, timeout=5)
            return {test['name']: test.get('command')
                    for test in json.loads(result.stdout)['tests']}

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected = catalogue(ROOT / 'Source/UnitTests/Switch2Kit', root / 'standalone')
            self.assertTrue(expected, 'The focused test catalogue must not be empty')
            for name in ('Common', 'Core', 'VideoCommon', 'Switch2Kit'):
                (root / name).mkdir()
                (root / name / 'CMakeLists.txt').write_text('')
            (root / 'Switch2Kit/CMakeLists.txt').write_text(
                f'include("{(ROOT / "Source/UnitTests/Switch2Kit/CMakeLists.txt").as_posix()}")\n')
            for name in ('UnitTestsMain.cpp', 'StubHost.cpp'):
                (root / name).write_text('// Configure-only registration fixture.\n')
            (root / 'CMakeLists.txt').write_text(
                'cmake_minimum_required(VERSION 3.25)\n'
                'project(TestRegistration LANGUAGES CXX)\n'
                'set(CMAKE_RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/Binaries")\n'
                'foreach(dependency fmt::fmt gtest::gtest core uicommon)\n'
                '  add_library(${dependency} INTERFACE IMPORTED)\n'
                'endforeach()\n'
                f'include("{(ROOT / "Source/UnitTests/CMakeLists.txt").as_posix()}")\n')
            for enabled in ('OFF', 'ON'):
                with self.subTest(ENABLE_SWITCH2KIT=enabled):
                    registered = catalogue(root, root / 'normal', f'-DENABLE_SWITCH2KIT={enabled}')
                    self.assertIn('tests', registered, 'Keep the upstream test registration')
                    self.assertEqual(expected, {name: command for name, command in registered.items()
                                                if name.startswith('Switch2Kit.')})

    def test_ci_retains_regressions(self):
        # Check CTest's actual commands, not copies of command names in comments.
        with tempfile.TemporaryDirectory() as build:
            subprocess.run(['cmake', '-S', str(ROOT / 'Source/UnitTests/Switch2Kit'),
                            '-B', build], check=True, capture_output=True, timeout=15)
            result = subprocess.run(['ctest', '--test-dir', build, '--show-only=json-v1'],
                                    check=True, capture_output=True, text=True, timeout=5)
        commands = {tuple(test['command'][1:]) for test in json.loads(result.stdout)['tests']}
        for script, flags in (('test_switch2kit.py', ()),
                              ('test_switch2kit_host.py', ('--sanitize',)),
                              ('test_switch2kit_mapping.py', ('--sanitize',)),
                              ('test_switch2kit_autoconnect.py', ())):
            self.assertIn((str(ROOT / 'Tools' / script), *flags), commands)
        workflow = self.read('.github/workflows/native-switch2kit.yml')
        self.assertIn('ctest --test-dir build-switch2kit-tests --output-on-failure --no-tests=error',
                      workflow)


if __name__ == "__main__":
    unittest.main(verbosity=2)
