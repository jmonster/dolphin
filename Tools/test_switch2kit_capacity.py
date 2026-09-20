#!/usr/bin/env python3
"""Compile the production SDL adapter with an exact-width C ABI capacity check.

The test-only deleted overload rejects size_t capacities on 64-bit hosts even
when Clang/GCC constant-fold array::size() and do not diagnose MSVC's C4267.
No controller engine, SDL implementation, or application code is replaced.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    compiler = os.environ.get('CXX') or shutil.which('clang++') or shutil.which('g++')
    if not compiler:
        raise SystemExit('A C++20 Clang or GCC compiler is required')
    sdk = ROOT / 'Externals/Switch2Kit'
    source = sdk / 'Integrations/SDL3/Switch2KitSDL3.cpp'
    sdl = ROOT / 'Externals/SDL/SDL/include'
    if not source.is_file() or not (sdl / 'SDL3/SDL.h').is_file():
        raise SystemExit('Initialize the pinned Switch2Kit and SDL submodules first')
    with tempfile.TemporaryDirectory(prefix='s2k-capacity-') as directory:
        header = Path(directory) / 'ExactCapacity.hpp'
        header.write_text('''#include <cstddef>
#include <cstdint>
#include <type_traits>
#include "Switch2KitC.h"
static_assert(sizeof(std::size_t) > sizeof(uint32_t), "This regression requires a 64-bit host");
// A capacity with any other type must not silently narrow at the ABI boundary.
template <typename Capacity,
          std::enable_if_t<!std::is_same_v<Capacity, uint32_t>, int> = 0>
S2KResult s2k_read(S2KContext*, S2KEvent*, Capacity, uint32_t, uint32_t*,
                  S2KSnapshot*, uint32_t, uint32_t*) = delete;
''')
        command = [compiler, '-std=c++20', '-Wall', '-Wextra', '-Werror',
                   '-fsyntax-only', '-include', str(header),
                   '-I' + str(sdk / 'Sources/Switch2KitCABI/include'),
                   '-I' + str(sdl), str(source)]
        subprocess.run(command, check=True, timeout=60)
    print('Production SDL adapter uses an exact uint32_t event capacity')


if __name__ == '__main__':
    main()
