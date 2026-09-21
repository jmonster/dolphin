# Copyright 2026 Dolphin Emulator Project
# SPDX-License-Identifier: GPL-2.0-or-later
"""Setup regressions loaded by the existing Switch2Kit CTest CI test group."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from checkout_native import checkout, git, native_modules


class NativeCheckoutTests(unittest.TestCase):
    def test_only_foreign_binary_and_android_modules_are_excluded(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = ('Externals/Qt', 'Externals/FFmpeg-bin', 'Externals/libadrenotools',
                     'Externals/Switch2Kit', 'Externals/SDL/SDL', 'new-dependency')
            (root / '.gitmodules').write_text(''.join(
                f'[submodule "{path}"]\npath = {path}\nurl = example\n' for path in paths))
            for platform in ('linux', 'darwin', 'win32'):
                selected = {path for _, path, active in native_modules(root, platform) if active}
                self.assertEqual(selected, set(paths) - {'Externals/libadrenotools'} -
                                 (set() if platform == 'win32' else {'Externals/Qt', 'Externals/FFmpeg-bin'}))
            with self.assertRaises(ValueError):
                native_modules(root, 'unsupported')
            (root / '.gitmodules').write_text('[submodule "bad"]\npath = ../escape\n')
            with self.assertRaises(ValueError):
                native_modules(root, 'linux')

    def test_parallel_updates_use_committed_pins_not_remote_heads(self):
        # Real local Git repositories: no network or timing-dependent sleeps.
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
                'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'protocol.file.allow',
                'GIT_CONFIG_VALUE_0': 'always'}):
            root = Path(directory) / 'parent'
            origin = Path(directory) / 'dependency'
            for repo in (root, origin):
                repo.mkdir()
                git(repo, 'init', '-q')
                git(repo, 'config', 'user.name', 'Test')
                git(repo, 'config', 'user.email', 'test@example.invalid')
            (origin / 'value').write_text('pinned\n')
            git(origin, 'add', '.')
            git(origin, 'commit', '-qm', 'pin')
            pin = git(origin, 'rev-parse', 'HEAD').strip()
            (origin / 'value').write_text('not the pinned version\n')
            git(origin, 'commit', '-qam', 'remote head')
            paths = ('Externals/first', 'Externals/second with space')
            (root / '.gitmodules').write_text(''.join(
                f'[submodule "{path}"]\npath = {path}\nurl = {origin.as_uri()}\n' for path in paths))
            git(root, 'add', '.gitmodules')
            for path in paths:
                git(root, 'update-index', '--add', '--cacheinfo', f'160000,{pin},{path}')
            git(root, 'commit', '-qm', 'parent')
            checkout(root, 'linux')
            for path in paths:
                self.assertEqual(git(root / path, 'rev-parse', 'HEAD').strip(), pin)
                self.assertEqual((root / path / 'value').read_text(), 'pinned\n')
            # No matching committed gitlink must be a failure, not an empty pass.
            (root / '.gitmodules').write_text('[submodule "missing"]\npath = missing\nurl = bad\n')
            with self.assertRaises((ValueError, subprocess.CalledProcessError)):
                checkout(root, 'linux')


class NativeCacheSetupTests(unittest.TestCase):
    def test_child_project_cannot_undo_msvc_smoke_options(self):
        repository = Path(__file__).resolve().parents[1]
        for event in ('pull_request', 'workflow_dispatch'):
            with self.subTest(event=event), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / 'child').mkdir()
                (root / 'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.25)\n'
                    'set(MSVC TRUE)\nset(CMAKE_CXX_COMPILER_ID MSVC)\n'
                    'project(dolphin-emu LANGUAGES NONE)\nadd_subdirectory(child)\n')
                (root / 'child/CMakeLists.txt').write_text(
                    'project(dependency LANGUAGES NONE)\n'
                    f'include("{repository}/CMake/FlagsOverride.cmake")\n'
                    'get_directory_property(options COMPILE_OPTIONS)\n'
                    'file(WRITE "${CMAKE_BINARY_DIR}/child.txt" "${CMAKE_CXX_FLAGS_RELEASE}\\n${options}")\n')
                result = subprocess.run(['cmake', '-S', str(root), '-B', str(root / 'build'),
                    f'-DCMAKE_PROJECT_dolphin-emu_INCLUDE={repository}/Tools/ci-native.cmake'],
                    env=dict(os.environ, GITHUB_ACTIONS='true', GITHUB_EVENT_NAME=event),
                    capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                flags, options = (root / 'build/child.txt').read_text().split('\n', 1)
                self.assertEqual(flags, '/O2 /DNDEBUG /Z7')
                if event == 'pull_request':
                    self.assertIn(':/Od>', options)
                    self.assertIn(':/Ob0>', options)
                else:
                    self.assertEqual(options, '')

    def test_cache_is_not_used_by_probes_or_pch_consumers(self):
        hook = Path(__file__).resolve().parent / 'ci-native.cmake'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'Source/PCH').mkdir(parents=True)
            (root / 'Source/PCH/pch.h').write_text('#include <vector>\n')
            (root / 'value.cpp').write_text('int value() { return 0; }\n')
            (root / 'plain.c').write_text('int plain(void) { return 0; }\n')
            (root / 'CMakeLists.txt').write_text('''
cmake_minimum_required(VERSION 3.25)
project(dolphin-emu LANGUAGES C CXX)
if(CMAKE_C_COMPILER_LAUNCHER OR CMAKE_CXX_COMPILER_LAUNCHER)
  message(FATAL_ERROR "Configure probes must not use the cache wrapper")
endif()
include(CheckCSourceCompiles)
check_c_source_compiles("int main(void) { return 0; }" HAVE_WORKING_C)
if(NOT HAVE_WORKING_C)
  message(FATAL_ERROR "The real compiler probe must still succeed")
endif()
add_library(common OBJECT value.cpp)
add_library(ordinary OBJECT plain.c)
file(GENERATE OUTPUT "${CMAKE_BINARY_DIR}/launchers.json" CONTENT
  "[\\"$<TARGET_PROPERTY:common,CXX_COMPILER_LAUNCHER>\\",\\"$<TARGET_PROPERTY:ordinary,C_COMPILER_LAUNCHER>\\"]")
''')
            env = dict(os.environ, GITHUB_ACTIONS='true', GITHUB_EVENT_NAME='pull_request',
                       CC='clang', CXX='clang++')
            command = ['cmake', '-S', str(root), '-B', str(root / 'build'), '-G', 'Ninja',
                       f'-DCMAKE_PROJECT_dolphin-emu_INCLUDE={hook}',
                       '-DCMAKE_C_COMPILER_LAUNCHER=cmake;-E;env',
                       '-DCMAKE_CXX_COMPILER_LAUNCHER=cmake;-E;env']
            result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads((root / 'build/launchers.json').read_text()), ['', 'cmake;-E;env'])
            result = subprocess.run(['cmake', '--build', str(root / 'build'), '--parallel', '2'],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
