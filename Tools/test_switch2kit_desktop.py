#!/usr/bin/env python3
# Copyright 2026 Dolphin Emulator Project
# SPDX-License-Identifier: GPL-2.0-or-later
"""Register and launch the exact qualified PR ZIP through normal macOS LaunchServices.

This supplements, never substitutes for, the sandboxed direct-executable test.
There is no rebuild, re-sign, quarantine removal, TCC change or Gatekeeper bypass.
LaunchServices owns the process, so this test cannot collect its exit status;
the original exact-ZIP test independently establishes two exit-zero quit cycles.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile

REPOSITORY = "jmonster/dolphin"
RUN = 35176255148
HEAD = "81d50c55fde4f0606f9e35540dc3f5d02a245e23"
CHECKOUT = "b39660179953e9b9a97426a43b5d4e008ee9d712"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


def api_request(path):
    return urllib.request.Request("https://api.github.com/repos/" + REPOSITORY + path,
        headers={"Authorization": "Bearer " + os.environ["GITHUB_TOKEN"],
                 "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"})


def api(path):
    with urllib.request.urlopen(api_request(path), timeout=30) as response:
        return json.load(response)


def command(arguments, check=True):
    environment = {k: v for k, v in os.environ.items()
                   if k not in ("GITHUB_TOKEN", "GH_TOKEN") and not k.startswith(("DYLD_", "QT_", "QML_"))}
    result = subprocess.run([str(x) for x in arguments], text=True, capture_output=True,
                            timeout=120, env=environment)
    if check and result.returncode:
        raise RuntimeError(f"Command failed ({result.returncode}): {arguments!r}\n"
                           + result.stdout + result.stderr)
    return result


def fetch_application(architecture, work):
    run = api(f"/actions/runs/{RUN}")
    assert run["head_sha"] == HEAD
    artifact = None
    # The Intel producer can still be compiling when this independent acceptance
    # job starts. Never substitute an older artifact or a different source run.
    for attempt in range(40):
        artifacts = api(f"/actions/runs/{RUN}/artifacts?per_page=100")["artifacts"]
        artifact = next((a for a in artifacts if a["name"] == f"Dolphin-Switch2Kit-{architecture}"
                         and not a["expired"]), None)
        if artifact:
            break
        print("The exact source run has not published this architecture yet.", flush=True)
        time.sleep(30)
    if artifact is None:
        raise RuntimeError("Exact qualified application artifact is not available")
    # Obtain the signed download redirect without forwarding the GitHub token
    # to its storage host. The second request deliberately has no auth headers.
    opener = urllib.request.build_opener(NoRedirect)
    try:
        opener.open(api_request(f"/actions/artifacts/{artifact['id']}/zip"), timeout=30)
        raise RuntimeError("Expected GitHub's signed artifact redirect")
    except urllib.error.HTTPError as response:
        if response.code != 302:
            raise
        location = response.headers["Location"]
    assert location.startswith("https://")
    with urllib.request.urlopen(location, timeout=120) as response:
        outer_data = response.read()
    assert "sha256:" + hashlib.sha256(outer_data).hexdigest() == artifact["digest"]
    with zipfile.ZipFile(io.BytesIO(outer_data)) as outer:
        validation = json.loads(outer.read("switch2kit-validation.json"))
        data = outer.read(f"Dolphin-Switch2Kit-{architecture}.zip")
    assert validation["status"] == "passed" and validation["source_revision"] == CHECKOUT
    assert validation["architecture"] == architecture
    assert len(validation["runs"]) == 2
    assert all(r["normal_exit"] and not r["forced_cleanup"] for r in validation["runs"])
    assert hashlib.sha256(data).hexdigest() == validation["archive_sha256"]
    archive = work / "verified-app.zip"
    archive.write_bytes(data)
    command(["/usr/bin/ditto", "-x", "-k", archive, work])
    apps = list(work.glob("*.app"))
    assert len(apps) == 1
    command(["/usr/bin/codesign", "--verify", "--deep", "--strict", apps[0]])
    return apps[0], {"artifact_id": artifact["id"], "archive_sha256": validation["archive_sha256"],
                     "source_run": RUN, "source_head": HEAD, "source_checkout": CHECKOUT,
                     "prior_exit_zero_cycles": 2, "signature_verified_again": True}


def desktop_cycle(app, probe, user, phase):
    result = {"phase": phase, "status": "failed", "window_observed": False,
              "quit_requested": False, "termination_observed": False,
              "exit_status_available": False, "forced_cleanup": False}
    try:
        assert command([probe, "find", app], check=False).returncode == 3
        # This is the ordinary LaunchServices open path, not direct exec or a sandbox.
        opened = command(["/usr/bin/open", "-n", "-a", app, "--args", "--user", user])
        result["open_stdout"] = opened.stdout
        result["open_stderr"] = opened.stderr
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            lookup = command([probe, "find", app], check=False)
            if lookup.returncode == 0:
                pid = int(lookup.stdout.strip())
                if command([probe, "probe", pid], check=False).returncode == 0:
                    result["window_observed"] = True
                    break
            time.sleep(0.5)
        if not result["window_observed"]:
            raise RuntimeError("LaunchServices did not produce a visible application window")
        time.sleep(5)
        command([probe, "probe", pid])
        result["stable_seconds"] = 5
        command([probe, "quit", pid])
        result["quit_requested"] = True
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if command([probe, "find", app], check=False).returncode == 3:
                result["termination_observed"] = True
                break
            time.sleep(0.25)
        if not result["termination_observed"]:
            raise RuntimeError("Application did not terminate after normal quit request")
        result["status"] = "passed"
    except (AssertionError, OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        result["reason"] = str(error)
    finally:
        if command([probe, "find", app], check=False).returncode != 3:
            command([probe, "cleanup", app])
            result["forced_cleanup"] = True
            result["status"] = "failed"
    return result


def main():
    report = {"status": "failed", "architecture": os.environ["ARCH"], "runs": [],
              "scope": "normal macOS LaunchServices registration/open/quit/relaunch of the exact qualified ZIP",
              "physical_controller_tested": False, "stock_clean_mac_tested": False,
              "notarization_tested": False, "download_quarantine_tested": False}
    try:
        assert sys.platform == "darwin" and platform.machine() == report["architecture"]
        report["macos"] = command(["/usr/bin/sw_vers", "-productVersion"]).stdout.strip()
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix="Dolphin Desktop QA ", dir="/private/tmp") as temporary:
            work = Path(temporary)
            app, origin = fetch_application(report["architecture"], work)
            report.update(origin)
            probe = work / "DesktopProbe"
            command(["/usr/bin/xcrun", "swiftc", root / "Tools/switch2kit/DesktopProbe.swift", "-o", probe])
            registered = command([probe, "register", app])
            report["launchservices_registration_status"] = int(registered.stdout.strip())
            assert report["launchservices_registration_status"] == 0
            user = work / "Test User"
            (user / "Config").mkdir(parents=True)
            (user / "Config/Dolphin.ini").write_text(
                "[Analytics]\nEnabled = False\nPermissionAsked = True\n[AutoUpdate]\nUpdateTrack =\n")
            for phase in ("desktop-first-launch", "desktop-relaunch"):
                result = desktop_cycle(app, probe, user, phase)
                report["runs"].append(result)
                if result["status"] != "passed":
                    raise RuntimeError(result.get("reason", "Desktop launch failed"))
            report["status"] = "passed"
    except Exception as error:
        report["reason"] = str(error)
    finally:
        Path("switch2kit-desktop-validation.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
