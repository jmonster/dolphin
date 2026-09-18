// Copyright 2026 Dolphin Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later
#include "InputCommon/ControllerInterface/SDL/Switch2Kit.h"
#include <iostream>

using namespace ciface::SDL;
int main()
{
  assert(FindSwitch2Controllers() == S2K_NOT_READY);
  InitializeSwitch2Kit();
  UpdateSwitch2Kit();
  assert(GetSwitch2KitStatus().available);
  assert(Fake::created == 0 && Fake::adapters == 0);
  std::cout << "PASS: initialization/poll/status do not start Bluetooth\n";

  Fake::create_error = 4;
  assert(FindSwitch2Controllers() == 4);
  UpdateSwitch2Kit();
  assert(Fake::created == 0 && Fake::adapters == 0);
  Fake::create_error = 0;
  Fake::start_error = S2K_BUSY;
  assert(FindSwitch2Controllers() == S2K_BUSY);
  UpdateSwitch2Kit();
  assert(Fake::adapters == 0);
  Fake::start_error = 0;
  assert(FindSwitch2Controllers() == S2K_OK);
  UpdateSwitch2Kit();
  assert(Fake::created == 1 && Fake::adapters == 1);
  std::cout << "PASS: creation/start failures are retryable without polling a stopped context\n";

  StopSwitch2Controllers();
  const auto stopped_constructions = Fake::constructions.load();
  const auto stopped_pumps = Fake::pumps.load();
  for (int i = 0; i != 100; ++i) UpdateSwitch2Kit();
  assert(Fake::adapters == 0 && Fake::constructions == stopped_constructions);
  assert(Fake::pumps == stopped_pumps && GetSwitch2KitStatus().stopping);
  assert(FindSwitch2Controllers() == S2K_BUSY);
  UpdateSwitch2Kit();
  assert(Fake::adapters == 0);
  Fake::context->state.stopping = false; // Complete asynchronous teardown.
  assert(FindSwitch2Controllers() == S2K_OK);
  UpdateSwitch2Kit();
  assert(Fake::created == 1 && Fake::adapters == 1);
  std::cout << "PASS: disconnect stays disconnected, busy retry and restart reuse the context\n";

  const std::pair<unsigned, Switch2KitBluetooth> states[] = {
      {0, Switch2KitBluetooth::Unknown}, {S2K_BT_RESETTING, Switch2KitBluetooth::Resetting},
      {S2K_BT_UNSUPPORTED, Switch2KitBluetooth::Unsupported},
      {S2K_BT_UNAUTHORIZED, Switch2KitBluetooth::Unauthorized},
      {S2K_BT_OFF, Switch2KitBluetooth::Off}, {S2K_BT_ON, Switch2KitBluetooth::On}};
  for (const auto& [value, expected] : states)
  {
    Fake::context->state.bluetooth = value;
    assert(GetSwitch2KitStatus().bluetooth == expected);
  }
  Fake::read_error = 2;
  assert(GetSwitch2KitStatus().error == 2);
  Fake::read_error = 0;
  Fake::pump_error = 8;
  UpdateSwitch2Kit();
  assert(GetSwitch2KitStatus().error == 8);
  Fake::pump_error = 0;
  std::cout << "PASS: non-consuming status reads and Bluetooth/error reporting\n";

  S2KID first{}, second{};
  first.bytes[0] = 0xa1;
  second.bytes[0] = 0xb2;
  Fake::identities = {{10, first}, {20, second}};
  assert(GetSwitch2KitPreferredId(10) == 0);
  assert(GetSwitch2KitPreferredId(20) == 1);
  const auto saves = Fake::saves;
  Fake::identities = {{30, second}, {40, first}}; // New instances, reverse reconnect order.
  assert(GetSwitch2KitPreferredId(30) == 1);
  assert(GetSwitch2KitPreferredId(40) == 0);
  assert(Fake::saves == saves);
  assert(!GetSwitch2KitPreferredId(999));
  Fake::readable = false;
  assert(!GetSwitch2KitPreferredId(40));
  assert(Fake::saves == saves);
  Fake::readable = true;
  Fake::saved.clear();
  Fake::writable = false;
  assert(!GetSwitch2KitPreferredId(40));
  assert(Fake::saved.empty());
  Fake::writable = true;
  for (unsigned i = 0; i != S2K_MAX_CONTROLLERS; ++i) Fake::saved[std::to_string(i)] = "occupied";
  const auto full_saves = Fake::saves;
  assert(!GetSwitch2KitPreferredId(40));
  assert(Fake::saves == full_saves);
  std::cout << "PASS: persistent identity/reverse reconnect, unknown devices, config failures/full slots\n";

  std::atomic<bool> go = false;
  auto poll = std::thread([&] {
    while (!go.load()) std::this_thread::yield();
    for (int i = 0; i != 2000; ++i) UpdateSwitch2Kit();
  });
  auto status = std::thread([&] {
    while (!go.load()) std::this_thread::yield();
    for (int i = 0; i != 2000; ++i) (void)GetSwitch2KitStatus();
  });
  auto enumerate = std::thread([&] {
    while (!go.load()) std::this_thread::yield();
    for (int i = 0; i != 2000; ++i) (void)GetSwitch2KitPreferredId(40);
  });
  go = true;
  StopSwitch2Controllers();
  ShutdownSwitch2Kit();
  poll.join(); status.join(); enumerate.join();
  ShutdownSwitch2Kit(); // Idempotent shutdown and reinitialization.
  assert(!GetSwitch2KitStatus().available);
  assert(Fake::adapters == 0 && Fake::created == Fake::destroyed);
  InitializeSwitch2Kit();
  UpdateSwitch2Kit();
  assert(Fake::created == 1);
  assert(FindSwitch2Controllers() == S2K_OK);
  UpdateSwitch2Kit();
  ShutdownSwitch2Kit();
  assert(Fake::created == 2 && Fake::destroyed == 2 && Fake::adapters == 0);
  std::cout << "PASS: concurrent poll/status/enumeration/stop/shutdown and reinitialization\n";

  // Auto-connect is a saved opt-in, not a repeated Find operation.
  Fake::saved.clear();
  Fake::settings.clear();
  Fake::exists = false;
  InitializeSwitch2Kit();
  assert(!GetSwitch2KitStatus().auto_connect);
  assert(StartSwitch2KitAutoConnect() == S2K_OK);
  assert(Fake::context == nullptr);
  const auto manual_windows = Fake::discoveries;
  assert(SetSwitch2KitAutoConnect(true) == S2K_OK);
  assert(Fake::settings["AutoConnect"] == "True");
  assert(Fake::context->automatic && GetSwitch2KitStatus().auto_connect);
  UpdateSwitch2Kit();
  const auto starts = Fake::starts, configurations = Fake::configurations;
  const auto setting_saves = Fake::saves, setting_loads = Fake::loads;
  for (int i = 0; i != 1000; ++i)
  {
    UpdateSwitch2Kit();
    (void)GetSwitch2KitStatus();
    assert(StartSwitch2KitAutoConnect() == S2K_OK);
  }
  assert(Fake::starts == starts && Fake::configurations == configurations);
  assert(Fake::discoveries == manual_windows);
  assert(Fake::saves == setting_saves && Fake::loads == setting_loads);
  assert(GetSwitch2KitPreferredId(40) == 0);
  const auto identities = Fake::saved;
  assert(Fake::settings["AutoConnect"] == "True");
  const auto adapter_count = Fake::constructions.load();
  assert(SetSwitch2KitAutoConnect(false) == S2K_OK);
  assert(!Fake::context->automatic && GetSwitch2KitStatus().running);
  assert(Fake::adapters == 1 && Fake::constructions == adapter_count);
  assert(Fake::saved == identities && Fake::settings["AutoConnect"] == "False");
  std::cout << "PASS: opt-in uses continuous policy without window renewal, remapping or per-poll I/O\n";

  Fake::readable = false;
  assert(SetSwitch2KitAutoConnect(true) == S2K_INTERNAL_ERROR);
  assert(!GetSwitch2KitStatus().auto_connect && !Fake::context->automatic);
  Fake::readable = true;
  Fake::writable = false;
  assert(SetSwitch2KitAutoConnect(true) == S2K_INTERNAL_ERROR);
  assert(!GetSwitch2KitStatus().auto_connect && Fake::saved == identities);
  Fake::writable = true;
  Fake::configure_error = S2K_BUSY;
  assert(SetSwitch2KitAutoConnect(true) == S2K_BUSY);
  UpdateSwitch2Kit();
  assert(GetSwitch2KitStatus().error == S2K_BUSY); // Input cannot hide a failed policy change.
  Fake::configure_error = 0;
  assert(FindSwitch2Controllers() == S2K_OK);
  assert(Fake::context->automatic && GetSwitch2KitStatus().error == S2K_OK);
  StopSwitch2Controllers();
  Fake::context->state.stopping = false;
  const auto stopped_starts = Fake::starts;
  for (int i = 0; i != 100; ++i)
  {
    UpdateSwitch2Kit();
    assert(StartSwitch2KitAutoConnect() == S2K_OK);
  }
  assert(Fake::starts == stopped_starts && Fake::adapters == 0);
  assert(!GetSwitch2KitStatus().running && GetSwitch2KitStatus().auto_connect);
  assert(FindSwitch2Controllers() == S2K_OK);
  assert(Fake::context->automatic && Fake::discoveries == manual_windows);
  ShutdownSwitch2Kit();
  std::cout << "PASS: failed settings/policy changes are visible; manual Disconnect beats auto-connect\n";

  const auto before_relaunch = Fake::created.load();
  InitializeSwitch2Kit();
  UpdateSwitch2Kit();
  assert(Fake::created == before_relaunch && GetSwitch2KitStatus().auto_connect);
  assert(StartSwitch2KitAutoConnect() == S2K_OK);
  assert(Fake::created == before_relaunch + 1 && Fake::context->automatic);
  ShutdownSwitch2Kit();
  InitializeSwitch2Kit();
  StopSwitch2Controllers(); // A deferred startup callback must not undo an explicit stop.
  assert(StartSwitch2KitAutoConnect() == S2K_OK);
  assert(Fake::context == nullptr);
  ShutdownSwitch2Kit();
  InitializeSwitch2Kit();
  Fake::create_error = 4;
  assert(StartSwitch2KitAutoConnect() == 4);
  assert(StartSwitch2KitAutoConnect() == S2K_OK);
  assert(GetSwitch2KitStatus().error == 4 && Fake::context == nullptr);
  Fake::create_error = 0;
  Fake::start_error = S2K_BUSY;
  assert(FindSwitch2Controllers() == S2K_BUSY);
  UpdateSwitch2Kit();
  assert(Fake::adapters == 0);
  Fake::start_error = 0;
  assert(FindSwitch2Controllers() == S2K_OK);
  assert(Fake::context->automatic);
  ShutdownSwitch2Kit();
  Fake::readable = false;
  InitializeSwitch2Kit();
  assert(!GetSwitch2KitStatus().auto_connect);
  assert(StartSwitch2KitAutoConnect() == S2K_OK && Fake::context == nullptr);
  ShutdownSwitch2Kit();
  Fake::readable = true;
  Fake::settings["AutoConnect"] = "invalid";
  InitializeSwitch2Kit();
  assert(!GetSwitch2KitStatus().auto_connect);
  assert(StartSwitch2KitAutoConnect() == S2K_OK && Fake::context == nullptr);
  ShutdownSwitch2Kit();
  assert(Fake::adapters == 0 && Fake::created == Fake::destroyed);
  std::cout << "PASS: saved consent, main-thread lazy startup, one-shot failures and stop-before-start\n";

}
