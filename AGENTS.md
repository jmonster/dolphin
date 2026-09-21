# Working on this Dolphin fork

## Upstream first

Keep Dolphin's upstream build system, Google Test suite, coding conventions and
project documentation intact. Make the smallest additive change for Switch2Kit.
Do not introduce a fork-wide test framework, custom YAML policy language, or a
blanket rule forbidding native validation. Upstream's external Buildbot service
is not automatically inherited by this fork; do not claim otherwise.

The existing `unittests` target remains the baseline. Register our focused tests
with CTest in `Source/UnitTests/Switch2Kit`, not a parallel Python test runner.
On supported POSIX hosts they belong to the ordinary `ENABLE_TESTS` suite even
with `ENABLE_SWITCH2KIT=OFF`. Never add a separate test opt-in or gate the fixture
regressions on the application backend; they do not need Swift or Bluetooth.
The same registration can be configured alone for fast iteration:

```sh
git submodule update --init --depth 1 Externals/Switch2Kit Externals/SDL/SDL
cmake -S Source/UnitTests/Switch2Kit -B build-switch2kit-tests
ctest --test-dir build-switch2kit-tests --output-on-failure --no-tests=error
```

## Efficiency without loss of validation

Fast tests must exercise the smallest relevant production boundary. Keep ASan /
UBSan, both Linux compiler-capacity probes, real CMake feature guards, and mapping,
consent, identity, lifecycle and deployment regressions. The local CTest suite
should remain under one minute; each command has a 20-second timeout and the CI
job a 3-minute ceiling. Fix slow tests rather than silently dropping assertions,
disabling sanitizers, increasing timeouts, or claiming skipped tests passed.

Use changed inputs to avoid unrelated work. Documentation must not rebuild five
applications. SDK/SDL pin changes require the real SDK, rumble and SDL integration
suites plus native builds. Shared production/build/resource changes require native
build/link/package/launch validation on all supported desktop architectures.
Platform-specific scripts require their affected platform. Test the selector for
renames, deletions, shared inputs and failure cases; unknown inputs fail toward
more validation, not less. Never use labels or manual dispatch as a substitute
for necessary automatic validation.

Use compiler caches and the ordinary CMake build graph. Reuse upstream core
objects rather than duplicating standalone builds. Run the unchanged upstream
unit suite in the Linux application build tree. Do not duplicate it per platform
without a demonstrated need. Cache hits must never skip test execution, relinking
or package checks. Report cold/warm timings separately; caches can miss or expire.
Cancel obsolete runs, fail early, and upload application artifacts only when
requested. Do not add nightly builds, extra matrices or broader triggers without
an explicit need and a measured runtime/cost impact.

## Automatic-job runtime budget

Every automatic job, including native setup/build/package/launch work, has a
10-minute maximum. The focused suite keeps its stricter existing limits. A timed
out or cancelled native job is a failure, not a successful fast run. Do not raise
this budget, shard the same work into more billed jobs, switch to larger paid
runners, or delete checks to make the dashboard look fast. A green run above the
budget is not merge-ready. Verify actual job durations on the exact PR head.

Native macOS/Windows smoke builds keep Release defines/runtime ABI but compile
C/C++ without expensive optimization. They still compile/link the complete real
application and execute every architecture/dependency/relocation/archive check.
Linux's optimized builds/upstream unit suite, real Swift SDK tests and sanitizer
regressions remain unchanged. These smoke builds do not establish optimized
macOS/Windows code-generation or gameplay performance correctness. The existing
explicit artifact build uses normal optimized Release flags; local developer
build defaults are unchanged. Do not describe unoptimized smoke builds as release
qualification or distribute them as optimized releases.

Cache the pinned Windows installer, do not upgrade already installed Homebrew
build dependencies, and use the CPUs already assigned to each standard runner.
Compiler-cache statistics must be visible; measure rather than assume a hit.
Cold-cache failures must be fixed, not hidden by reporting only a warm rerun.

## Claims and review

A source check is not a native build; a fixture is not the actual SDK; an SDK test
is not Bluetooth hardware acceptance. Preserve native architecture, dependency,
relocation and exact-archive launch checks. Never trade away required coverage to
advertise a seconds-only result. CI changes must state what still runs, when it
runs, what is not covered, and which exact revision actually passed. Do not merge
based on an earlier revision's green result. Disclose AI assistance and leave
controller behavior, dependency pins and user-data safeguards unchanged unless
the task explicitly requires changing them.
