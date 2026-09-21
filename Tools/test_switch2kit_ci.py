#!/usr/bin/env python3
# Copyright 2026 Dolphin Emulator Project
# SPDX-License-Identifier: GPL-2.0-or-later
"""Small regressions for change selection; no bespoke workflow parser or runner."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from switch2kit_ci import TARGETS, changed_paths, select_checks
from test_native_ci_setup import NativeCacheSetupTests, NativeCheckoutTests

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

class NativeBuildSetupTests(unittest.TestCase):
    root = Path(__file__).resolve().parents[1]

    def configure(self, root, event='pull_request', **extra_env):
        env = dict(os.environ, GITHUB_ACTIONS='true', GITHUB_EVENT_NAME=event, **extra_env)
        # Fixtures exercise CMake, not the surrounding native job's cache server.
        for name in ('CMAKE_C_COMPILER_LAUNCHER', 'CMAKE_CXX_COMPILER_LAUNCHER',
                     'S2K_CI_COMPILER_CACHE'):
            env.pop(name, None)
        result = subprocess.run(['cmake', '-S', str(root), '-B', str(root / 'build'),
                                 '-G', 'Ninja', '-DCMAKE_BUILD_TYPE=Release',
                                 f'-DCMAKE_PROJECT_dolphin-emu_INCLUDE={self.root}/Tools/ci-native.cmake'],
                                env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_release_flags_after_upstream_msvc_override(self):
        # This is a CMake scope regression, not a simulated Windows compiler.
        # Load the real upstream flag file and then use the actual project hook.
        for event, expected in [('pull_request', '/Od /Ob0 /DNDEBUG /Z7'),
                                ('workflow_dispatch', '/O2 /DNDEBUG /Z7')]:
            with self.subTest(event=event), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / 'CMakeLists.txt').write_text(f'''
cmake_minimum_required(VERSION 3.25)
set(MSVC TRUE)
set(CMAKE_CXX_COMPILER_ID MSVC)
set(CMAKE_CXX_FLAGS_RELEASE "/Od /DNDEBUG" CACHE STRING "")
include("{self.root}/CMake/FlagsOverride.cmake")
project(dolphin-emu LANGUAGES NONE)
file(WRITE "${{CMAKE_BINARY_DIR}}/flags.txt" "${{CMAKE_CXX_FLAGS_RELEASE}}")
''')
                self.configure(root, event)
                self.assertEqual((root / 'build/flags.txt').read_text(), expected)

    def test_pch_keeps_per_target_flags_and_linux_optimization(self):
        import json
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'Source/PCH').mkdir(parents=True)
            (root / 'Source/PCH/pch.h').write_text('''
#include <vector>
#include <string>
#ifndef FIXTURE_VALUE
#error Per-target definitions must reach the PCH.
#endif
#ifndef NDEBUG
#error Release definitions must be retained.
#endif
''')
            (root / 'QtWidgets').write_text('#pragma once\n')
            (root / 'value.cpp').write_text('int value() { return FIXTURE_VALUE; }\n')
            (root / 'special.cpp').write_text('int special() { return 2; }\n')
            (root / 'plain.c').write_text('int c_value(void) { return 1; }\n')
            (root / 'component').mkdir()
            (root / 'component/CMakeLists.txt').write_text('''
add_library(common ../value.cpp ../plain.c ../special.cpp)
set_source_files_properties(../special.cpp PROPERTIES COMPILE_OPTIONS -std=c++20)
target_compile_definitions(common PRIVATE FIXTURE_VALUE=7)
''')
            (root / 'main.cpp').write_text('''
#include <vector>
extern int value();
int main() { std::vector<int> values{value()}; return values[0] == 7 ? 0 : 1; }
''')
            (root / 'CMakeLists.txt').write_text('''
cmake_minimum_required(VERSION 3.25)
project(dolphin-emu LANGUAGES C CXX)
set(CMAKE_CXX_STANDARD 23)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
set(ENABLE_QT ON)
add_subdirectory(component)
add_executable(dolphin-emu main.cpp)
target_compile_definitions(dolphin-emu PRIVATE FIXTURE_VALUE=9)
target_include_directories(dolphin-emu PRIVATE "${CMAKE_SOURCE_DIR}")
target_link_libraries(dolphin-emu PRIVATE common)
''')
            self.configure(root, CC='clang', CXX='clang++')
            result = subprocess.run(['cmake', '--build', str(root / 'build'), '--parallel', '2'],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            subprocess.run([str(root / 'build/dolphin-emu')], check=True, timeout=2)
            commands = json.loads((root / 'build/compile_commands.json').read_text())
            plain = next(entry['command'] for entry in commands if entry['file'].endswith('plain.c'))
            self.assertNotIn('cmake_pch.hxx', plain)
            special = next(entry['command'] for entry in commands if entry['file'].endswith('special.cpp'))
            self.assertNotIn('cmake_pch.hxx', special)
            self.assertIn('-std=c++20', special)
            cpp = next(entry['command'] for entry in commands if entry['file'].endswith('value.cpp'))
            self.assertIn('cmake_pch.hxx', cpp)
            self.assertIn('-O0' if sys.platform == 'darwin' else '-O1', cpp)
            self.assertIn('-DNDEBUG', cpp)

    def test_ci_build_acceleration_changes_select_all_native_platforms(self):
        self.assertEqual(select_checks(['Tools/ci-native.cmake']), NATIVE)


if __name__ == '__main__':
    unittest.main(verbosity=2)
