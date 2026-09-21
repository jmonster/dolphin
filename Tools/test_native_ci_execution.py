#!/usr/bin/env python3
# Copyright 2026 Dolphin Emulator Project
# SPDX-License-Identifier: GPL-2.0-or-later
"""Execute the native-CI configure/cache/PCH boundaries, without Dolphin or Swift."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest

import checkout_native

PRESET = Path(__file__).with_name('ci-native.cmake').resolve()


def run(*args, cwd, env=None, ok=True):
    result = subprocess.run([str(arg) for arg in args], cwd=cwd, env=env,
                            text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=15)
    if ok and result.returncode:
        raise AssertionError(f'{args}:\n{result.stdout}')
    return result


def write(root, name, content):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content), encoding='utf-8')
    return path


class NativeExecutionTests(unittest.TestCase):
    def test_real_probes_pch_generated_sources_and_test_execution(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            wrapper = write(root, 'cache.py', '''\
                import json, os, sys
                with open(os.environ['CACHE_CALLS'], 'a') as out:
                    out.write(json.dumps([os.getcwd(), *sys.argv[1:]]) + '\\n')
                os.execv(sys.argv[1], sys.argv[1:])
            ''')
            launcher = f'{sys.executable};{wrapper}'
            calls = root / 'cache-calls.jsonl'
            env = dict(os.environ, GITHUB_ACTIONS='true', CACHE_CALLS=str(calls),
                       S2K_CI_COMPILER_CACHE=launcher,
                       CMAKE_C_COMPILER_LAUNCHER=launcher,
                       CMAKE_CXX_COMPILER_LAUNCHER=launcher)
            # Use the selected host compiler, not a fake successful compiler.
            cc = os.environ.get('CC') or shutil.which('cc')
            cxx = os.environ.get('CXX') or shutil.which('c++')
            self.assertTrue(cc and cxx, 'A real C and C++ compiler is required')
            write(root, 'Source/PCH/pch.h', '#pragma once\n#include <vector>\n')
            write(root, 'common.cpp', 'int common_value() { return 10; }\n')
            write(root, 'Source/UnitTests/CMakeLists.txt', '''\
                add_library(upstream_cases OBJECT case.cpp)
                add_executable(tests EXCLUDE_FROM_ALL main.cpp)
                target_link_libraries(tests PRIVATE upstream_cases)
                add_custom_target(unittests DEPENDS tests)
            ''')
            write(root, 'Source/UnitTests/case.cpp', 'int tested_value() { return 42; }\n')
            write(root, 'Source/UnitTests/main.cpp',
                  'int tested_value(); int main() { return tested_value() == 42 ? 0 : 1; }\n')
            write(root, 'special.cpp', '''\
                #ifndef PER_SOURCE
                #error per-source options lost
                #endif
                int special_value() { return 11; }
            ''')
            write(root, 'generated.cpp.in', 'int generated_value() { return 12; }\n')
            write(root, 'plain.c', '''\
                #ifndef NDEBUG
                #error Release defines lost
                #endif
                #if defined(__linux__) && !defined(__OPTIMIZE__)
                #error Linux must remain optimized
                #endif
                int plain_value(void) { return 9; }
            ''')
            write(root, 'external.cpp', 'int external_value() { return 0; }\n')
            write(root, 'MachineIndependent/pch.h', '#pragma once\n#include <sstream>\n')
            write(root, 'main.cpp', '''\
                #include <fstream>
                extern "C" int plain_value(void);
                int common_value(); int special_value(); int generated_value();
                int external_value();
                int main() {
                  std::ofstream("executed.txt", std::ios::app) << "executed\\n";
                  return plain_value() + common_value() + special_value() +
                         generated_value() + external_value() == 42 ? 0 : 1;
                }
            ''')
            # A separate CMake process models SDK and try_compile environments.
            write(root, 'probe/CMakeLists.txt', '''\
                cmake_minimum_required(VERSION 3.25)
                project(NestedProbe LANGUAGES C CXX)
                include(CheckCSourceCompiles)
                include(CheckCXXSourceCompiles)
                check_c_source_compiles("int main(void) { return 0; }" REAL_C)
                check_cxx_source_compiles("int main() { return 0; }" REAL_CXX)
                check_c_source_compiles("extern int missing_symbol(void); int main(void) { return missing_symbol(); }" BAD_LINK)
                if(NOT REAL_C OR NOT REAL_CXX OR BAD_LINK)
                  message(FATAL_ERROR "Real configure/link probes were bypassed")
                endif()
            ''')
            write(root, 'child/CMakeLists.txt', '''\
                project(Child LANGUAGES C CXX)
                include(CheckCSourceCompiles)
                check_c_source_compiles("int main(void) { return 0; }" CHILD_C)
                if(NOT CHILD_C)
                  message(FATAL_ERROR "Child probe failed")
                endif()
                add_library(plain STATIC ../plain.c)
            ''')
            write(root, 'CMakeLists.txt', '''\
                cmake_minimum_required(VERSION 3.25)
                project(dolphin-emu LANGUAGES C CXX)
                add_subdirectory(child)
                add_subdirectory(Source/UnitTests)
                execute_process(COMMAND "${CMAKE_COMMAND}" -S "${CMAKE_SOURCE_DIR}/probe"
                  -B "${CMAKE_BINARY_DIR}/probe" -G Ninja
                  "-DCMAKE_C_COMPILER=${CMAKE_C_COMPILER}"
                  "-DCMAKE_CXX_COMPILER=${CMAKE_CXX_COMPILER}"
                  RESULT_VARIABLE probe_result OUTPUT_VARIABLE probe_output ERROR_VARIABLE probe_error)
                if(probe_result)
                  message(FATAL_ERROR "Nested probe failed: ${probe_output}${probe_error}")
                endif()
                add_custom_command(OUTPUT "${CMAKE_BINARY_DIR}/generated.cpp"
                  COMMAND "${CMAKE_COMMAND}" -E copy "${CMAKE_SOURCE_DIR}/generated.cpp.in"
                    "${CMAKE_BINARY_DIR}/generated.cpp" DEPENDS generated.cpp.in)
                add_library(common STATIC common.cpp special.cpp "${CMAKE_BINARY_DIR}/generated.cpp")
                target_link_libraries(common PRIVATE plain)
                set_source_files_properties(special.cpp PROPERTIES COMPILE_OPTIONS -DPER_SOURCE=1)
                # Model a child resetting launchers, like SDL's own setup.
                set_property(TARGET common PROPERTY CXX_COMPILER_LAUNCHER "$ENV{S2K_CI_COMPILER_CACHE}")
                add_library(glslang STATIC external.cpp)
                add_library(external_pch STATIC external.cpp)
                target_precompile_headers(external_pch PRIVATE "${CMAKE_SOURCE_DIR}/Source/PCH/pch.h")
                set_property(TARGET external_pch PROPERTY CXX_COMPILER_LAUNCHER "$ENV{S2K_CI_COMPILER_CACHE}")
                add_executable(check main.cpp)
                target_link_libraries(check PRIVATE plain common external_pch)
                # Upstream adds this after project(). The CI setting must follow it.
                target_compile_options(common PRIVATE -ggdb)
                enable_testing()
                add_test(NAME actual_execution COMMAND check)
            ''')
            for event, expected_opt in [('pull_request', '-O1'), ('workflow_dispatch', '-O3')]:
                with self.subTest(event=event):
                    env['GITHUB_EVENT_NAME'] = event
                    build = root / event
                    calls.unlink(missing_ok=True)
                    configure = ['cmake', '-S', root, '-B', build, '-G', 'Ninja',
                                 '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_EXPORT_COMPILE_COMMANDS=ON',
                                 f'-DCMAKE_C_COMPILER={cc}', f'-DCMAKE_CXX_COMPILER={cxx}',
                                 f'-DCMAKE_PROJECT_dolphin-emu_INCLUDE={PRESET}']
                    run(*configure, cwd=root, env=env)
                    # Legacy standard launchers can reach root ABI detection,
                    # which precedes project()'s include. They must not reach any
                    # subsequent feature probe or nested configure. Workflows now
                    # set only S2K_CI_COMPILER_CACHE, avoiding even these two calls.
                    initial = [json.loads(line) for line in calls.read_text().splitlines()] if calls.exists() else []
                    for request in initial:
                        self.assertTrue(request[0].startswith(str(build / 'CMakeFiles')))
                        self.assertIn(Path(request[-1]).name,
                                      ['CMakeCCompilerABI.c', 'CMakeCXXCompilerABI.cpp'])
                    calls.unlink(missing_ok=True)
                    commands = json.loads((build / 'compile_commands.json').read_text())
                    c_command = next(c['command'] for c in commands if c['file'].endswith('plain.c'))
                    if sys.platform.startswith('linux'):
                        self.assertIn(expected_opt, c_command)
                    common_command = next(c['command'] for c in commands if c['file'].endswith('common.cpp'))
                    self.assertIn('cmake_pch', common_command)
                    case_command = next(c['command'] for c in commands if c['file'].endswith('case.cpp'))
                    self.assertIn('cmake_pch', case_command)
                    order = run('ninja', '-C', build, '-t', 'query',
                                'cmake_object_order_depends_target_common', cwd=root, env=env).stdout
                    if event == 'pull_request':
                        self.assertNotIn('cmake_object_order_depends_target_plain', order)
                    else:
                        self.assertIn('cmake_object_order_depends_target_plain', order)
                    if event == 'pull_request':
                        self.assertLess(common_command.index('-ggdb'), common_command.index('-g1'))
                    else:
                        self.assertNotIn('-g1', common_command)
                    special = next(c['command'] for c in commands if c['file'].endswith('special.cpp'))
                    self.assertNotIn('cmake_pch', special)
                    run('cmake', '--build', build, '--parallel', '2', cwd=root, env=env)
                    requests = [json.loads(line) for line in calls.read_text().splitlines()]
                    self.assertTrue(any('plain.c' in ' '.join(req) for req in requests))
                    self.assertFalse(any('cmake_pch' in ' '.join(req) or
                                         'common.cpp' in ' '.join(req) or
                                         'external.cpp' in ' '.join(req) for req in requests))
                    run('cmake', '--build', build, '--target', 'unittests', '--parallel', '2',
                        cwd=root, env=env)
                    run(build / 'Source/UnitTests/tests', cwd=root, env=env)
                    for _ in range(2):
                        run('cmake', '--build', build, '--parallel', '2', cwd=root, env=env)
                        run('ctest', '--test-dir', build, '--output-on-failure', '--no-tests=error',
                            cwd=root, env=env)
                    self.assertEqual((build / 'executed.txt').read_text().splitlines(),
                                     ['executed', 'executed'])
                    # Reconfiguring must not resurrect a cached launcher in probes.
                    calls.unlink()
                    run(*configure, cwd=root, env=env)
                    self.assertFalse(calls.exists())

    def test_manual_msvc_pch_is_not_a_cmake_pch_property(self):
        # This exercises target wiring on POSIX. The real Windows job remains
        # responsible for compiling/linking the upstream /Yc and /Yu commands.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write(root, 'part.cpp', 'int part;\n')
            write(root, 'CMakeLists.txt', '''\
                cmake_minimum_required(VERSION 3.25)
                project(dolphin-emu LANGUAGES CXX)
                set(MSVC TRUE)
                # Earlier /Od values used to be retained by option deduplication.
                add_compile_options(/Od /Ob0)
                add_library(build_pch STATIC part.cpp)
                add_library(use_pch INTERFACE)
                add_dependencies(use_pch build_pch)
                add_library(core STATIC part.cpp)
                target_link_libraries(core PRIVATE use_pch)
                add_library(ordinary STATIC part.cpp)
                foreach(t build_pch core ordinary)
                  target_compile_options(${t} PRIVATE "$<$<CONFIG:Release>:/O2>" "$<$<CONFIG:Release>:/Ob2>")
                  set_target_properties(${t} PROPERTIES LINKER_LANGUAGE CXX
                    C_COMPILER_LAUNCHER bad-inherited CXX_COMPILER_LAUNCHER bad-inherited)
                  file(GENERATE OUTPUT "${CMAKE_BINARY_DIR}/${t}.txt" CONTENT
                    "$<TARGET_PROPERTY:${t},C_COMPILER_LAUNCHER>|$<TARGET_PROPERTY:${t},CXX_COMPILER_LAUNCHER>|$<TARGET_PROPERTY:${t},OPTIMIZE_DEPENDENCIES>")
                endforeach()
            ''')
            env = dict(os.environ, GITHUB_ACTIONS='true', GITHUB_EVENT_NAME='pull_request',
                       S2K_CI_COMPILER_CACHE='cmake;-E;env')
            run('cmake', '-S', root, '-B', root / 'build', '-G', 'Ninja',
                f'-DCMAKE_PROJECT_dolphin-emu_INCLUDE={PRESET}',
                '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_EXPORT_COMPILE_COMMANDS=ON',
                '-DCMAKE_C_COMPILER_LAUNCHER=cmake;-E;env',
                '-DCMAKE_CXX_COMPILER_LAUNCHER=cmake;-E;env', cwd=root, env=env)
            for target in ['core', 'build_pch']:
                self.assertEqual((root / 'build' / f'{target}.txt').read_text(), '||ON')
            self.assertEqual((root / 'build/ordinary.txt').read_text(),
                             'cmake;-E;env|cmake;-E;env|ON')
            commands = json.loads((root / 'build/compile_commands.json').read_text())
            for command in commands:
                options = command['command'].split()
                self.assertEqual([o for o in options if o in ('/Od', '/O1', '/O2')][-1], '/Od')
                self.assertEqual([o for o in options if o in ('/Ob0', '/Ob1', '/Ob2')][-1], '/Ob0')
            # Explicit release artifacts must retain the later upstream optimizer.
            env['GITHUB_EVENT_NAME'] = 'workflow_dispatch'
            run('cmake', '-S', root, '-B', root / 'manual', '-G', 'Ninja',
                f'-DCMAKE_PROJECT_dolphin-emu_INCLUDE={PRESET}',
                '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_EXPORT_COMPILE_COMMANDS=ON', cwd=root, env=env)
            commands = json.loads((root / 'manual/compile_commands.json').read_text())
            for command in commands:
                options = command['command'].split()
                self.assertEqual([o for o in options if o in ('/Od', '/O1', '/O2')][-1], '/O2')
                self.assertEqual([o for o in options if o in ('/Ob0', '/Ob1', '/Ob2')][-1], '/Ob2')



class NativePinVerificationTests(unittest.TestCase):
    def test_local_recursive_gitlinks_reject_missing_and_stale_pins(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            env = dict(os.environ, GIT_ALLOW_PROTOCOL='file',
                       GIT_AUTHOR_NAME='Fixture', GIT_AUTHOR_EMAIL='fixture@example.invalid',
                       GIT_COMMITTER_NAME='Fixture', GIT_COMMITTER_EMAIL='fixture@example.invalid')

            def git(where, *args):
                return run('git', '-C', where, *args, cwd=root, env=env).stdout.strip()

            leaf, library, parent = [root / name for name in ('leaf', 'library', 'parent')]
            for repo in (leaf, library, parent):
                repo.mkdir()
                git(repo, 'init', '-q')
                write(repo, 'version', 'one\n')
                git(repo, 'add', '.')
                git(repo, 'commit', '-qm', 'one')
            old_leaf = git(leaf, 'rev-parse', 'HEAD')
            write(leaf, 'version', 'two\n')
            git(leaf, 'commit', '-qam', 'two')
            new_leaf = git(leaf, 'rev-parse', 'HEAD')
            git(library, 'submodule', 'add', '-q', str(leaf), 'nested')
            git(library / 'nested', 'checkout', '-q', old_leaf)
            git(library, 'commit', '-qam', 'pin nested')
            git(parent, 'submodule', 'add', '-q', str(library), 'Externals/UnknownDependency')
            git(parent, 'commit', '-qam', 'pin native')
            native = parent / 'Externals/UnknownDependency'
            with self.assertRaisesRegex(ValueError, 'recursive gitlink'):
                checkout_native.verify_checkout(parent, 'linux')
            git(parent, 'submodule', 'update', '--init', '--recursive')
            checkout_native.verify_checkout(parent, 'linux')
            git(native / 'nested', 'checkout', '-q', new_leaf)
            with self.assertRaisesRegex(ValueError, 'recursive gitlink'):
                checkout_native.verify_checkout(parent, 'linux')
            git(native / 'nested', 'checkout', '-q', old_leaf)
            git(native, 'checkout', '-q', 'HEAD~1')
            with self.assertRaisesRegex(ValueError, 'expected .* got'):
                checkout_native.verify_checkout(parent, 'linux')
            git(parent, 'submodule', 'deinit', '-f', '--all')
            with self.assertRaisesRegex(ValueError, 'Uninitialized native dependency'):
                checkout_native.verify_checkout(parent, 'linux')


if __name__ == '__main__':
    unittest.main()
