#!/usr/bin/env python3
# Copyright 2026 Dolphin Emulator Project
# SPDX-License-Identifier: GPL-2.0-or-later
"""Small regression tests for CI fan-out, YAML parsing and runtime limits."""
import contextlib
import copy
import io
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import yaml
from check_ci_policy import (AUTOMATIC_WORKFLOW, ROOT, PolicyError, check_repository,
                             load_workflow, validate_workflow)
from run_fast_tests import (BudgetExceeded, SUITE_SECONDS, TEST_SECONDS, TESTS,
                            run_command, run_suite)


class WorkflowPolicyTests(unittest.TestCase):
    def setUp(self):
        self.workflow = load_workflow(
            (ROOT / '.github/workflows' / AUTOMATIC_WORKFLOW).read_text())

    def reject(self, workflow, name=AUTOMATIC_WORKFLOW):
        with self.assertRaises(PolicyError):
            validate_workflow(name, workflow)

    def test_repository_policy(self):
        check_repository()

    def test_only_one_automatic_job_and_runner(self):
        for field, value in (('runs-on', 'macos-15'), ('runs-on', 'windows-2025-vs2026'),
                             ('runs-on', ['self-hosted']), ('timeout-minutes', '90'),
                             ('strategy', {'matrix': {'os': ['ubuntu-24.04', 'macos-15']}}),
                             ('container', 'swift:6.2.1-noble'), ('services', {}),
                             ('env', {'PYTHONPATH': '${{ runner.temp }}/ci-policy'}),
                             ('uses', './.github/workflows/build.yml'),
                             ('continue-on-error', 'true'), ('if', 'false')):
            with self.subTest(field=field, value=value):
                workflow = copy.deepcopy(self.workflow)
                workflow['jobs']['wiring'][field] = value
                self.reject(workflow)
        self.workflow['jobs']['build'] = copy.deepcopy(self.workflow['jobs']['wiring'])
        self.reject(self.workflow)

    def test_cannot_remove_gates_or_add_full_builds(self):
        for mutation in ('extra', 'removed', 'recursive', 'soft-fail', 'skip', 'replace'):
            with self.subTest(mutation=mutation):
                workflow = copy.deepcopy(self.workflow)
                steps = workflow['jobs']['wiring']['steps']
                if mutation == 'extra':
                    steps.append({'run': 'cmake --build build --target dolphin-emu'})
                elif mutation == 'removed':
                    steps.pop(1)
                elif mutation == 'recursive':
                    steps[0]['with']['submodules'] = 'recursive'
                elif mutation == 'soft-fail':
                    steps[-1]['continue-on-error'] = 'true'
                elif mutation == 'skip':
                    steps[-1]['if'] = 'false'
                else:
                    steps[-1]['run'] = 'python3 Tools/run_fast_tests.py || true'
                self.reject(workflow)

    def test_unfiltered_pr_gate_and_no_duplicate_events(self):
        for events in ({'pull_request': {'paths': ['Source/**']}, 'workflow_dispatch': ''},
                       {'push': '', 'pull_request': '', 'workflow_dispatch': ''},
                       {'workflow_dispatch': ''}):
            self.workflow['on'] = events
            self.reject(self.workflow)

    def test_manual_workflows_reject_all_automatic_trigger_syntaxes(self):
        for trigger in ('pull_request', 'push', 'schedule', 'workflow_run',
                        'workflow_call', 'pull_request_target', 'issue_comment'):
            for events in (trigger, [trigger, 'workflow_dispatch'],
                           {trigger: '', 'workflow_dispatch': ''}):
                with self.subTest(events=events):
                    workflow = {'on': events, 'jobs': {'build': {'timeout-minutes': '45'}}}
                    self.reject(workflow, 'new-expensive.yaml')

    def test_manual_dispatch_forms_remain_usable(self):
        for events in ('workflow_dispatch', ['workflow_dispatch'], {'workflow_dispatch': ''}):
            validate_workflow('manual.yml', {
                'on': events, 'jobs': {'build': {'timeout-minutes': '45'}}})

    def test_manual_timeouts_and_matrices(self):
        for job in ({}, {'timeout-minutes': '120'}, {'timeout-minutes': '${{ inputs.limit }}'},
                    {'timeout-minutes': '0'}, {'timeout-minutes': '45', 'strategy': {}}):
            self.reject({'on': 'workflow_dispatch', 'jobs': {'build': job}}, 'manual.yml')

    def test_real_yaml_parser_preserves_on_and_rejects_ambiguous_yaml(self):
        self.assertEqual(load_workflow('on: [pull_request, workflow_dispatch]')['on'],
                         ['pull_request', 'workflow_dispatch'])
        for text in ('on: workflow_dispatch\non: push\n',
                     'on: workflow_dispatch\njobs:\n  build:\n    runs-on: linux\n    runs-on: macos\n',
                     'on: &events [push]\njobs: *events\n', 'on: [unterminated', '- not-a-workflow'):
            with self.subTest(text=text), self.assertRaises((PolicyError, yaml.YAMLError)):
                load_workflow(text)

    def test_new_yaml_file_is_scanned_and_missing_gate_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workflows = root / '.github/workflows'
            workflows.mkdir(parents=True)
            (root / 'AGENTS.md').write_text('policy')
            with self.assertRaises(PolicyError):
                check_repository(root)
            (workflows / AUTOMATIC_WORKFLOW).write_text(
                (ROOT / '.github/workflows' / AUTOMATIC_WORKFLOW).read_text())
            (workflows / 'surprise.yaml').write_text('on: push\njobs:\n  big:\n    timeout-minutes: 90\n')
            with self.assertRaises(PolicyError):
                check_repository(root)
            (workflows / 'surprise.yaml').unlink()
            (root / 'AGENTS.md').unlink()
            with self.assertRaises(PolicyError):
                check_repository(root)


