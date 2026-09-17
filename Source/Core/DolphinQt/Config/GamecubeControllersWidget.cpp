// Copyright 2021 Dolphin Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

#include "DolphinQt/Config/GamecubeControllersWidget.h"

#include <QComboBox>
#include <QGridLayout>
#include <QGroupBox>
#include <QLabel>
#include <QPushButton>
#include <QSignalBlocker>
#include <QVBoxLayout>
#ifdef HAVE_SWITCH2KIT
#include "Core/HW/GCPad.h"
#include "DolphinQt/Config/Mapping/Switch2KitMapping.h"
#include "DolphinQt/QtUtils/ModalMessageBox.h"
#include "InputCommon/ControllerEmu/ControllerEmu.h"
#include "InputCommon/InputConfig.h"
#endif

#include <optional>
#include <utility>

#include "Core/ConfigManager.h"
#include "Core/Core.h"
#include "Core/HW/SI/SI_Device.h"
#include "Core/NetPlayProto.h"
#include "Core/System.h"

#include "DolphinQt/Config/Mapping/GCPadWiiUConfigDialog.h"
#include "DolphinQt/Config/Mapping/MappingWindow.h"
#include "DolphinQt/QtUtils/NonDefaultQPushButton.h"
#include "DolphinQt/QtUtils/SignalBlocking.h"
#include "DolphinQt/Settings.h"

using SIDeviceName = std::pair<SerialInterface::SIDevices, const char*>;
static constexpr std::array s_gc_types = {
    SIDeviceName{SerialInterface::SIDEVICE_NONE, _trans("None")},
    SIDeviceName{SerialInterface::SIDEVICE_GC_CONTROLLER, _trans("Standard Controller")},
    SIDeviceName{SerialInterface::SIDEVICE_WIIU_ADAPTER,
                 _trans("GameCube Controller Adapter (USB)")},
    SIDeviceName{SerialInterface::SIDEVICE_GC_STEERING, _trans("Steering Wheel")},
    SIDeviceName{SerialInterface::SIDEVICE_DANCEMAT, _trans("Dance Mat")},
    SIDeviceName{SerialInterface::SIDEVICE_GC_TARUKONGA, _trans("DK Bongos")},
#ifdef HAS_LIBMGBA
    SIDeviceName{SerialInterface::SIDEVICE_GC_GBA_EMULATED, _trans("GBA (Integrated)")},
#endif
    SIDeviceName{SerialInterface::SIDEVICE_GC_GBA, _trans("GBA (TCP)")},
    SIDeviceName{SerialInterface::SIDEVICE_GC_KEYBOARD, _trans("Keyboard Controller")},
    SIDeviceName{SerialInterface::SIDEVICE_AM_BASEBOARD, _trans("Triforce Baseboard")},
};

static std::optional<int> ToGCMenuIndex(const SerialInterface::SIDevices sidevice)
{
  for (size_t i = 0; i < s_gc_types.size(); ++i)
  {
    if (s_gc_types[i].first == sidevice)
      return static_cast<int>(i);
  }
  return {};
}

static SerialInterface::SIDevices FromGCMenuIndex(const int menudevice)
{
  return s_gc_types[menudevice].first;
}

GamecubeControllersWidget::GamecubeControllersWidget(QWidget* parent) : QWidget(parent)
{
  CreateLayout();
  ConnectWidgets();

  connect(&Settings::Instance(), &Settings::ConfigChanged, this,
          [this] { LoadSettings(Core::GetState(Core::System::GetInstance())); });
  connect(&Settings::Instance(), &Settings::EmulationStateChanged, this,
          [this](Core::State state) { LoadSettings(state); });
  LoadSettings(Core::GetState(Core::System::GetInstance()));
#ifdef HAVE_SWITCH2KIT
  connect(&Settings::Instance(), &Settings::DevicesChanged, this,
          &GamecubeControllersWidget::RefreshSwitch2KitDevices);
  RefreshSwitch2KitDevices();
#endif
}

