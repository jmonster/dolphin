# Repository instructions

These rules apply to the entire repository and to every agent/contributor.

## CI cost and test speed are hard requirements

Automatic tests must be lean and fast. A slow test must be reduced, replaced with
a focused regression, or removed from automatic CI. Do not solve a timeout by
raising the budget, adding runners, dropping assertions, skipping failures, or
turning off sanitizers. A warm cache is not evidence that a test is cheap.

- Exactly ONE automatic GitHub Actions job: `Native Switch2Kit / wiring`, on
  `ubuntu-24.04`, for pull requests. No automatic macOS/Windows jobs, matrices,
  scheduled builds, `workflow_run` chains, reusable-workflow escape hatches, or
  duplicate branch-push jobs. Keep the gate unfiltered so changes to workflows,
  this file, and test infrastructure are always checked.
- Hard budgets: **60 seconds for the entire regression suite**, **20 seconds per
  test command**, and **3 minutes for the whole job**, including setup. The job
  timeout is a safety ceiling, not a target. Report cold-run timing when changing
  tests; fail closed when a budget is exceeded.
- Test production behavior at the smallest boundary. Small C/C++ harnesses,
  sanitizer checks, source checks and tiny CMake fixtures are appropriate. Do not
  compile Dolphin, Qt, SDL, the Swift SDK, or all dependencies to test a small
  policy/disabled-feature branch. Do not build an application just to inspect it.
- Only shallow checkout and the explicitly needed pinned Switch2Kit/SDL submodules
  belong in the PR lane. No recursive submodule fetch, platform toolchain install,
  source/application archive, or artifact upload. The one pinned PyYAML wheel is
  installed into a temporary directory for structural workflow validation.
- Add focused tests to `Tools/run_fast_tests.py`, not separate workflow jobs.
  Preserve both compiler capacity probes, ASan/UBSan host/mapping coverage, consent,
  and feature-disabled checks. Keep fixtures tiny; do not claim they qualify a
  native platform, packaged application, Bluetooth hardware or gameplay.

## Full application qualification is separate and explicitly requested

The macOS, Linux, Windows and source-archive workflows are **workflow_dispatch
only**. They are optional application/SDK qualification tools, not PR tests.
Do not dispatch them without a human explicitly requesting that expensive work.
Select one architecture/configuration at a time; do not recreate an automatic
build matrix. Preserve real build, packaging, dependency and launch assertions
when changing those tools. A passing fast PR check is not native qualification.

## Required verification for CI/test edits

Install `PyYAML==6.0.3` in your development environment, then run:

```sh
python3 Tools/check_ci_policy.py
python3 Tools/test_ci_policy.py
git submodule update --init --depth 1 Externals/Switch2Kit Externals/SDL/SDL
python3 Tools/run_fast_tests.py   # Linux; enforces the shared deadline
```

`check_ci_policy.py` scans every `.yml`/`.yaml` workflow, rejects additional
automatic triggers/jobs and allowlists the fast lane's steps. Its tests must catch
attempts to restore expensive CI. Do not weaken the checker or runner to make a
change pass. Budget/policy exceptions need explicit repository-owner approval.
Repository-side checks are not a security boundary: keep `wiring` required in
branch protection and review changes to this policy and its enforcement together.

Make targeted changes, preserve controller behavior and user-data safeguards, and
disclose AI-assisted changes and validation limitations in pull requests. Never
claim a test, native build, or hardware check was performed unless it actually ran.
