// Copyright 2026 Dolphin Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

// Test-only boundaries. The test compiles the unmodified production host wrapper,
// not a copy of its logic. These fakes do NOT validate SDL, Swift or Bluetooth.
#include <atomic>
#include <cassert>
#include <cstdint>
#include <map>
#include <mutex>
#include <string>
#include <thread>

using S2KResult = int;
constexpr int S2K_OK = 0, S2K_BUSY = 5, S2K_NOT_READY = 6;
constexpr int S2K_BT_RESETTING = 1, S2K_BT_UNSUPPORTED = 2, S2K_BT_UNAUTHORIZED = 3;
constexpr int S2K_BT_OFF = 4, S2K_BT_ON = 5, S2K_DISCOVERY_SCANNING = 1;
constexpr unsigned S2K_MAX_CONTROLLERS = 64;
struct S2KID { std::uint8_t bytes[16]{}; };
struct S2KEvent {};
struct S2KSnapshot
{
  unsigned running{}, stopping{}, discovery{}, count{}, bluetooth{};
};
struct S2KContext { S2KSnapshot state; };

namespace Fake
{
inline std::recursive_mutex joystick_mutex;
inline thread_local int joystick_depth = 0;
inline std::atomic<int> created = 0, destroyed = 0, adapters = 0, constructions = 0, pumps = 0;
inline S2KResult create_error = 0, start_error = 0, read_error = 0, pump_error = 0;
inline S2KContext* context = nullptr;
inline const auto main_thread = std::this_thread::get_id();
inline bool exists = false, readable = true, writable = true;
inline int saves = 0;
inline std::map<std::string, std::string> saved;
inline std::map<std::uint32_t, S2KID> identities;
}
inline void SDL_LockJoysticks() { Fake::joystick_mutex.lock(); ++Fake::joystick_depth; }
inline void SDL_UnlockJoysticks() { --Fake::joystick_depth; Fake::joystick_mutex.unlock(); }
inline S2KContext* s2k_create(const void*, S2KResult* result)
{
  assert(std::this_thread::get_id() == Fake::main_thread);
  *result = Fake::create_error;
  if (*result) return nullptr;
  ++Fake::created;
  return Fake::context = new S2KContext;
}
inline int s2k_start(S2KContext* context)
{
  if (Fake::start_error) return Fake::start_error;
  if (context->state.stopping) return S2K_BUSY;
  context->state.running = true;
  return S2K_OK;
}
inline int s2k_discover(S2KContext* context, double seconds)
{
  assert(seconds == 60.0);
  context->state.discovery = S2K_DISCOVERY_SCANNING;
  return S2K_OK;
}
inline int s2k_stop(S2KContext* context)
{
  if (context->state.running)
  {
    context->state.running = false;
    context->state.stopping = true;
    context->state.discovery = 0;
  }
  return S2K_OK;
}
inline void s2k_destroy(S2KContext* context)
{
  assert(Fake::adapters == 0); // No adapter may outlive its borrowed context.
  assert(Fake::joystick_depth > 0);
  ++Fake::destroyed;
  delete context;
  Fake::context = nullptr;
}
inline int s2k_read(S2KContext* context, S2KEvent* events, unsigned capacity,
                    unsigned stride, unsigned* count, S2KSnapshot* snapshot,
                    unsigned size, unsigned* flags)
{
  assert(events == nullptr && capacity == 0); // Status must not consume events.
  assert(stride == sizeof(S2KEvent) && size == sizeof(S2KSnapshot));
  *snapshot = context->state;
  *count = *flags = 0;
  return Fake::read_error;
}
namespace Switch2Kit
{
class SDL3Adapter
{
public:
  explicit SDL3Adapter(S2KContext*)
  {
    assert(Fake::joystick_depth > 0);
    ++Fake::adapters;
    ++Fake::constructions;
  }
  ~SDL3Adapter() { assert(Fake::joystick_depth > 0); --Fake::adapters; }
  int pump()
  {
    assert(Fake::joystick_depth > 0);
    ++Fake::pumps;
    return Fake::pump_error;
  }
  bool identity(std::uint32_t instance, S2KID* physical, S2KID*)
  {
    assert(Fake::joystick_depth > 0);
    const auto found = Fake::identities.find(instance);
    if (found == Fake::identities.end()) return false;
    *physical = found->second;
    return true;
  }
};
}
constexpr int D_CONFIG_IDX = 0;
namespace File
{
inline std::string GetUserPath(int) { return "/test-only/"; }
inline bool Exists(const std::string&) { return Fake::exists; }
}
namespace Common
{
class IniFile
{
public:
  class Section
  {
  public:
    std::map<std::string, std::string> values;
    void Get(const std::string& key, std::string* value) { *value = values[key]; }
    void Set(const std::string& key, const std::string& value) { values[key] = value; }
  } section;
  bool Load(const std::string&)
  {
    assert(Fake::joystick_depth == 0); // Never perform config I/O under SDL's lock.
    section.values = Fake::saved;
    return Fake::readable;
  }
  Section* GetOrCreateSection(const char*) { return &section; }
  bool Save(const std::string&)
  {
    assert(Fake::joystick_depth == 0);
    ++Fake::saves;
    if (!Fake::writable) return false;
    Fake::saved = section.values;
    Fake::exists = true;
    return true;
  }
};
}
