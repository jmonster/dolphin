#!/usr/bin/env python3
# Copyright 2026 Dolphin Emulator Project
# SPDX-License-Identifier: GPL-2.0-or-later
"""Fail closed on accidental CI cost regressions. Requires PyYAML 6.0.3."""
from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
AUTOMATIC_WORKFLOW = "native-switch2kit.yml"
CHECKOUT = "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
BOOTSTRAP = ('python3 -m pip install --disable-pip-version-check --no-deps '
             '--only-binary=:all: --retries 1 --timeout 10 '
             '--target "$RUNNER_TEMP/ci-policy" PyYAML==6.0.3\n'
             'python3 Tools/check_ci_policy.py')
SUBMODULES = "git submodule update --init --depth 1 Externals/Switch2Kit Externals/SDL/SDL"
FAST_TESTS = "python3 Tools/run_fast_tests.py"


class PolicyError(ValueError):
    pass


class UniqueLoader(yaml.BaseLoader):
    # BaseLoader preserves 'on' as a string (YAML 1.1 otherwise makes it True).
    def construct_mapping(self, node, deep=False):
        keys = [self.construct_object(key, deep=deep) for key, _ in node.value]
        if any(not isinstance(key, str) for key in keys) or len(keys) != len(set(keys)):
            raise PolicyError("Workflow mapping keys must be unique strings")
        return super().construct_mapping(node, deep=deep)


def load_workflow(text):
    # No aliases/merge keys hiding extra triggers, jobs or overridden budgets.
    if any(isinstance(token, (yaml.tokens.AnchorToken, yaml.tokens.AliasToken))
           for token in yaml.scan(text)):
        raise PolicyError("Workflow anchors and aliases are not allowed")
    workflow = yaml.load(text, Loader=UniqueLoader)
    if not isinstance(workflow, dict):
        raise PolicyError("Workflow must be a mapping")
    return workflow


def require(condition, message):
    if not condition:
        raise PolicyError(message)


def event_names(events):
    if isinstance(events, str):
        return {events}
    if isinstance(events, (dict, list)):
        return set(events)
    raise PolicyError("Invalid workflow triggers")


def validate_workflow(name, workflow):
    events = event_names(workflow.get("on"))
    jobs = workflow.get("jobs")
    require(isinstance(jobs, dict) and jobs, "Workflow must contain jobs")
    if name != AUTOMATIC_WORKFLOW:
        require(events == {"workflow_dispatch"},
                "Only native-switch2kit.yml may run automatically; use workflow_dispatch")
        for job in jobs.values():
            require(isinstance(job, dict), "Invalid manual job")
            limit = job.get("timeout-minutes", "")
            require(str(limit).isdigit() and 0 < int(limit) <= 60,
                    "Manual qualification jobs need an explicit timeout <= 60 minutes")
            require("strategy" not in job, "Select one manual target; no build matrices")
        return

    require(set(workflow) == {"name", "on", "permissions", "concurrency", "jobs"},
            "Automatic workflow has unreviewed top-level settings")
    require(workflow["on"] == {"pull_request": "", "workflow_dispatch": ""},
            "Keep the gate on every PR, without path filters, duplicate pushes or schedules")
    require(workflow["name"] == "Native Switch2Kit", "Keep the required check name stable")
    require(workflow["permissions"] == {"contents": "read"}, "CI must be read-only")
    require(workflow["concurrency"] == {
        "group": "native-switch2kit-${{ github.ref }}", "cancel-in-progress": "true"},
        "Cancel superseded runs for the same ref")
    require(set(jobs) == {"wiring"}, "Automatic CI has exactly one job: wiring")
    job = jobs["wiring"]
    require(isinstance(job, dict), "Invalid automatic job")
    require(set(job) == {"runs-on", "timeout-minutes", "env", "steps"},
            "No matrices, services, containers, reusable jobs or conditional/soft-fail gates")
    require(job["runs-on"] == "ubuntu-24.04", "Only one standard Linux runner is permitted")
    require(job["timeout-minutes"] == "3", "Automatic job hard limit is 3 minutes")
    require(job["env"] == {"PYTHONPATH": "${{ runner.temp }}/ci-policy"},
            "Only the isolated YAML parser path belongs in the automatic job environment")
    expected = [
        {"uses": CHECKOUT, "timeout-minutes": "1", "with": {
            "persist-credentials": "false", "fetch-depth": "1", "submodules": "false"}},
        {"run": BOOTSTRAP, "timeout-minutes": "1"},
        {"run": SUBMODULES, "timeout-minutes": "1"},
        {"run": FAST_TESTS, "timeout-minutes": "2"},
    ]
    steps = job["steps"]
    require(isinstance(steps, list) and all(isinstance(step, dict) for step in steps),
            "Invalid automatic steps")
    normalized = []
    for step in steps:
        step = {key: value for key, value in step.items() if key != "name"}
        if isinstance(step.get("run"), str):
            step["run"] = step["run"].strip()
        normalized.append(step)
    require(normalized == expected,
            "Automatic steps are allowlisted: shallow checkout, policy, two submodules, "
            "bounded tests. No full builds, installers, artifacts or bypasses")


def check_repository(root=ROOT):
    require((root / "AGENTS.md").is_file(), "Root AGENTS.md CI policy is required")
    files = sorted(path for path in (root / ".github/workflows").iterdir()
                   if path.suffix in (".yml", ".yaml"))
    require(any(path.name == AUTOMATIC_WORKFLOW for path in files), "Fast PR gate is missing")
    for path in files:
        try:
            validate_workflow(path.name, load_workflow(path.read_text(encoding="utf-8")))
        except (ValueError, TypeError, yaml.YAMLError) as error:
            raise PolicyError(f"{path.name}: {error}") from error
    print(f"CI policy passed: {len(files)} workflows; one automatic 3-minute Linux job.")


if __name__ == "__main__":
    try:
        check_repository()
    except (PolicyError, OSError) as error:
        sys.exit(f"CI POLICY FAILURE: {error}\nSee AGENTS.md; do not raise the budget to pass.")
