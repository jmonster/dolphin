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
bool s_auto_connect = false;
bool s_auto_start_pending = false;
S2KResult s_action_error = S2K_OK;
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
// Both helpers run outside the SDL/adapter lock and share the identity-file lock.
bool LoadAutoConnect()
{
  const std::lock_guard settings_lock(s_settings_mutex);
  const auto path = File::GetUserPath(D_CONFIG_IDX) + "Switch2Kit.ini";
  Common::IniFile ini;
  if (!ini.Load(path))
    return false;
  bool enabled = false;
  ini.GetOrCreateSection("Settings")->Get("AutoConnect", &enabled, false);
  return enabled;
}

bool SaveAutoConnect(bool enabled)
{
  const std::lock_guard settings_lock(s_settings_mutex);
  const auto path = File::GetUserPath(D_CONFIG_IDX) + "Switch2Kit.ini";
  Common::IniFile ini;
  if (File::Exists(path) && !ini.Load(path))
    return false;
  ini.GetOrCreateSection("Settings")->Set("AutoConnect", enabled);
  return ini.Save(path);
}

// Caller holds s_mutex and is on the main thread. Never called from input polling.
int StartSwitch2KitLocked()
{
  if (!s_available)
    return s_action_error = S2K_NOT_READY;
  // Creation/permission presentation belongs to the main run loop, even when
  // startup was explicitly authorized by a preference from a previous launch.
  if (!s_context)
    s_context = s2k_create(nullptr, &s_action_error);
  if (!s_context)
    return s_action_error;
  s_action_error = s2k_set_automatic_discovery(s_context, s_auto_connect ? 1 : 0);
  if (s_action_error != S2K_OK)
    return s_action_error;
  s_action_error = s2k_start(s_context);
  if (s_action_error == S2K_OK)
  {
    s_started = true;
    if (!s_auto_connect)
      s_action_error = s2k_discover(s_context, 60.0);
  }
  return s_action_error;
}
}  // namespace

void InitializeSwitch2Kit()
{
  const bool auto_connect = LoadAutoConnect();
  const std::lock_guard lock(s_mutex);
  s_available = true;
  s_auto_connect = auto_connect;
  s_auto_start_pending = auto_connect;
  s_action_error = S2K_OK;
  s_error = S2K_OK;
}

int FindSwitch2Controllers()
{
  const std::lock_guard lock(s_mutex);
  s_auto_start_pending = false;
  return StartSwitch2KitLocked();
}

int StartSwitch2KitAutoConnect()
{
  const std::lock_guard lock(s_mutex);
  if (!s_auto_start_pending)
    return S2K_OK;
  s_auto_start_pending = false;
  if (!s_auto_connect || s_started)
    return S2K_OK;
  // One startup attempt only. A failure remains visible and Find can retry it.
  return StartSwitch2KitLocked();
}

int SetSwitch2KitAutoConnect(bool enabled)
{
  {
    const std::lock_guard lock(s_mutex);
    if (!s_available)
      return S2K_NOT_READY;
  }
  // Preserve every existing section and fail without changing the preference
  // or radio policy if configuration cannot be read/saved.
  if (!SaveAutoConnect(enabled))
  {
    const std::lock_guard lock(s_mutex);
    return s_action_error = S2K_INTERNAL_ERROR;
  }
  const std::lock_guard lock(s_mutex);
  s_auto_connect = enabled;
  s_auto_start_pending = false;
  if (enabled)
    return StartSwitch2KitLocked();
  // Disabling discovery retains ready controllers and their current mappings.
  s_action_error = s_context && s_started ? s2k_set_automatic_discovery(s_context, 0) : S2K_OK;
  return s_action_error;
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
  // while asynchronous Bluetooth teardown is still completing. Explicit Find or
  // enabling Auto-connect can restart it; a deferred startup callback cannot.
  s_auto_start_pending = false;
  s_started = false;
  s_adapter.reset();
  s_error = S2K_OK;
  if (s_context)
    s_action_error = s2k_stop(s_context);
  // Stop is asynchronous. Never block the main run loop waiting for teardown.
}

void ShutdownSwitch2Kit()
{
  const JoystickLock joystick_lock;
  const std::lock_guard lock(s_mutex);
  s_available = false;
  s_started = false;
  s_auto_start_pending = false;
  s_auto_connect = false;
  s_action_error = S2K_OK;
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
  status.auto_connect = s_auto_connect;
  status.error = s_action_error != S2K_OK ? s_action_error : s_error;
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
