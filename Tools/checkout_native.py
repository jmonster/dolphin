#!/usr/bin/env python3
# Copyright 2026 Dolphin Emulator Project
# SPDX-License-Identifier: GPL-2.0-or-later
"""Fetch the native build's exact gitlinks concurrently, including pinned commits."""
import argparse
import configparser
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath
import subprocess
import sys


def git(root, *arguments):
    result = subprocess.run(['git', '-C', str(root), *arguments], check=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, timeout=120)
    return result.stdout


def native_modules(root, platform):
    if platform not in ('linux', 'darwin', 'win32'):
        raise ValueError(f'Unsupported native host: {platform}')
    config = configparser.ConfigParser(interpolation=None)
    with (root / '.gitmodules').open() as file:
        config.read_file(file)
    modules = []
    for section in config.sections():
        name = section.removeprefix('submodule "').removesuffix('"')
        path = config[section]['path']
        relative = PurePosixPath(path)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError(f'Unsafe submodule path: {path}')
        active = path != 'Externals/libadrenotools'  # Android only.
        if platform != 'win32' and path in ('Externals/Qt', 'Externals/FFmpeg-bin'):
            active = False  # Windows binaries, not POSIX build dependencies.
        modules.append((name, path, active))
    return modules


def checkout(root, platform):
    modules = native_modules(root, platform)
    paths = [path for _, path, active in modules if active]
    if not paths:
        raise ValueError('No native dependencies selected')
    # Serialize parent configuration writes before starting independent workers.
    # Build helpers use --verify in CI rather than fetching unrelated modules.
    for name, _, active in modules:
        git(root, 'config', f'submodule.{name}.active', str(active).lower())
    git(root, 'submodule', 'init', '--', *paths)
    pins = native_pins(root, paths)

    def update(path):
        # --jobs only parallelizes the initial clones; fetching older gitlink
        # commits afterwards was still serial. Parallelize each complete update.
        output = git(root, 'submodule', 'update', '--init', '--recursive',
                     '--depth=1', '--checkout', '--', path)
        actual = git(root / path, 'rev-parse', 'HEAD').strip()
        if actual != pins[path]:
            raise ValueError(f'{path}: expected {pins[path]}, got {actual}')
        print(f'{path}: {actual}', flush=True)
        return output

    with ThreadPoolExecutor(max_workers=8) as workers:
        list(workers.map(update, paths))


def native_pins(root, paths):
    entries = git(root, 'ls-tree', '-z', 'HEAD', '--', *paths).split('\0')
    pins = {}
    for entry in filter(None, entries):
        metadata, path = entry.split('\t', 1)
        mode, kind, sha = metadata.split()
        if mode != '160000' or kind != 'commit':
            raise ValueError(f'Expected a pinned gitlink: {path}')
        pins[path] = sha
    if set(pins) != set(paths):
        raise ValueError('Selected dependencies do not match committed gitlinks')

    return pins


def verify_checkout(root, platform):
    """Reject missing/stale pins without fetching, including nested gitlinks."""
    paths = [path for _, path, active in native_modules(root, platform) if active]
    if not paths:
        raise ValueError('No native dependencies selected')
    pins = native_pins(root, paths)
    for path, expected in pins.items():
        # git -C on an uninitialized submodule can resolve the parent repository.
        # Require the submodule's own .git before comparing its HEAD.
        if not (root / path / '.git').exists():
            raise ValueError(f'Uninitialized native dependency: {path}')
        actual = git(root / path, 'rev-parse', 'HEAD').strip()
        if actual != expected:
            raise ValueError(f'{path}: expected {expected}, got {actual}')
    status = git(root, 'submodule', 'status', '--recursive', '--', *paths)
    for line in status.splitlines():
        if not line.startswith(' '):
            raise ValueError(f'Uninitialized or stale recursive gitlink: {line}')
    print(f'Verified {len(pins)} native dependencies and their recursive gitlinks', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true', help='Verify pins without fetching')
    args = parser.parse_args()
    try:
        action = verify_checkout if args.verify else checkout
        action(Path(__file__).resolve().parents[1], sys.platform)
    except subprocess.CalledProcessError as error:
        print(error.stdout, file=sys.stderr)
        raise SystemExit(error.returncode)
