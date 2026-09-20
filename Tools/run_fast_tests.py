#!/usr/bin/env python3
# Copyright 2026 Dolphin Emulator Project
# SPDX-License-Identifier: GPL-2.0-or-later
"""Run the small production-code regressions, never a full Dolphin/SDK build.

The suite has a shared wall-clock deadline, not N independent timeout allowances.
A failure or timeout is fatal; kill the entire compiler/test process group.
"""
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SUITE_SECONDS = 60
TEST_SECONDS = 20
# Keep both compiler capacity probes and the existing sanitizer coverage.
TESTS = (
    ("CI policy regressions", ("test_ci_policy.py",), {}),
    ("SDL capacity (Clang)", ("test_switch2kit_capacity.py",), {"CXX": "clang++"}),
    ("SDL capacity (GCC)", ("test_switch2kit_capacity.py",), {"CXX": "g++"}),
    ("Integration and disabled CMake", ("test_switch2kit.py",), {}),
    ("Connection consent", ("test_switch2kit_autoconnect.py",), {}),
    ("Mapping ASan/UBSan", ("test_switch2kit_mapping.py", "--sanitize"), {}),
    ("Host lifecycle ASan/UBSan", ("test_switch2kit_host.py", "--sanitize"), {}),
    ("Tiny deployment fixtures", ("test_switch2kit_runtime.py",), {}),
)


class BudgetExceeded(RuntimeError):
    pass


def run_command(command, *, seconds, env, cwd):
    if seconds <= 0:
        raise BudgetExceeded("Shared suite deadline exhausted before starting the next test")
    # Automatic CI is Linux. Do not leave grandchildren (e.g. cc1plus) running.
    process = subprocess.Popen(command, env=env, cwd=cwd, start_new_session=True)
    try:
        result = process.wait(timeout=seconds)
    except subprocess.TimeoutExpired as error:
        raise BudgetExceeded(f"Test exceeded its {seconds:.2f}s remaining allowance") from error
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
    if result:
        raise subprocess.CalledProcessError(result, command)


def run_suite(tests=TESTS, *, suite_seconds=SUITE_SECONDS, test_seconds=TEST_SECONDS,
              root=ROOT):
    started = time.monotonic()
    deadline = started + suite_seconds
    for name, arguments, extra_env in tests:
        print(f"\n=== {name} ===", flush=True)
        before = time.monotonic()
        run_command([sys.executable, str(root / "Tools" / arguments[0]), *arguments[1:]],
                    seconds=min(test_seconds, deadline - before),
                    env={**os.environ, **extra_env}, cwd=root)
        print(f"PASS {name}: {time.monotonic() - before:.2f}s", flush=True)
    elapsed = time.monotonic() - started
    if elapsed > suite_seconds:
        raise BudgetExceeded(f"Suite exceeded {suite_seconds}s")
    print(f"\nAll {len(tests)} checks passed in {elapsed:.2f}s (budget {suite_seconds}s).",
          flush=True)


if __name__ == "__main__":
    if sys.platform != "linux":
        sys.exit("The budgeted PR suite requires Linux; run individual portable tests locally.")
    try:
        run_suite()
    except (BudgetExceeded, subprocess.CalledProcessError, OSError) as error:
        sys.exit(f"FAST CI FAILED: {error}\nFix or reduce the test; do not increase the budget.")
