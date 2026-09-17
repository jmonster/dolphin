// Copyright 2026 Dolphin Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

#pragma once

#include <string>

class QWidget;

namespace Switch2KitMapping
{
std::string ProfileForDevice(const std::string& device);
// Explicit user action only. Confirms/backs up custom mappings before replacement.
// A failed or cancelled operation leaves the physical device and layout unchanged.
bool Apply(QWidget* parent, int port, const std::string& device);
}  // namespace Switch2KitMapping