void GamecubeControllersWidget::CreateLayout()
{
  m_gc_box = new QGroupBox(tr("GameCube Controllers"));
  m_gc_layout = new QGridLayout();
  m_gc_layout->setVerticalSpacing(7);
  m_gc_layout->setColumnStretch(1, 1);

  for (size_t i = 0; i < m_gc_groups.size(); i++)
  {
    auto* gc_label = new QLabel(tr("Port %1").arg(i + 1));
    auto* gc_box = m_gc_controller_boxes[i] = new QComboBox();
    auto* gc_button = m_gc_buttons[i] = new NonDefaultQPushButton(tr("Configure"));

    for (const auto& item : s_gc_types)
    {
      gc_box->addItem(tr(item.second));
    }

    int controller_row = m_gc_layout->rowCount();
    m_gc_layout->addWidget(gc_label, controller_row, 0);
    m_gc_layout->addWidget(gc_box, controller_row, 1);
#ifdef HAVE_SWITCH2KIT
    auto* const devices = m_switch2kit_devices[i] = new QComboBox(this);
    devices->setAccessibleName(tr("Physical controller for Port %1").arg(i + 1));
    devices->setToolTip(
        tr("Choose a connected Switch 2 controller to apply its recommended mapping. "
           "Use Configure for custom mappings or other controllers."));
    devices->setSizeAdjustPolicy(QComboBox::AdjustToMinimumContentsLengthWithIcon);
    devices->setMinimumContentsLength(18);
    m_gc_layout->addWidget(devices, controller_row, 2);
    m_gc_layout->addWidget(gc_button, controller_row, 3);
#else
    m_gc_layout->addWidget(gc_button, controller_row, 2);
#endif
  }
  m_gc_box->setLayout(m_gc_layout);

  auto* layout = new QVBoxLayout;
  layout->setContentsMargins(0, 0, 0, 0);
  layout->setAlignment(Qt::AlignTop);
  layout->addWidget(m_gc_box);
  setLayout(layout);
}

void GamecubeControllersWidget::ConnectWidgets()
{
  for (size_t i = 0; i < m_gc_controller_boxes.size(); ++i)
  {
    connect(m_gc_controller_boxes[i], &QComboBox::currentIndexChanged, this, [this, i] {
      OnGCTypeChanged(i);
      SaveSettings();
    });
    connect(m_gc_buttons[i], &QPushButton::clicked, this, [this, i] { OnGCPadConfigure(i); });
#ifdef HAVE_SWITCH2KIT
    // activated is user-only; hotplug refresh must never replace saved mappings.
    connect(m_switch2kit_devices[i], qOverload<int>(&QComboBox::activated), this,
            [this, i](int) { OnSwitch2KitDeviceSelected(i); });
#endif
  }
}

void GamecubeControllersWidget::OnGCTypeChanged(size_t index)
{
  const SerialInterface::SIDevices si_device =
      FromGCMenuIndex(m_gc_controller_boxes[index]->currentIndex());
  m_gc_buttons[index]->setEnabled(si_device != SerialInterface::SIDEVICE_NONE &&
                                  si_device != SerialInterface::SIDEVICE_GC_GBA);
}

void GamecubeControllersWidget::OnGCPadConfigure(size_t index)
{
  MappingWindow::Type type;

  switch (FromGCMenuIndex(m_gc_controller_boxes[index]->currentIndex()))
  {
  case SerialInterface::SIDEVICE_NONE:
  case SerialInterface::SIDEVICE_GC_GBA:
    return;
  case SerialInterface::SIDEVICE_GC_CONTROLLER:
    type = MappingWindow::Type::MAPPING_GCPAD;
    break;
  case SerialInterface::SIDEVICE_WIIU_ADAPTER:
  {
    GCPadWiiUConfigDialog dialog(static_cast<int>(index), this);
    dialog.exec();
    return;
  }
  case SerialInterface::SIDEVICE_GC_STEERING:
    type = MappingWindow::Type::MAPPING_GC_STEERINGWHEEL;
    break;
  case SerialInterface::SIDEVICE_DANCEMAT:
    type = MappingWindow::Type::MAPPING_GC_DANCEMAT;
    break;
  case SerialInterface::SIDEVICE_GC_TARUKONGA:
    type = MappingWindow::Type::MAPPING_GC_BONGOS;
    break;
  case SerialInterface::SIDEVICE_GC_GBA_EMULATED:
    type = MappingWindow::Type::MAPPING_GC_GBA;
    break;
  case SerialInterface::SIDEVICE_GC_KEYBOARD:
    type = MappingWindow::Type::MAPPING_GC_KEYBOARD;
    break;
  case SerialInterface::SIDEVICE_AM_BASEBOARD:
    type = MappingWindow::Type::MAPPING_AM_BASEBOARD;
    break;
  default:
    return;
  }

  MappingWindow* window = new MappingWindow(this, type, static_cast<int>(index));
  window->setAttribute(Qt::WA_DeleteOnClose, true);
  window->setWindowModality(Qt::WindowModality::WindowModal);
#ifdef HAVE_SWITCH2KIT
  connect(window, &QDialog::finished, this, [this] { RefreshSwitch2KitDevices(); });
#endif
  window->show();
}

