# Testing the Switch2Kit additions

## Upstream baseline

Dolphin's checked-in unit-test system is Google Test plus CMake/CTest, under
`Source/UnitTests`. Its external Buildbot infrastructure is not a GitHub Actions
workflow that a fork inherits. This change preserves the existing upstream
`tests` / `unittests` targets and all their tests. The only extension to the parent
unit-test CMake file registers the Switch2Kit subdirectory on POSIX hosts.
There is no Switch2Kit-specific test opt-in.

The full Linux backend-disabled build now uses `ENABLE_TESTS=ON` and runs the
ordinary `unittests` target, including the Switch2Kit regressions, in that same
build tree. This checks the upstream baseline and our additions together without
a second standalone core build. The image still contains no Swift, and its
existing no-SDK/runtime-dependency assertions remain mandatory.

## Fast iteration uses the same CTest registration

```sh
git submodule update --init --depth 1 Externals/Switch2Kit Externals/SDL/SDL
cmake -S Source/UnitTests/Switch2Kit -B build-switch2kit-tests
ctest --test-dir build-switch2kit-tests --output-on-failure --no-tests=error
```

This executes the existing mapping and host C++ harnesses with ASan/UBSan, real
CMake guard and deployment fixtures, connection-consent checks, and the real
adapter source's type/capacity probes under both Linux compilers. The same tests
run in ordinary POSIX test builds under `ENABLE_TESTS`, regardless of
`ENABLE_SWITCH2KIT`. The existing Windows exclusion reflects the POSIX compiler
harnesses, not a user-selectable test option. There is no separate runner or PyYAML
workflow-policy dependency. A local fixture pass does not qualify the actual SDK,
Qt UI, complete application, native packaging or Bluetooth hardware.

## Automatic selection

`Native Switch2Kit` always runs the small CTest suite and computes changes against
the PR event's base SHA, using the actual merge checkout. It does not use GitHub's
limited path-filter file list. Git failures fail the job. Renames include both
the removed and added path; unknown inputs conservatively request native checks.

| Changed inputs | Additional automatic validation |
| --- | --- |
| Documentation only, or portable fixture tests only | No application builds; the CTest suite still runs |
| SDK/SDL pin or sources, or `.gitmodules` | Real Swift SDK, rumble and in-process SDL suites, then all native builds |
| Shared production code, CMake, dependencies or packaged resources | macOS arm64 + x86_64, Linux enabled + genuinely Swift-free disabled, Windows x64 |
| Platform-specific build/launch script or workflow | That platform's real build and package checks |
| Upstream unit-test sources | Linux application build and ordinary upstream unit suite |
| Change selector or parent workflow | SDK and every native job; validate the actual orchestration |

The three platform workflows are reusable workflows called from the parent,
not independent PR triggers. A selected check must succeed: the aggregate
**Switch2Kit checks** job rejects a failed, cancelled or unexpectedly skipped job.
Make that aggregate check required in repository protection; `wiring` alone is
not sufficient. This PR does not change branch-protection settings.

## Reuse work, not test results

Native C/C++ builds use the standard CMake compiler-launcher mechanism with
sccache. Unchanged objects can be reused, but the real build graph, linking,
architecture/dependency checks and exact-archive launch tests still execute.
Linux disabled follows enabled so unchanged upstream objects can be reused
across the two configurations where compiler/cache keys match. SDK tests cache
the pinned Swift build, but always execute `swift test`, rumble and real SDL tests.

Caches can miss or expire. GitHub cache scope also matters: a PR cache is not a
shared default-branch cache for future PRs. A manual run on `master` can prime
base-branch caches; it is optional and expensive, not run automatically by this
change. Cold native qualification remains a full build and is **not** a
seconds-only operation. Measure cold/warm native timings before claiming savings.
Job timeouts are safety ceilings, not benchmark results.

Pull requests still construct and launch the exact application archives. They
do not upload successful application archives merely to test them. Failure
diagnostics are uploaded; successful distributables are uploaded only for an
explicit Actions **Run workflow** request. Select `macos`, `linux`, `windows`,
`sdk` or `all` in the parent workflow; `tests` is the cheap manual default.
The source-archive workflow remains manual because archiving adds no behavioral
coverage. No hardware qualification is inferred from any CI result.
