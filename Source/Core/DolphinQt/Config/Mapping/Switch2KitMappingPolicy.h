// Copyright 2026 Dolphin Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

#pragma once

#include <string_view>

namespace Switch2KitMapping
{
// Match the named SDL adapter, never a similarly named keyboard or another backend.
inline std::string_view ProfileForDevice(std::string_view source, std::string_view name)
{
  if (source != "SDL")
    return {};
  if (name == "Switch2Kit GameCube")
    return "Switch2Kit GameCube";
  if (name == "Switch2Kit Pro Controller 2")
    return "Switch2Kit Pro Controller 2";
  return {};
}

// A physical assignment is not a customization of the button layout. All other
// settings, including calibration, modifiers and extra bindings, must match.
template <typename Values>
bool SameMapping(Values left, Values right)
{
  left.erase("Device");
  right.erase("Device");
  return left == right;
}
}  // namespace Switch2KitMapping
