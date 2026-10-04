#!/usr/bin/env python3
# Copyright 2026 Dolphin Emulator Project
# SPDX-License-Identifier: GPL-2.0-or-later
"""Select validation from changed inputs, not from labels or guessed coverage.

PRs compare their merge result with the event's base SHA. Renames are expanded
into deletion/addition pairs so moving a production file to Docs cannot hide it.
Unknown files conservatively select all native builds. Git errors fail the job.
"""
import argparse
import os
from pathlib import Path
import subprocess

TARGETS = frozenset(('sdk', 'macos', 'linux', 'windows'))
PLATFORM_TOOLS = {
    'Tools/build-switch2kit-linux.sh': 'linux',
    'Tools/build-switch2kit-windows.ps1': 'windows',
    'Tools/test_switch2kit_windows_launch.ps1': 'windows',
    'Tools/test_switch2kit_bundle.py': 'macos',
    'Tools/mac-codesign.sh': 'macos',
}


def select_checks(paths):
    selected = set()
    for path in paths:
        if path == '.github/workflows/switch2kit-desktop.yml':
            continue  # Source archiving has no compilation or behavioral coverage.
        if path in PLATFORM_TOOLS:
            selected.add(PLATFORM_TOOLS[path])
        elif path in ('.github/workflows/switch2kit-macos.yml',
                      '.github/workflows/switch2kit-linux.yml',
                      '.github/workflows/switch2kit-windows.yml'):
            selected.add(Path(path).stem.removeprefix('switch2kit-'))
        elif path in ('Tools/switch2kit_ci.py', 'Tools/test_switch2kit_ci.py',
                      '.github/workflows/native-switch2kit.yml', '.gitmodules'):
            selected.update(TARGETS)
        elif path == 'Externals/Switch2Kit' or path.startswith(('Externals/Switch2Kit/',
                                                               'Externals/SDL/')):
            selected.update(TARGETS)
        elif path.startswith(('Source/UnitTests/', 'Tools/switch2kit/')):
            # The normal upstream test target is executed in the Linux native job.
            if path.startswith('Source/UnitTests/') and not path.startswith('Source/UnitTests/Switch2Kit/'):
                selected.add('linux')
        elif path.startswith('Tools/test_switch2kit') and path.endswith('.py'):
            continue  # These portable tests always execute in the CTest job.
        elif path.startswith(('Docs/', '.tx/')) or path in (
                'Readme.md', 'Contributing.md', 'CODE_OF_CONDUCT.md', 'COPYING',
                'AGENTS.md', '.mailmap', '.git-blame-ignore-revs', '.editorconfig'):
            continue
        else:
            # Includes Source/Core, CMake, resources, other Externals and unknown
            # build inputs. Do not assume a platform-independent edit is harmless.
            selected.update(('macos', 'linux', 'windows'))
    return selected


def changed_paths(base, head='HEAD'):
    result = subprocess.run(['git', 'diff', '--no-renames', '--name-only', '-z', base, head],
                            check=True, stdout=subprocess.PIPE, timeout=15)
    return [os.fsdecode(path) for path in result.stdout.split(b'\0') if path]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base')
    parser.add_argument('--target', choices=('tests', 'all', *sorted(TARGETS)), default='tests')
    args = parser.parse_args()
    selected = select_checks(changed_paths(args.base)) if args.base else (
        set(TARGETS) if args.target == 'all' else set() if args.target == 'tests' else {args.target})
    # Outputs are derived only from constant target names, never from filenames.
    output = ''.join(f'{target}={str(target in selected).lower()}\n' for target in sorted(TARGETS))
    print(output, end='')
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as stream:
            stream.write(output)


if __name__ == '__main__':
    main()
