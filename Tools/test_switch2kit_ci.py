#!/usr/bin/env python3
# Copyright 2026 Dolphin Emulator Project
# SPDX-License-Identifier: GPL-2.0-or-later
"""Small regressions for change selection; no bespoke workflow parser or runner."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from switch2kit_ci import TARGETS, changed_paths, select_checks

NATIVE = {'macos', 'linux', 'windows'}


class ChangeSelectionTests(unittest.TestCase):
    def test_documentation_does_not_build_applications(self):
        self.assertEqual(select_checks(['Readme.md', 'Docs/Switch2Kit.md', 'AGENTS.md']), set())

    def test_every_shared_production_input_rebuilds_native_applications(self):
        for path in ('Source/Core/DolphinQt/Config/ControllersPane.cpp',
                     'Source/Core/Common/Config/Config.h', 'CMakeLists.txt',
                     'CMake/DolphinSwitch2Kit.cmake', 'Externals/fmt/fmt',
                     'Data/Sys/Profiles/GCPad/Switch2Kit GameCube.ini', 'new-build-input'):
            with self.subTest(path=path):
                self.assertEqual(select_checks([path]), NATIVE)

    def test_sdk_and_sdl_pins_restore_real_sdk_and_all_native_checks(self):
        for path in ('Externals/Switch2Kit', 'Externals/SDL/SDL', '.gitmodules',
                     'Externals/Switch2Kit/Package.swift'):
            self.assertEqual(select_checks([path]), TARGETS)

    def test_platform_specific_tools_do_not_rebuild_unaffected_platforms(self):
        for target in NATIVE:
            self.assertEqual(select_checks([f'.github/workflows/switch2kit-{target}.yml']), {target})
        self.assertEqual(select_checks(['Tools/build-switch2kit-linux.sh']), {'linux'})
        self.assertEqual(select_checks(['Tools/test_switch2kit_bundle.py']), {'macos'})
        self.assertEqual(select_checks(['Tools/test_switch2kit_windows_launch.ps1']), {'windows'})

    def test_orchestration_changes_validate_the_entire_graph(self):
        for path in ('Tools/switch2kit_ci.py', 'Tools/test_switch2kit_ci.py',
                     '.github/workflows/native-switch2kit.yml'):
            self.assertEqual(select_checks([path]), TARGETS)

    def test_fast_fixture_changes_stay_in_the_always_run_ctest_suite(self):
        self.assertEqual(select_checks(['Tools/test_switch2kit_host.py',
                                        'Tools/switch2kit/HostTest.cpp',
                                        'Source/UnitTests/Switch2Kit/CMakeLists.txt']), set())
        self.assertEqual(select_checks(['Source/UnitTests/CMakeLists.txt']), {'linux'})

    def test_multiple_changes_union_the_required_checks(self):
        self.assertEqual(select_checks(['Docs/Switch2Kit.md',
                                        'Tools/build-switch2kit-linux.sh',
                                        'Tools/test_switch2kit_bundle.py']), {'linux', 'macos'})

    def test_git_failure_cannot_be_reported_as_no_changes(self):
        with patch('switch2kit_ci.subprocess.run', side_effect=subprocess.CalledProcessError(1, 'git')):
            with self.assertRaises(subprocess.CalledProcessError):
                changed_paths('missing-base')

    def test_deleted_renamed_and_whitespace_paths_are_not_lost(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def git(*args):
                return subprocess.run(['git', '-C', str(root), *args], check=True,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            git('init', '-q')
            git('config', 'user.name', 'Test')
            git('config', 'user.email', 'test@example.invalid')
            source = root / 'Source/Core/file with space.cpp'
            source.parent.mkdir(parents=True)
            source.write_text('int value;\n')
            git('add', '.')
            git('commit', '-qm', 'base')
            (root / 'Docs').mkdir()
            source.rename(root / 'Docs/moved.cpp')
            git('add', '-A')
            git('commit', '-qm', 'rename')
            previous = os.getcwd()
            try:
                os.chdir(root)
                paths = changed_paths('HEAD~1')
            finally:
                os.chdir(previous)
            self.assertIn('Source/Core/file with space.cpp', paths)
            self.assertIn('Docs/moved.cpp', paths)
            self.assertEqual(select_checks(paths), NATIVE)


if __name__ == '__main__':
    unittest.main(verbosity=2)
