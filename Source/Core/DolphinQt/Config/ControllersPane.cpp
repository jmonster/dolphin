// Copyright 2025 Dolphin Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

#include "DolphinQt/Config/ControllersPane.h"

#include <QVBoxLayout>

#ifdef HAVE_SWITCH2KIT
#include <QCheckBox>
#include <QGridLayout>
#include <QGroupBox>
#include <QLabel>
#include <QMessageBox>
#include <QPushButton>
#include <QSignalBlocker>
#include <QTimer>

#include "DolphinQt/QtUtils/NonDefaultQPushButton.h"
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

  layout->addWidget(gamecube_controllers);
  layout->addWidget(m_wiimote_controllers);
#ifdef HAVE_SWITCH2KIT
  layout->addWidget(CreateSwitch2ControllersBox());
#endif
  auto* const common = new CommonControllersWidget(this);
  layout->addWidget(common);
  layout->addStretch(1);
}

#ifdef HAVE_SWITCH2KIT
QGroupBox* ControllersPane::CreateSwitch2ControllersBox()
{
  // Discovery manages physical input devices, not emulated controller types or port mappings.
  auto* const box = new QGroupBox(tr("Switch 2 Controllers"), this);
  auto* const layout = new QGridLayout(box);
  layout->setVerticalSpacing(7);
  layout->setColumnStretch(0, 1);

  auto* const auto_connect = new QCheckBox(tr("Automatically connect"), box);
  auto_connect->setAccessibleName(tr("Automatically connect Switch 2 controllers"));
  auto_connect->setToolTip(
      tr("Listen for supported controllers while Dolphin is open, including on future launches. "
         "This uses Bluetooth. Turning this off keeps connected controllers and saved mappings."));
  auto* const find = new NonDefaultQPushButton(tr("Find Controllers"), box);
  find->setAccessibleName(tr("Find Switch 2 controllers"));
  find->setToolTip(tr("Search for supported Switch 2 controllers. Hold the controller's SYNC "
                      "button for first-time pairing."));
  auto* const stop = new NonDefaultQPushButton(tr("Disconnect All"), box);
  stop->setAccessibleName(tr("Disconnect all Switch 2 controllers"));
  stop->setToolTip(tr("Disconnect all Switch 2 controllers and stop searching for this session. "
                      "Saved mappings and the automatic connection setting are not changed."));
  layout->addWidget(auto_connect, 0, 0);
  layout->addWidget(find, 0, 1);
  layout->addWidget(stop, 0, 2);

  auto* const status = new QLabel(box);
  status->setAccessibleName(tr("Switch 2 connection status"));
  status->setWordWrap(true);
  layout->addWidget(status, 1, 0, 1, 3);
  auto* const help = new QLabel(
      tr("Turn on your controller to reconnect, or hold SYNC to pair. "
         "Choose it next to a GameCube port above to apply recommended controls and rumble. "
         "Use Configure for custom mappings."),
      box);
  help->setWordWrap(true);
  layout->addWidget(help, 2, 0, 1, 3);

  const auto update_status = [status, find, stop, auto_connect] {
    const auto state = ciface::SDL::GetSwitch2KitStatus();
    find->setEnabled(state.available && !state.stopping);
    stop->setEnabled(state.running && !state.stopping);
    auto_connect->setEnabled(state.available && !state.stopping);
    const QSignalBlocker blocker(auto_connect);
    auto_connect->setChecked(state.auto_connect);
    if (!state.available)
      status->setText(tr("SDL controller input is unavailable."));
    else if (state.stopping)
      status->setText(tr("Disconnecting controllers..."));
    else if (state.bluetooth == ciface::SDL::Switch2KitBluetooth::Unauthorized)
      status->setText(tr("Allow Dolphin in System Settings > Privacy & Security > Bluetooth."));
    else if (state.bluetooth == ciface::SDL::Switch2KitBluetooth::Off)
      status->setText(tr("Turn on Bluetooth to connect controllers."));
    else if (state.bluetooth == ciface::SDL::Switch2KitBluetooth::Unsupported)
      status->setText(tr("Bluetooth is not supported on this Mac."));
    else if (state.error != 0)
      status->setText(
          tr("Controller input error %1. Use Find Controllers to retry.").arg(state.error));
    else if (!state.running)
      status->setText(tr("Disconnected. Use Find Controllers to connect."));
    else if (state.scanning && state.auto_connect)
      status->setText(tr("Listening for controllers. Connected: %1.").arg(state.controllers));
    else if (state.scanning)
      status->setText(tr("Searching for 60 seconds. Connected: %1.").arg(state.controllers));
    else if (state.auto_connect)
      status->setText(tr("Automatic connection enabled. Connected: %1.").arg(state.controllers));
    else
      status->setText(
          tr("Connected: %1. Use Find Controllers to add another.").arg(state.controllers));
  };
  auto* const timer = new QTimer(box);
  connect(timer, &QTimer::timeout, box, update_status);
  timer->start(500);

  connect(find, &QPushButton::clicked, box, [this, update_status] {
    const int result = ciface::SDL::FindSwitch2Controllers();
    update_status();
    if (result != 0)
      QMessageBox::warning(this, tr("Switch 2 Controllers"),
                           tr("Controller discovery could not start (error %1). Check Bluetooth "
                              "permission and close other controller apps. If disconnecting, "
                              "wait for it to finish before trying again.")
                               .arg(result));
  });
  connect(stop, &QPushButton::clicked, box, [update_status] {
    ciface::SDL::StopSwitch2Controllers();
    update_status();
  });
  connect(auto_connect, &QCheckBox::toggled, box, [this, update_status](bool enabled) {
    const int result = ciface::SDL::SetSwitch2KitAutoConnect(enabled);
    update_status();
    if (result != 0)
      QMessageBox::warning(this, tr("Switch 2 Controllers"),
                           tr("The automatic connection setting could not be saved or applied "
                              "(error %1). Check configuration access and Bluetooth permission. "
                              "The checkbox shows the saved choice; use Find Controllers to retry.")
                               .arg(result));
  });
  update_status();
  return box;
}
#endif
