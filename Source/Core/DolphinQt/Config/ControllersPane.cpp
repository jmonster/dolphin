// Copyright 2025 Dolphin Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

#include "DolphinQt/Config/ControllersPane.h"

#include <QVBoxLayout>

#ifdef HAVE_SWITCH2KIT
#include <QHBoxLayout>
#include <QLabel>
#include <QMessageBox>
#include <QPushButton>
#include <QTimer>

#include "InputCommon/ControllerInterface/SDL/Switch2Kit.h"
#endif

#include "DolphinQt/Config/CommonControllersWidget.h"
#include "DolphinQt/Config/GamecubeControllersWidget.h"
#include "DolphinQt/Config/WiimoteControllersWidget.h"

ControllersPane::ControllersPane()
{
  CreateMainLayout();
}

void ControllersPane::CreateMainLayout()
{
  auto* const layout = new QVBoxLayout{this};

  auto* const gamecube_controllers = new GamecubeControllersWidget(this);
  m_wiimote_controllers = new WiimoteControllersWidget(this);
  auto* const common = new CommonControllersWidget(this);

  layout->addWidget(gamecube_controllers);
  layout->addWidget(m_wiimote_controllers);
  layout->addWidget(common);
#ifdef HAVE_SWITCH2KIT
  auto* const actions = new QHBoxLayout;
  auto* const find = new QPushButton(tr("Find Switch 2 Controllers"), this);
  auto* const stop = new QPushButton(tr("Disconnect Switch 2 Controllers"), this);
  actions->addWidget(find);
  actions->addWidget(stop);
  layout->addLayout(actions);
  auto* const status = new QLabel(this);
  status->setWordWrap(true);
  layout->addWidget(status);
  auto* const help = new QLabel(
      tr("Hold Sync to pair, then choose your GameCube or Pro controller next to a port above. "
         "Recommended controls and rumble are applied for you. Configure is only needed for "
         "custom mappings. No separate controller app is needed."), this);
  help->setWordWrap(true);
  layout->addWidget(help);
  connect(find, &QPushButton::clicked, this, [this] {
    const int result = ciface::SDL::FindSwitch2Controllers();
    if (result != 0)
      QMessageBox::warning(this, tr("Switch 2 Controllers"),
                           tr("Controller discovery could not start (error %1). Check Bluetooth "
                              "permission and close other controller apps. If disconnecting, "
                              "wait for it to finish before trying again.").arg(result));
  });
  connect(stop, &QPushButton::clicked, this, [] { ciface::SDL::StopSwitch2Controllers(); });
  const auto update_status = [status, find, stop] {
    const auto state = ciface::SDL::GetSwitch2KitStatus();
    find->setEnabled(state.available && !state.stopping);
    stop->setEnabled(state.running && !state.stopping);
    if (!state.available)
      status->setText(tr("SDL controller input is unavailable."));
    else if (state.stopping)
      status->setText(tr("Disconnecting controllers..."));
    else if (!state.running)
      status->setText(tr("Switch 2 controller support is stopped."));
    else if (state.bluetooth == ciface::SDL::Switch2KitBluetooth::Unauthorized)
      status->setText(tr("Allow Dolphin in System Settings > Privacy & Security > Bluetooth."));
    else if (state.bluetooth == ciface::SDL::Switch2KitBluetooth::Off)
      status->setText(tr("Turn on Bluetooth to connect controllers."));
    else if (state.bluetooth == ciface::SDL::Switch2KitBluetooth::Unsupported)
      status->setText(tr("Bluetooth is not supported on this Mac."));
    else if (state.error != 0)
      status->setText(tr("Controller input error %1. Try discovery again.").arg(state.error));
    else if (state.scanning)
      status->setText(tr("Searching for 60 seconds: hold Sync. Connected: %1.")
                          .arg(state.controllers));
    else
      status->setText(tr("Connected Switch 2 controllers: %1. Use Find to add another.")
                          .arg(state.controllers));
  };
  auto* const timer = new QTimer(this);
  connect(timer, &QTimer::timeout, this, update_status);
  timer->start(500);
  update_status();
#endif
  layout->addStretch(1);
}