void GamecubeControllersWidget::LoadSettings(Core::State state)
{
  const bool running = state != Core::State::Uninitialized;
  for (size_t i = 0; i < m_gc_groups.size(); i++)
  {
    const SerialInterface::SIDevices si_device =
        Config::Get(Config::GetInfoForSIDevice(static_cast<int>(i)));
    const std::optional<int> gc_index = ToGCMenuIndex(si_device);
    if (gc_index)
    {
      SignalBlocking(m_gc_controller_boxes[i])->setCurrentIndex(*gc_index);
      m_gc_controller_boxes[i]->setEnabled(NetPlay::IsNetPlayRunning() ? !running : true);
      OnGCTypeChanged(i);
    }
  }
#ifdef HAVE_SWITCH2KIT
  RefreshSwitch2KitDevices();
#endif
}

void GamecubeControllersWidget::SaveSettings()
{
  {
    Config::ConfigChangeCallbackGuard config_guard;

    for (size_t i = 0; i < m_gc_groups.size(); ++i)
    {
      const SerialInterface::SIDevices si_device =
          FromGCMenuIndex(m_gc_controller_boxes[i]->currentIndex());
      Config::SetBaseOrCurrent(Config::GetInfoForSIDevice(static_cast<int>(i)), si_device);
    }
  }

  SConfig::GetInstance().SaveSettings();
}

#ifdef HAVE_SWITCH2KIT
void GamecubeControllersWidget::RefreshSwitch2KitDevices()
{
  auto* config = Pad::GetConfig();
  if (config->GetControllerCount() < 4)
    return;
  const auto devices = g_controller_interface.GetAllDeviceStrings();
  const bool netplay = NetPlay::IsNetPlayRunning();
  for (size_t i = 0; i < m_switch2kit_devices.size(); ++i)
  {
    auto* box = m_switch2kit_devices[i];
    const QSignalBlocker blocker(box);
    box->clear();
    box->addItem(tr("Choose Switch 2 controller..."), QString());
    for (const auto& device : devices)
    {
      const auto profile = Switch2KitMapping::ProfileForDevice(device);
      if (!profile.empty())
      {
        ciface::Core::DeviceQualifier qualifier;
        qualifier.FromString(device);
        const auto label =
            profile == "Switch2Kit GameCube" ? tr("GameCube (%1)") : tr("Pro Controller (%1)");
        box->addItem(label.arg(qualifier.cid + 1), QString::fromStdString(device));
        box->setItemData(box->count() - 1, QString::fromStdString(device), Qt::ToolTipRole);
      }
    }
    std::string selected;
    {
      const auto lock = ControllerEmu::EmulatedController::GetStateLock();
      selected = config->GetController(static_cast<int>(i))->GetDefaultDevice().ToString();
    }
    const auto qselected = QString::fromStdString(selected);
    const int item = box->findData(qselected);
    if (item >= 0)
      box->setCurrentIndex(item);
    else if (!Switch2KitMapping::ProfileForDevice(selected).empty())
    {
      box->addItem(tr("Disconnected: %1").arg(qselected), qselected);
      box->setCurrentIndex(box->count() - 1);
    }
    else if (!selected.empty())
    {
      box->setItemText(0, tr("Custom / other controller"));
    }
    box->setEnabled(!netplay && box->count() > 1);
  }
}

void GamecubeControllersWidget::OnSwitch2KitDeviceSelected(size_t index)
{
  if (NetPlay::IsNetPlayRunning())
    return;
  const auto device = m_switch2kit_devices[index]->currentData().toString().toStdString();
  if (device.empty())
  {
    RefreshSwitch2KitDevices();
    return;
  }
  auto* config = Pad::GetConfig();
  bool already_assigned = false;
  {
    const auto lock = ControllerEmu::EmulatedController::GetStateLock();
    for (size_t i = 0; i < m_switch2kit_devices.size(); ++i)
    {
      if (i != index &&
          Config::Get(Config::GetInfoForSIDevice(static_cast<int>(i))) ==
              SerialInterface::SIDEVICE_GC_CONTROLLER &&
          config->GetController(static_cast<int>(i))->GetDefaultDevice().ToString() == device)
        already_assigned = true;
    }
  }
  if (already_assigned)
    ModalMessageBox::warning(this, tr("Controller Already Assigned"),
                             tr("This controller is already assigned to another port. "
                                "Set that port to None first, or choose another controller."));
  else if (Switch2KitMapping::Apply(this, static_cast<int>(index), device))
  {
    SignalBlocking(m_gc_controller_boxes[index])
        ->setCurrentIndex(*ToGCMenuIndex(SerialInterface::SIDEVICE_GC_CONTROLLER));
    OnGCTypeChanged(index);
    SaveSettings();
  }
  RefreshSwitch2KitDevices();
}
#endif
