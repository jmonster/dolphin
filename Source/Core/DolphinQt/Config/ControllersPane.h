// Copyright 2025 Dolphin Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

#pragma once

#include <QWidget>

class QGroupBox;
class WiimoteControllersWidget;

class ControllersPane final : public QWidget
{
  Q_OBJECT
public:
  ControllersPane();

private:
  void CreateMainLayout();
#ifdef HAVE_SWITCH2KIT
  QGroupBox* CreateSwitch2ControllersBox();
#endif

  WiimoteControllersWidget* m_wiimote_controllers;
};
