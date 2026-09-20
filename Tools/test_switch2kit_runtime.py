#!/usr/bin/env python3
# Copyright 2026 Dolphin Emulator Project
# SPDX-License-Identifier: GPL-2.0-or-later
"""Exercise the actual parent CMake deployment graph with native ELF fixtures.

The facade/runtime are small native test libraries, not replacement controller
implementations. Native Windows CI separately qualifies the complete real GUI.
"""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SDK = ROOT / 'Externals/Switch2Kit'


@unittest.skipUnless(sys.platform == 'linux', 'Native ELF wiring probe requires Linux')
class RuntimeWiring(unittest.TestCase):
    def command(self, *args, **kwargs):
        return subprocess.run(args, text=True, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, timeout=60, **kwargs)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='Dolphin deployment graph ')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.build = self.root / 'build'
        self.runtime = self.root / 'compiler runtime'
        self.config = self.root / 'runtime.cmake'
        self.output = self.build / 'Binaries'
        resource = self.root / 'Data/Sys/Profiles/GCPad/Switch2Kit GameCube.ini'
        resource.parent.mkdir(parents=True)
        resource.write_text('[Profile]\nButtons/A = `Button S`\n')
        for directory in ('AudioCommon', 'Common', 'Core', 'DiscIO', 'InputCommon',
                          'UICommon', 'VideoCommon', 'VideoBackends', 'UpdaterCommon',
                          'DolphinQt', 'DolphinNoGUI', 'DolphinTool'):
            path = self.root / directory
            path.mkdir()
            (path / 'CMakeLists.txt').write_text('')
        mappings = self.root / 'DolphinQt/Config/Mapping'
        mappings.mkdir(parents=True)
        for extension in ('cpp', 'h'):
            (mappings / f'Switch2KitMapping.{extension}').write_text('// Empty fixture translation unit.\n')
        notices = self.root / 'Externals/Switch2Kit'
        (notices / 'LICENSES').mkdir(parents=True)
        (notices / 'CREDITS.md').write_text('Native fixture attribution, not a distribution.\n')
        (notices / 'LICENSES/MIT-trevlars.txt').write_text('Native fixture license.\n')
        (self.root / 'swift-license.txt').write_text('Native fixture runtime license.\n')
        (self.root / 'icu-license.txt').write_text('Native fixture ICU license.\n')
        (self.root / 'leaf.c').write_text('int runtime_value(void) { return 7; }\n')
        (self.root / 'facade.c').write_text('extern int runtime_value(void); int facade(void) { return runtime_value(); }\n')
        (self.root / 'main.c').write_text('''#ifdef ENABLED
extern int facade(void);
int main(void) { return facade() == 7 ? 0 : 1; }
#else
int main(void) { return 0; }
#endif
''')
        (self.root / 'InputCommon/CMakeLists.txt').write_text('''if(ENABLE_SWITCH2KIT)
  add_library(runtime SHARED "${PROJECT_SOURCE_DIR}/leaf.c")
  set_target_properties(runtime PROPERTIES PREFIX "" SUFFIX ".dll"
    LIBRARY_OUTPUT_DIRECTORY "${PROJECT_SOURCE_DIR}/compiler runtime")
  add_library(facade SHARED "${PROJECT_SOURCE_DIR}/facade.c")
  set_target_properties(facade PROPERTIES PREFIX "" SUFFIX ".dll" OUTPUT_NAME Switch2KitC
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/facade")
  target_link_libraries(facade PRIVATE runtime)
  add_library(Switch2Kit::C ALIAS facade)
  add_custom_target(Switch2KitCBuild DEPENDS facade)
endif()
''')
        for directory, target in (('DolphinQt', 'dolphin-emu'),
                                  ('DolphinNoGUI', 'dolphin-nogui'), ('DolphinTool', 'dolphin-tool')):
            (self.root / directory / 'CMakeLists.txt').write_text(f'''add_executable({target} "${{PROJECT_SOURCE_DIR}}/main.c")
set_target_properties({target} PROPERTIES BUILD_WITH_INSTALL_RPATH TRUE INSTALL_RPATH "$ORIGIN")
if(ENABLE_SWITCH2KIT)
  target_compile_definitions({target} PRIVATE ENABLED)
  target_link_libraries({target} PRIVATE Switch2Kit::C)
endif()
''')
        values = {'S2K_RUNTIME_DIRS': self.runtime,
                  'S2K_SWIFT_LICENSE': self.root / 'swift-license.txt',
                  'S2K_ICU_LICENSE': self.root / 'icu-license.txt',
                  'S2K_COMPILER_VERSION': 'Native fixture, not Swift',
                  'CMAKE_GET_RUNTIME_DEPENDENCIES_PLATFORM': 'linux+elf',
                  'CMAKE_GET_RUNTIME_DEPENDENCIES_TOOL': 'objdump',
                  'CMAKE_GET_RUNTIME_DEPENDENCIES_COMMAND': shutil.which('objdump'),
                  'S2K_READELF': shutil.which('readelf')}
        self.config.write_text(''.join(f'set({key} [==[{value}]==])\n' for key, value in values.items()))
        (self.root / 'CMakeLists.txt').write_text(f'''cmake_minimum_required(VERSION 3.24)
project(HostRuntimeWiring LANGUAGES C CXX)
# Evaluate the production Windows branch with native test libraries. This does
# not claim to emulate Windows, Swift, Qt or Bluetooth.
set(WIN32 ${{TEST_WINDOWS}})
set(ENABLE_QT ON)
set(ENABLE_NOGUI ON)
set(ENABLE_CLI_TOOL ON)
set(ENABLE_AUTOUPDATE OFF)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY "${{PROJECT_BINARY_DIR}}/Binaries")
set(CMAKE_INSTALL_BINDIR bin)
set(SWITCH2KIT_RUNTIME_CONFIG [==[{self.config}]==])
set(SWITCH2KIT_RUNTIME_SCRIPT [==[{SDK / 'Integrations/CMake/StageDesktopRuntime.cmake'}]==])
function(switch2kit_install_linux target)
endfunction()
include([==[{ROOT / 'Source/Core/CMakeLists.txt'}]==])
''')

    def configure(self, enabled=True, windows=True):
        result = self.command('cmake', '-S', str(self.root), '-B', str(self.build), '-G', 'Ninja',
                              f'-DENABLE_SWITCH2KIT={"ON" if enabled else "OFF"}',
                              f'-DTEST_WINDOWS={"ON" if windows else "OFF"}', '-DCMAKE_BUILD_TYPE=Release')
        self.assertEqual(result.returncode, 0, result.stdout)

    def build_hosts(self):
        return self.command('cmake', '--build', str(self.build), '--parallel', '3', '--target',
                            'dolphin-emu', 'dolphin-nogui', 'dolphin-tool')

    def test_packaged_hosts_launch_after_compiler_runtime_is_removed(self):
        self.configure()
        result = self.build_hosts()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertTrue((self.output / 'runtime.dll').is_file(), 'Only the facade was staged, not its runtime')
        for notice in ('CREDITS.md', 'LICENSES/MIT-trevlars.txt', 'SwiftRuntime/LICENSE.txt', 'SwiftRuntime/ICU.txt'):
            self.assertTrue((self.output / 'Switch2KitNotices' / notice).is_file(), notice)
        relocated = self.root / 'relocated application'
        shutil.copytree(self.output, relocated)
        shutil.rmtree(self.build)
        shutil.rmtree(self.runtime)
        for target in ('dolphin-emu', 'dolphin-nogui', 'dolphin-tool'):
            result = self.command(str(relocated / target), env={'PATH': '/usr/bin:/bin'}, cwd=self.root)
            self.assertEqual(result.returncode, 0, result.stdout)
        (relocated / 'runtime.dll').unlink()
        result = self.command(str(relocated / 'dolphin-emu'), env={'PATH': '/usr/bin:/bin'}, cwd=self.root)
        self.assertNotEqual(result.returncode, 0, 'A machine runtime rescued the incomplete package')

    def test_bad_runtime_configuration_stops_host_build(self):
        self.configure()
        self.config.write_text('message(FATAL_ERROR "Fixture runtime selection is invalid")\n')
        result = self.build_hosts()
        self.assertNotEqual(result.returncode, 0, 'Deployment errors must fail the application build')
        self.assertIn('Fixture runtime selection is invalid', result.stdout)
        self.assertFalse((self.output / 'dolphin-emu').exists())

    def test_linux_resources_follow_relocated_prefix_only_when_enabled(self):
        for enabled in (True, False):
            with self.subTest(enabled=enabled):
                self.configure(enabled=enabled, windows=False)
                prefix = self.root / ('enabled install' if enabled else 'disabled install')
                result = self.command('cmake', '--install', str(self.build), '--prefix', str(prefix))
                self.assertEqual(result.returncode, 0, result.stdout)
                installed = prefix / 'bin/Sys/Profiles/GCPad/Switch2Kit GameCube.ini'
                self.assertEqual(installed.exists(), enabled)
                if enabled:
                    self.assertEqual(installed.read_bytes(),
                                     (self.root / 'Data/Sys/Profiles/GCPad/Switch2Kit GameCube.ini').read_bytes())

    def test_disabled_hosts_do_not_read_sdk_or_runtime_configuration(self):
        self.configure(enabled=False)
        self.config.unlink()
        shutil.rmtree(self.root / 'Externals')
        result = self.build_hosts()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertFalse((self.output / 'Switch2KitC.dll').exists())
        self.assertFalse((self.output / 'Switch2KitNotices').exists())
        result = self.command(str(self.output / 'dolphin-emu'), env={'PATH': '/usr/bin:/bin'})
        self.assertEqual(result.returncode, 0, result.stdout)


if __name__ == '__main__':
    unittest.main(verbosity=2)
