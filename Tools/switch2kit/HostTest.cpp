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
}
