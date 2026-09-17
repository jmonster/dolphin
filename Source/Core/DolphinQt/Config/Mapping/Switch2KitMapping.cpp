// Copyright 2026 Dolphin Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

#include "DolphinQt/Config/Mapping/Switch2KitMapping.h"

#include <QCoreApplication>
#include <QDir>
#include <QTemporaryFile>

#include <string_view>

#include "Common/IniFile.h"
#include "Core/HW/GCPad.h"
#include "Core/HW/GCPadEmu.h"
#include "DolphinQt/QtUtils/ModalMessageBox.h"
#include "DolphinQt/Config/Mapping/Switch2KitMappingPolicy.h"
#include "InputCommon/InputConfig.h"

namespace Switch2KitMapping
{
namespace
{
QString Tr(const char* text)
{
  return QCoreApplication::translate("Switch2KitMapping", text);
}

Common::IniFile::Section Snapshot(ControllerEmu::EmulatedController* controller)
{
  Common::IniFile::Section section("Profile");
  controller->SaveConfig(&section);
  return section;
}

bool IsKnownMapping(const Common::IniFile::Section& before, int port, InputConfig* config)
{
  GCPad candidate(port);
  if (SameMapping(before.GetValues(), Snapshot(&candidate).GetValues()))
    return true;  // Cleared/unconfigured pad.
  candidate.LoadDefaults(g_controller_interface);
  if (SameMapping(before.GetValues(), Snapshot(&candidate).GetValues()))
    return true;  // Dolphin's initial keyboard bindings.
  for (const auto* name : {"Switch2Kit GameCube", "Switch2Kit Pro Controller 2"})
  {
    Common::IniFile ini;
    if (!ini.Load(config->GetSysProfileDirectoryPath() + name + ".ini"))
      continue;
    auto* profile = ini.GetSection("Profile");
    if (!profile)
      continue;
    candidate.LoadConfig(profile);
    if (SameMapping(before.GetValues(), Snapshot(&candidate).GetValues()))
      return true;
    // The first version shipped this preset with rumble intentionally unbound.
    if (std::string_view(name) == "Switch2Kit GameCube")
    {
      profile->Set("Rumble/Motor", "");
      candidate.LoadConfig(profile);
      if (SameMapping(before.GetValues(), Snapshot(&candidate).GetValues()))
        return true;
    }
  }
  return false;
}
}  // namespace

std::string ProfileForDevice(const std::string& device)
{
  ciface::Core::DeviceQualifier qualifier;
  qualifier.FromString(device);
  if (qualifier.cid < 0)
    return {};
  return std::string(ProfileForDevice(qualifier.source, qualifier.name));
}

bool Apply(QWidget* parent, int port, const std::string& device)
{
  auto* config = Pad::GetConfig();
  if (port < 0 || port >= config->GetControllerCount())
    return false;
  const auto name = ProfileForDevice(device);
  if (name.empty())
    return false;
  ciface::Core::DeviceQualifier qualifier;
  qualifier.FromString(device);
  if (!g_controller_interface.HasConnectedDevice(qualifier))
  {
    ModalMessageBox::warning(parent, Tr("Switch 2 Controllers"),
                             Tr("The controller disconnected. Connect it and try again."));
    return false;
  }

  Common::IniFile preset;
  if (!preset.Load(config->GetSysProfileDirectoryPath() + name + ".ini") ||
      !preset.GetSection("Profile"))
  {
    ModalMessageBox::warning(parent, Tr("Switch 2 Controllers"),
                             Tr("The recommended profile is missing from this Dolphin build."));
    return false;
  }
  auto* controller = config->GetController(port);
  const auto before = Snapshot(controller);
  const bool customized = !IsKnownMapping(before, port, config);
  if (customized && ModalMessageBox::question(
          parent, Tr("Replace Controller Mapping?"),
          Tr("Replace your custom mapping for Port %1? A backup will be saved in controller "
             "profiles, where it can be restored with Load.").arg(port + 1),
          QMessageBox::Yes | QMessageBox::Cancel, QMessageBox::Cancel) != QMessageBox::Yes)
  {
    return false;
  }
  // Modal dialogs run a nested event loop. Do not overwrite edits made meanwhile.
  if (before.GetValues() != Snapshot(controller).GetValues())
  {
    ModalMessageBox::warning(parent, Tr("Switch 2 Controllers"),
                             Tr("The mapping changed while this dialog was open. Try again."));
    return false;
  }
  if (!g_controller_interface.HasConnectedDevice(qualifier))
  {
    ModalMessageBox::warning(parent, Tr("Switch 2 Controllers"),
                             Tr("The controller disconnected. Connect it and try again."));
    return false;
  }
  if (customized)
  {
    const auto directory = QString::fromStdString(config->GetUserProfileDirectoryPath());
    QTemporaryFile backup(directory +
                          QStringLiteral("Before Switch2Kit Port %1-XXXXXX.ini").arg(port + 1));
    Common::IniFile saved;
    *saved.GetOrCreateSection("Profile") = before;
    if (!QDir().mkpath(directory) || !backup.open() || !saved.Save(backup.fileName().toStdString()))
    {
      ModalMessageBox::warning(parent, Tr("Switch 2 Controllers"),
                               Tr("The backup could not be saved. Your mapping was not changed."));
      return false;
    }
    backup.setAutoRemove(false);
  }
  {
    const auto lock = ControllerEmu::EmulatedController::GetStateLock();
    controller->LoadConfig(preset.GetSection("Profile"));
    controller->SetDefaultDevice(device);
  }
  controller->UpdateReferences(g_controller_interface);
  config->SaveConfig();
  config->GenerateControllerTextures();
  return true;
}
}  // namespace Switch2KitMapping
