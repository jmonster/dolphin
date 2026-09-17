// Copyright 2026 Dolphin Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later
// Test-only UI/configuration boundaries. Never linked into Dolphin.
#pragma once

#include <array>
#include <cassert>
#include <filesystem>
#include <fstream>
#include <functional>
#include <map>
#include <mutex>
#include <string>
#include <string_view>
#include <utility>

namespace Fake
{
inline bool fail_directory = false, fail_open = false, fail_save = false;
inline int answer = 0, questions = 0, warnings = 0, saves = 0, textures = 0;
inline std::function<void()> during_question;
inline std::string sys_directory, user_directory;
inline unsigned serial = 0;
}

class QWidget {};
class QString
{
public:
  QString() = default;
  QString(const char* value) : m_value(value) {}
  QString(std::string value) : m_value(std::move(value)) {}
  static QString fromStdString(const std::string& value) { return QString(value); }
  std::string toStdString() const { return m_value; }
  QString arg(int number) const
  {
    auto value = m_value;
    const auto index = value.find("%1");
    if (index != std::string::npos)
      value.replace(index, 2, std::to_string(number));
    return value;
  }
  friend QString operator+(const QString& a, const QString& b)
  {
    return QString(a.m_value + b.m_value);
  }
private:
  std::string m_value;
};
#define QStringLiteral(value) QString(value)
class QCoreApplication
{
public:
  static QString translate(const char*, const char* value) { return QString(value); }
};
class QDir
{
public:
  bool mkpath(const QString& directory)
  {
    if (Fake::fail_directory)
      return false;
    std::error_code error;
    std::filesystem::create_directories(directory.toStdString(), error);
    return !error;
  }
};
class QTemporaryFile
{
public:
  explicit QTemporaryFile(const QString& pattern) : m_path(pattern.toStdString())
  {
    m_path.replace(m_path.find("XXXXXX"), 6, std::to_string(++Fake::serial));
  }
  bool open()
  {
    if (Fake::fail_open)
      return false;
    std::ofstream stream(m_path);
    return stream.good();
  }
  QString fileName() const { return QString(m_path); }
  void setAutoRemove(bool value) { m_remove = value; }
  ~QTemporaryFile()
  {
    if (m_remove)
      std::filesystem::remove(m_path);
  }
private:
  std::string m_path;
  bool m_remove = true;
};
struct QMessageBox { enum { Yes = 1, Cancel = 2 }; };
class ModalMessageBox
{
public:
  static void warning(QWidget*, const QString&, const QString&) { ++Fake::warnings; }
  static int question(QWidget*, const QString&, const QString&, int buttons, int default_button)
  {
    assert(buttons == (QMessageBox::Yes | QMessageBox::Cancel));
    assert(default_button == QMessageBox::Cancel);
    ++Fake::questions;
    if (Fake::during_question)
      Fake::during_question();
    return Fake::answer;
  }
};

namespace Common
{
class IniFile
{
public:
  class Section
  {
  public:
    explicit Section(std::string = {}) {}
    using SectionMap = std::map<std::string, std::string>;
    const SectionMap& GetValues() const { return values; }
    void Set(const std::string& key, const std::string& value) { values[key] = value; }
    SectionMap values;
  };
  bool Load(const std::string& path)
  {
    m_sections.clear();
    std::ifstream file(path);
    if (!file)
      return false;
    std::string line, name;
    while (std::getline(file, line))
    {
      if (line.empty())
        continue;
      if (line.front() == '[' && line.back() == ']')
      {
        name = line.substr(1, line.size() - 2);
        GetOrCreateSection(name);
      }
      else if (const auto pos = line.find('='); pos != std::string::npos)
      {
        auto key = line.substr(0, pos), value = line.substr(pos + 1);
        while (!key.empty() && key.back() == ' ') key.pop_back();
        while (!value.empty() && value.front() == ' ') value.erase(0, 1);
        GetOrCreateSection(name)->Set(key, value);
      }
    }
    return true;
  }
  bool Save(const std::string& path)
  {
    if (Fake::fail_save)
      return false;
    std::ofstream file(path);
    for (const auto& [name, section] : m_sections)
    {
      file << '[' << name << "]\n";
      for (const auto& [key, value] : section.GetValues())
        file << key << " = " << value << '\n';
    }
    return file.good();
  }
  Section* GetOrCreateSection(const std::string& name) { return &m_sections[name]; }
  Section* GetSection(const std::string& name)
  {
    const auto found = m_sections.find(name);
    return found == m_sections.end() ? nullptr : &found->second;
  }
private:
  std::map<std::string, Section> m_sections;
};
}

namespace ciface::Core
{
struct DeviceQualifier
{
  std::string source, name;
  int cid = -1;
  void FromString(const std::string& text)
  {
    source.clear(); name.clear(); cid = -1;
    const auto first = text.find('/'), second = text.find('/', first + 1);
    if (first == std::string::npos || second == std::string::npos)
      return;
    source = text.substr(0, first); name = text.substr(second + 1);
    try { cid = std::stoi(text.substr(first + 1, second - first - 1)); } catch (...) {}
  }
  std::string ToString() const { return source + '/' + std::to_string(cid) + '/' + name; }
};
}
class ControllerInterface
{
public:
  bool connected = true;
  bool HasConnectedDevice(const ciface::Core::DeviceQualifier&) const { return connected; }
};
inline ControllerInterface g_controller_interface;
namespace ControllerEmu
{
class EmulatedController
{
public:
  Common::IniFile::Section values;
  static auto GetStateLock()
  {
    static std::recursive_mutex mutex;
    return std::unique_lock<std::recursive_mutex>(mutex);
  }
  void SaveConfig(Common::IniFile::Section* section) { *section = values; }
  void LoadConfig(Common::IniFile::Section* section) { values = *section; }
  void SetDefaultDevice(const std::string& device) { values.Set("Device", device); }
  void UpdateReferences(const ControllerInterface&) {}
};
}
class GCPad : public ControllerEmu::EmulatedController
{
public:
  explicit GCPad(unsigned = 0) {}
  void LoadDefaults(const ControllerInterface&)
  {
    values = Common::IniFile::Section();
    values.Set("Buttons/A", "X");
  }
};
class InputConfig
{
public:
  std::array<GCPad, 4> pads;
  int GetControllerCount() const { return 4; }
  ControllerEmu::EmulatedController* GetController(int port) { return &pads.at(port); }
  std::string GetSysProfileDirectoryPath() const { return Fake::sys_directory; }
  std::string GetUserProfileDirectoryPath() const { return Fake::user_directory; }
  void SaveConfig() { ++Fake::saves; }
  void GenerateControllerTextures() { ++Fake::textures; }
};
namespace Pad
{
inline InputConfig config;
inline InputConfig* GetConfig() { return &config; }
}
