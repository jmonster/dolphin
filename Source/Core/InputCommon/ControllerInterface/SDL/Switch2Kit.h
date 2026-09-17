// Copyright 2026 Dolphin Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

#pragma once

#include <cstdint>
#include <optional>

namespace ciface::SDL
{
enum class Switch2KitBluetooth
{
  Unknown,
  Resetting,
  Unsupported,
  Unauthorized,
  Off,
  On,
};

struct Switch2KitStatus
{
  bool available = false;
  bool running = false;
  bool scanning = false;
  bool stopping = false;
  std::uint32_t controllers = 0;
  Switch2KitBluetooth bluetooth = Switch2KitBluetooth::Unknown;
  int error = 0;
};

// SDL backend lifecycle: initialize after SDL_Init, shut down BEFORE SDL_Quit.
// Neither function starts Bluetooth. The GUI owns explicit user consent/discovery.
void InitializeSwitch2Kit();
void ShutdownSwitch2Kit();
void UpdateSwitch2Kit();

// Find must be called on the macOS main thread with its run loop running.
int FindSwitch2Controllers();
void StopSwitch2Controllers();
Switch2KitStatus GetSwitch2KitStatus();
std::optional<int> GetSwitch2KitPreferredId(std::uint32_t instance);
}  // namespace ciface::SDL