class RuntimeBudgetTests(unittest.TestCase):
    def test_budgets_and_existing_behavior_checks_are_preserved(self):
        self.assertEqual((SUITE_SECONDS, TEST_SECONDS), (60, 20))
        commands = [(arguments, env) for _, arguments, env in TESTS]
        for arguments, env in (
                (('test_ci_policy.py',), {}),
                (('test_switch2kit_capacity.py',), {'CXX': 'clang++'}),
                (('test_switch2kit_capacity.py',), {'CXX': 'g++'}),
                (('test_switch2kit_mapping.py', '--sanitize'), {}),
                (('test_switch2kit_host.py', '--sanitize'), {}),
                (('test_switch2kit.py',), {}),
                (('test_switch2kit_autoconnect.py',), {}),
                (('test_switch2kit_runtime.py',), {})):
            self.assertIn((arguments, env), commands)

    def test_nonzero_exit_is_not_a_pass(self):
        with self.assertRaises(subprocess.CalledProcessError):
            run_command([sys.executable, '-c', 'raise SystemExit(7)'], seconds=2,
                        env=os.environ, cwd=ROOT)

    def test_expired_deadline_never_starts_another_process(self):
        with patch('run_fast_tests.subprocess.Popen') as spawn:
            with self.assertRaises(BudgetExceeded):
                run_command(['unused'], seconds=0, env={}, cwd=ROOT)
            spawn.assert_not_called()

    def test_shared_deadline_not_a_fresh_allowance_per_test(self):
        ticks = iter((0, 0, 0.25, 0.8, 0.9, 0.9))
        tests = (('one', ('one.py',), {}), ('two', ('two.py',), {}))
        with patch('run_fast_tests.time.monotonic', side_effect=lambda: next(ticks)), \
                patch('run_fast_tests.run_command') as command, \
                contextlib.redirect_stdout(io.StringIO()):
            run_suite(tests, suite_seconds=1, test_seconds=0.75)
        self.assertAlmostEqual(command.call_args_list[0].kwargs['seconds'], 0.75)
        self.assertAlmostEqual(command.call_args_list[1].kwargs['seconds'], 0.2)

    def test_failure_stops_the_suite_immediately(self):
        tests = (('one', ('one.py',), {}), ('two', ('two.py',), {}))
        with patch('run_fast_tests.run_command',
                   side_effect=subprocess.CalledProcessError(1, 'one')) as command, \
                contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(subprocess.CalledProcessError):
                run_suite(tests)
        self.assertEqual(command.call_count, 1)

    @unittest.skipUnless(sys.platform == 'linux', 'The budgeted PR lane is Linux')
    def test_timeout_kills_the_entire_process_group(self):
        # Start a grandchild that ignores SIGTERM. Simulate only the wait timeout,
        # so this test is deterministic and does not sleep for an actual budget.
        process = subprocess.Popen(
            [sys.executable, '-u', '-c',
             'import os,subprocess,sys,time; '
             'child=subprocess.Popen([sys.executable, "-u", "-c", '
             '"import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); '
             'print(123,flush=True); time.sleep(30)"],stdout=subprocess.PIPE); '
             'child.stdout.readline(); print(os.getpgrp(),flush=True); time.sleep(30)'],
            stdout=subprocess.PIPE, text=True, start_new_session=True)
        try:
            self.assertEqual(process.stdout.readline().strip(), str(process.pid))
            actual_wait = process.wait
            def wait(timeout=None):
                if timeout is not None:
                    raise subprocess.TimeoutExpired(process.args, timeout)
                return actual_wait(timeout=2)
            with patch('run_fast_tests.subprocess.Popen', return_value=process), \
                    patch.object(process, 'wait', side_effect=wait), \
                    patch('run_fast_tests.os.killpg', wraps=os.killpg) as kill:
                with self.assertRaises(BudgetExceeded):
                    run_command(['unused'], seconds=1, env={}, cwd=ROOT)
                kill.assert_called_once_with(process.pid, signal.SIGKILL)
            self.assertEqual(process.returncode, -signal.SIGKILL)
        finally:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=2)
            process.stdout.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
