#!/usr/bin/env bash
# Build the fork and its pinned controller library, without patching upstream files.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ $(uname -s) != Linux ]]; then echo 'This helper requires Linux.' >&2; exit 1; fi
for tool in cmake ninja git swift python3 pkg-config; do
  command -v "$tool" >/dev/null || { echo "Missing build tool: $tool" >&2; exit 1; }
done
# Remaining arguments are ordinary CMake configure arguments, as in the Windows helper.
run=false
if [[ ${1:-} == --run ]]; then run=true; shift; fi
if [[ ${GITHUB_ACTIONS:-} == true ]]; then
  python3 Tools/checkout_native.py --verify
else
  git submodule update --init --recursive
fi
cmake -S . -B build-switch2kit -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DENABLE_SWITCH2KIT=ON \
  -DENABLE_SDL=ON -DENABLE_QT=ON -DUSE_SYSTEM_SDL3=OFF \
  -DENABLE_TESTS=OFF -DENABLE_VULKAN=OFF -DENABLE_AUTOUPDATE=OFF \
  -DCMAKE_INSTALL_PREFIX="$PWD/build-switch2kit/install" "$@"
cmake --build build-switch2kit --parallel "${S2K_BUILD_JOBS:-3}"
cmake --install build-switch2kit
printf 'Built: %s/build-switch2kit/install/bin/dolphin-emu\n' "$PWD"
if "$run"; then exec "$PWD/build-switch2kit/install/bin/dolphin-emu"; fi
