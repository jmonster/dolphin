// Copyright 2026 Dolphin Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later
#include "DolphinQt/Config/Mapping/Switch2KitMapping.h"
#include "DolphinQt/Config/Mapping/Switch2KitMappingPolicy.h"
#include <iostream>

int main(int argc, char** argv)
{
  assert(argc == 3);
  Fake::sys_directory = std::string(argv[1]) + '/';
  Fake::user_directory = std::string(argv[2]) + '/';
  auto& config = *Pad::GetConfig();
  auto& pad = config.pads[0];
  const std::string gc = "SDL/0/Switch2Kit GameCube";
  const std::string pro = "SDL/1/Switch2Kit Pro Controller 2";
  assert(Switch2KitMapping::ProfileForDevice(gc) == "Switch2Kit GameCube");
  assert(Switch2KitMapping::ProfileForDevice(pro) == "Switch2Kit Pro Controller 2");
  for (const auto* invalid : {"", "Keyboard/0/Switch2Kit GameCube", "SDL/-1/Switch2Kit GameCube",
                             "SDL/0/Switch2Kit GameCube clone", "SDL/0/Switch2Kit Joy-Con 2 (L)"})
    assert(Switch2KitMapping::ProfileForDevice(std::string(invalid)).empty());
  assert(!Switch2KitMapping::Apply(nullptr, -1, gc));
  assert(!Switch2KitMapping::Apply(nullptr, 4, gc));
  assert(!Switch2KitMapping::Apply(nullptr, 0, "Keyboard/0/Switch2Kit GameCube"));
  assert(Fake::saves == 0);

  assert(Switch2KitMapping::Apply(nullptr, 0, gc));
  assert(pad.values.values.at("Buttons/A") == "`Button S`");
  assert(pad.values.values.at("Rumble/Motor") == "`Motor`");
  assert(pad.values.values.at("Device") == gc);
  assert(Fake::questions == 0 && Fake::saves == 1 && Fake::textures == 1);
  pad.LoadDefaults(g_controller_interface);
  pad.SetDefaultDevice("Keyboard/0/Apple");
  assert(Switch2KitMapping::Apply(nullptr, 0, pro));
  assert(pad.values.values.at("Buttons/A") == "`Button E`");
  assert(pad.values.values.at("Buttons/Y") == "`Button W`");
  assert(Fake::questions == 0);
  assert(Switch2KitMapping::Apply(nullptr, 0, gc));
  pad.values.Set("Rumble/Motor", "");  // Legacy shipped GC preset.
  assert(Switch2KitMapping::Apply(nullptr, 0, gc) && Fake::questions == 0);
  assert(config.pads[1].values.GetValues().empty());
  std::cout << "PASS exact device names, initial/default/legacy presets, both models and per-port isolation\n";

  pad.values.Set("Main Stick/Dead Zone", "17.0");
  const auto before = pad.values.GetValues();
  const int saves = Fake::saves;
  Fake::answer = QMessageBox::Cancel;
  assert(!Switch2KitMapping::Apply(nullptr, 0, pro));
  assert(pad.values.GetValues() == before && Fake::saves == saves);
  Fake::answer = QMessageBox::Yes;
  for (bool* failure : {&Fake::fail_directory, &Fake::fail_open, &Fake::fail_save})
  {
    *failure = true;
    assert(!Switch2KitMapping::Apply(nullptr, 0, pro));
    assert(pad.values.GetValues() == before && Fake::saves == saves);
    *failure = false;
  }
  assert(Switch2KitMapping::Apply(nullptr, 0, pro));
  unsigned backups = 0;
  for (const auto& file : std::filesystem::directory_iterator(Fake::user_directory))
  {
    Common::IniFile saved;
    assert(saved.Load(file.path().string()));
    assert(saved.GetSection("Profile")->GetValues() == before);
    ++backups;
  }
  assert(backups == 1);
  assert(pad.values.values.at("Device") == pro && Fake::saves == saves + 1);
  std::cout << "PASS custom calibration confirmation, default Cancel, backup failures and restorable backup\n";

  pad.values.Set("Buttons/A", "custom");
  Fake::during_question = [&] { pad.values.Set("Buttons/A", "edited while prompt open"); };
  assert(!Switch2KitMapping::Apply(nullptr, 0, gc));
  assert(pad.values.values.at("Buttons/A") == "edited while prompt open");
  Fake::during_question = [] { g_controller_interface.connected = false; };
  assert(!Switch2KitMapping::Apply(nullptr, 0, gc));
  Fake::during_question = {};
  g_controller_interface.connected = true;
  const auto current = pad.values.GetValues();
  const auto sys = Fake::sys_directory;
  Fake::sys_directory += "missing/";
  assert(!Switch2KitMapping::Apply(nullptr, 0, gc));
  assert(pad.values.GetValues() == current);
  Fake::sys_directory = sys;
  std::cout << "PASS nested-dialog edit/disconnect and missing-profile failure paths preserve settings\n";
}
