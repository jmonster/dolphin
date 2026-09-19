#!/usr/bin/env python3
# Copyright 2026 Dolphin Emulator Project
# SPDX-License-Identifier: GPL-2.0-or-later
"""Static UI/startup guards; execute test_switch2kit_host.py for host behavior."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class AutomaticConnectionWiringTests(unittest.TestCase):
    def read(self, path):
        return (ROOT / path).read_text()

    def test_startup_is_guarded_once_and_after_window_initialization(self):
        main = self.read("Source/Core/DolphinQt/Main.cpp")
        hook = "QTimer::singleShot(0, &win, [] { ciface::SDL::StartSwitch2KitAutoConnect(); });"
        self.assertEqual(main.count(hook), 1)
        self.assertLess(main.index("MainWindow win{"), main.index(hook))
        self.assertLess(main.index(hook), main.index("retval = app.exec();"))
        guarded = main.rsplit("#ifdef HAVE_SWITCH2KIT", 1)[1].split("#endif", 1)[0]
        self.assertIn(hook, guarded)
        self.assertIn('#ifdef HAVE_SWITCH2KIT\n#include <QTimer>', main)

    def test_checkbox_updates_do_not_start_or_remap_controllers(self):
        pane = self.read("Source/Core/DolphinQt/Config/ControllersPane.cpp")
        self.assertIn('tr("Automatically connect Switch 2 controllers")', pane)
        self.assertIn("&QCheckBox::toggled", pane)
        self.assertIn("SetSwitch2KitAutoConnect(enabled)", pane)
        self.assertNotIn("StartSwitch2KitAutoConnect", pane)
        update = pane.split("const auto update_status =", 1)[1].split("auto* const timer", 1)[0]
        self.assertIn("QSignalBlocker", update)
        self.assertIn("state.scanning && state.auto_connect", update)
        for action in ("FindSwitch2Controllers", "StopSwitch2Controllers",
                       "SetSwitch2KitAutoConnect", "Mapping::Apply"):
            self.assertNotIn(action, update)

    def test_section_initialization_does_not_change_connection_policy(self):
        pane = self.read("Source/Core/DolphinQt/Config/ControllersPane.cpp")
        initialization = pane.split("connect(find,", 1)[0]
        for action in ("FindSwitch2Controllers(", "StopSwitch2Controllers(",
                       "SetSwitch2KitAutoConnect(", "StartSwitch2KitAutoConnect(", "Mapping::Apply"):
            self.assertNotIn(action, initialization)

    def test_user_actions_refresh_the_displayed_backend_state(self):
        pane = self.read("Source/Core/DolphinQt/Config/ControllersPane.cpp")
        # Reflect explicit stop and saved-setting failures before the next timer tick.
        for action in ("FindSwitch2Controllers()", "StopSwitch2Controllers()",
                       "SetSwitch2KitAutoConnect(enabled)"):
            self.assertIn(f"{action};\n    update_status();", pane)

    def test_polling_and_initialization_never_start_bluetooth(self):
        native = self.read("Source/Core/InputCommon/ControllerInterface/SDL/Switch2Kit.cpp")
        initialize = native.split("void InitializeSwitch2Kit()", 1)[1].split("int Find", 1)[0]
        polling = native.split("void UpdateSwitch2Kit()", 1)[1].split("void Stop", 1)[0]
        for body in (initialize, polling):
            for forbidden in ("s2k_create(", "s2k_start(", "s2k_discover(", "StartSwitch2KitLocked("):
                self.assertNotIn(forbidden, body)
        self.assertNotIn("SaveAutoConnect", polling)
        self.assertNotIn("LoadAutoConnect", polling)
        stop = native.split("void StopSwitch2Controllers()", 1)[1].split("void Shutdown", 1)[0]
        self.assertIn("s_auto_start_pending = false;", stop)
        self.assertIn("s_started = false;", stop)

    def test_ci_retains_regressions_and_documented_sdk_pin(self):
        workflow = self.read(".github/workflows/native-switch2kit.yml")
        for script in ("test_switch2kit.py", "test_switch2kit_host.py --sanitize",
                       "test_switch2kit_mapping.py --sanitize", "test_switch2kit_autoconnect.py"):
            self.assertIn(script, workflow)
        sdk_pin = workflow.split('rev-parse HEAD)" = ', 1)[1].splitlines()[0]
        self.assertEqual(len(sdk_pin), 40)
        self.assertIn(f"`{sdk_pin}`", self.read("Docs/Switch2Kit.md"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
