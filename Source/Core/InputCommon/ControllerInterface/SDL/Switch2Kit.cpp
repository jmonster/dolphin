// Copyright 2026 Dolphin Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

#include "InputCommon/ControllerInterface/SDL/Switch2Kit.h"

#include <memory>
#include <mutex>
#include <string>

#include <SDL3/SDL.h>
#include <Switch2KitSDL3.hpp>

#include "Common/FileUtil.h"
#include "Common/IniFile.h"

namespace ciface::SDL
{
namespace
{
// The adapter owns only this backend's virtual SDL devices. Bluetooth remains in
// the linked Switch2Kit engine; no dashboard, sockets, or virtual HID are used.
std::mutex s_mutex;
std::mutex s_settings_mutex;
std::unique_ptr<Switch2Kit::SDL3Adapter> s_adapter;
S2KContext* s_context = nullptr;
bool s_available = false;
bool s_started = false;
S2KResult s_error = S2K_OK;

// SDL callbacks run with this lock held. Always take it before our own mutex.
class JoystickLock final
{
public:
  JoystickLock() { SDL_LockJoysticks(); }
  ~JoystickLock() { SDL_UnlockJoysticks(); }
};

std::string PhysicalKey(const S2KID& id)
{
  constexpr char HEX[] = "0123456789abcdef";
  std::string key = "s2k:";
  for (const auto byte : id.bytes)
  {
    key += HEX[byte >> 4];
    key += HEX[byte & 15];
  }
  return key;
}
}  // namespace

void InitializeSwitch2Kit()
{
  const std::lock_guard lock(s_mutex);
  s_available = true;
  s_error = S2K_OK;
}

int FindSwitch2Controllers()
{
  const std::lock_guard lock(s_mutex);
  if (!s_available)
    return S2K_NOT_READY;
  // Creation is deliberately deferred to the main-thread GUI action. Creating
  // the SDL backend on a worker thread must never create a Bluetooth manager.
  if (!s_context)
    s_context = s2k_create(nullptr, &s_error);
  if (!s_context)
    return s_error;
  s_error = s2k_start(s_context);
  if (s_error == S2K_OK)
  {
    s_started = true;
    s_error = s2k_discover(s_context, 60.0);
  }
  return s_error;
}

void UpdateSwitch2Kit()
{
  const JoystickLock joystick_lock;
  const std::lock_guard lock(s_mutex);
  if (!s_available || !s_context || !s_started)
    return;
  if (!s_adapter)
    s_adapter = std::make_unique<Switch2Kit::SDL3Adapter>(s_context);
  // Bounded to 256 events; the shared adapter commits each SDL transition.
  // Dolphin still samples controls at its existing input polling cadence.
  s_error = s_adapter->pump();
}

void StopSwitch2Controllers()
{
  const JoystickLock joystick_lock;
  const std::lock_guard lock(s_mutex);
  // Keep subsequent input polls from recreating the adapter while stopped or
  // while asynchronous Bluetooth teardown is still completing. Only Find starts it.
  s_started = false;
  s_adapter.reset();
  if (s_context)
    s_error = s2k_stop(s_context);
  // Stop is asynchronous. Never block the main run loop waiting for teardown.
}

void ShutdownSwitch2Kit()
{
  const JoystickLock joystick_lock;
  const std::lock_guard lock(s_mutex);
  s_available = false;
  s_started = false;
  // Destroy SDL devices before their borrowed C context and before SDL_Quit.
  s_adapter.reset();
  if (s_context)
  {
    s2k_destroy(s_context);
    s_context = nullptr;
  }
  s_error = S2K_OK;
  // The linked library stays resident while asynchronous Swift teardown finishes.
}

Switch2KitStatus GetSwitch2KitStatus()
{
  const std::lock_guard lock(s_mutex);
  Switch2KitStatus status;
  status.available = s_available;
  status.error = s_error;
  if (!s_context)
    return status;
  S2KSnapshot snapshot{};
  std::uint32_t count = 0;
  std::uint32_t flags = 0;
  // A capacity-zero read does not consume the input loop's event history.
  const auto result = s2k_read(s_context, nullptr, 0, sizeof(S2KEvent), &count, &snapshot,
                             sizeof(snapshot), &flags);
  if (result != S2K_OK)
  {
    status.error = result;
    return status;
  }
  status.running = snapshot.running != 0;
  status.stopping = snapshot.stopping != 0;
  status.scanning = snapshot.discovery == S2K_DISCOVERY_SCANNING;
  status.controllers = snapshot.count;
  switch (snapshot.bluetooth)
  {
  case S2K_BT_RESETTING:
    status.bluetooth = Switch2KitBluetooth::Resetting;
    break;
  case S2K_BT_UNSUPPORTED:
    status.bluetooth = Switch2KitBluetooth::Unsupported;
    break;
  case S2K_BT_UNAUTHORIZED:
    status.bluetooth = Switch2KitBluetooth::Unauthorized;
    break;
  case S2K_BT_OFF:
    status.bluetooth = Switch2KitBluetooth::Off;
    break;
  case S2K_BT_ON:
    status.bluetooth = Switch2KitBluetooth::On;
    break;
  default:
    break;
  }
  return status;
}

std::optional<int> GetSwitch2KitPreferredId(std::uint32_t instance)
{
  S2KID physical{};
  {
    const JoystickLock joystick_lock;
    const std::lock_guard lock(s_mutex);
    if (!s_adapter || !s_adapter->identity(instance, &physical, nullptr))
      return std::nullopt;
  }

  // File I/O is outside the SDL/adapter locks and never on the input update path.
  // Use the physical key, not the reconnect-specific SDL instance or connection ID.
  const auto identity = PhysicalKey(physical);
  const std::lock_guard settings_lock(s_settings_mutex);
  const auto path = File::GetUserPath(D_CONFIG_IDX) + "Switch2Kit.ini";
  Common::IniFile ini;
  if (File::Exists(path) && !ini.Load(path))
    return std::nullopt;  // Do not overwrite unreadable user configuration.
  auto* section = ini.GetOrCreateSection("Controllers");
  std::optional<int> available;
  for (int i = 0; i < static_cast<int>(S2K_MAX_CONTROLLERS); ++i)
  {
    std::string saved;
    section->Get(std::to_string(i), &saved);
    if (saved == identity)
      return i;
    if (saved.empty() && !available)
      available = i;
  }
  if (available)
  {
    section->Set(std::to_string(*available), identity);
    if (!ini.Save(path))
      return std::nullopt;
  }
  return available;
}
}  // namespace ciface::SDL
