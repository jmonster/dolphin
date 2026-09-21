# Native Switch 2 controllers

Dolphin's optional Switch2Kit backend connects NSO GameCube, Nintendo Switch 2 Pro
controllers and individual Joy-Con 2 halves through Bluetooth and SDL. It requires
a build with `ENABLE_SWITCH2KIT=ON`; the option is off by default. Enabled builds
require macOS 15 or newer, or the experimental Linux x86-64 / Windows x64 setup below.
No separate dashboard, network bridge, system-wide SDL override, virtual-controller
driver or Accessibility permission is needed.

## Playing a GameCube game

In **Controllers**, find **Switch 2 Controllers**, click **Find Controllers**, allow
Bluetooth access and hold the controller's Sync button. Close other applications
managing the same controller. A manual search lasts 60 seconds; use Find again to retry.

Select **Switch2Kit GameCube** or **Switch2Kit Pro Controller 2** in the physical-device
dropdown beside the desired GameCube port. This selects **Standard Controller** and
applies the recommended buttons, sticks, triggers and rumble mapping. A device can be
assigned to only one active Standard Controller port through this shortcut; set its
old port to None before moving it. Verify the controls in **Configure**, then open a game.

**Standard Controller** is the emulated device the game sees. The adjacent dropdown
selects the physical controller. Changing the emulated type does not start Bluetooth
discovery. These controllers do not use **GameCube Adapter for Wii U** mode.

In **Configure**, **Use Recommended Mapping** applies the preset to the selected
supported device. Changing that window's device selection, refreshing the list or
reconnecting does not overwrite bindings. Replacing custom settings requires confirmation
(Cancel is the default) and creates a uniquely named **Before Switch2Kit Port ...**
profile. Restore it with **Profile > Load**. A missing preset or failed backup leaves
the mapping intact.

The GameCube preset preserves independent analog L/R travel and digital full clicks.
The Pro preset matches the printed A/B/X/Y labels; + is Start, R is GameCube Z, and
ZL/ZR supply on/off L/R. Pro triggers cannot reproduce a variable analog squeeze.

### Automatic connection and recovery

**Automatically connect** starts listening now and saves the choice for future launches.
It is off by default: launching Dolphin with it off does not start Bluetooth or request
permission. With it on, discovery continues independently of emulation pause and the
settings window, without the manual search's 60-second limit.

**Disconnect All** stops input and discovery for the current session, even when automatic
connection is checked. Polling, resuming a game and reopening settings cannot undo that
stop. Use Find or re-enable automatic connection to resume. The saved choice still applies
on the next launch. Unchecking automatic connection stops automatic discovery without
disconnecting ready controllers; a handshake already admitted may finish.

Automatic discovery connects available supported controllers, not a saved allowlist.
It does not assign ports or replace mappings. It cannot wake a powered-off controller
or bypass Bluetooth access requirements, and continuous discovery uses radio resources.

`Switch2Kit.ini` in Dolphin's user configuration directory stores `[Settings] AutoConnect`
and persistent physical-device numbers separately. Failed settings reads or saves do not
overwrite the existing configuration or change the runtime choice. Use Find to retry a
failed start after resolving the reported problem. Unreadable/unwritable configuration or
exhaustion of the 64 saved identity slots falls back to ordinary device numbering; verify
assignments in that case. Adapter or device-address changes can also affect identity on
Linux and Windows. Reconnecting two otherwise unchanged identical controllers in reverse
order retains their saved assignments.

## Controller differences and motion

Discover each Joy-Con 2 half with Find/Sync, then use the ordinary per-port **Configure**
window to bind its SDL buttons and axes manually. The quick port selector supports
GameCube and Pro controllers; the backend does not combine Joy-Con halves into a pair.

For Wii games, configure an **Emulated Wii Remote** separately. The GameCube-port shortcut
does not configure Wii motion, and this integration does not provide a calibrated-motion
setup UI. Selecting a controller or supplying a test calibration file is not motion setup.

NSO GameCube rumble uses its Bluetooth on/off motor channel; Pro/Joy-Con use their
HD-rumble path. Verify actual motor behavior and that zero, disconnect and quit stop it.
An automated callback test is not a physical rumble test.

## Applications and prerequisites

For development artifacts, open **Actions > Native Switch2Kit > Run workflow**, choose
the revision and the `macos`, `linux` or `windows` target, then use the successful run's
artifacts. PRs automatically qualify affected platforms but upload application archives
only when explicitly requested. The workflows and application artifacts are:

| Platform | Workflow | Artifact |
| --- | --- | --- |
| macOS | [Native Switch2Kit](../.github/workflows/native-switch2kit.yml) | `Dolphin-Switch2Kit-arm64` or `Dolphin-Switch2Kit-x86_64` |
| Linux | [Switch2Kit Linux application](../.github/workflows/switch2kit-linux.yml) | `Dolphin-Switch2Kit-linux-x86_64` |
| Windows | [Switch2Kit Windows application](../.github/workflows/switch2kit-windows.yml) | `Dolphin-Switch2Kit-windows-x86_64` |

GitHub artifact downloads require sign-in and expire. Extract the outer artifact ZIP and
then the application ZIP or tarball inside it. Source and diagnostics archives are not
applications. Check the build and launch results for that exact revision; these development
artifacts are not published production releases or evidence of hardware qualification.

### macOS

Use macOS 15+ and the artifact matching Apple Silicon (`arm64`) or Intel (`x86_64`). Move
`DolphinQt.app` to Applications and open it. Enable Bluetooth and allow Dolphin under
**System Settings > Privacy & Security > Bluetooth**. The app embeds its controller library
and Swift runtime. Ad-hoc signing is not notarization: use Apple's
[per-app approval procedure](https://support.apple.com/en-us/102445) only for an app you
trust, rather than disabling Gatekeeper globally.

### Linux

The development target is Ubuntu 24.04 x86-64 with a graphical desktop, graphics/audio
drivers, a powered Bluetooth LE adapter, BlueZ and normal system-bus/GATT access. Install
the distribution runtimes:

```sh
sudo apt-get install bluez libsystemd0 libqt6widgets6t64 libqt6svg6 qt6-qpa-plugins \
  libevdev2 libudev1 libusb-1.0-0 libasound2t64 libpulse0 libgl1 libegl1
tar -xzf Dolphin-Switch2Kit-linux-x86_64.tar.gz
./Dolphin-Switch2Kit-linux-x86_64/bin/dolphin-emu
```

Keep `bin/Sys`, `lib` and `share/Switch2KitNotices` with the executable. Swift runtime
libraries are packaged; system libraries and drivers are not. This is an installed
directory, not a universal AppImage. No Swift installation or `LD_LIBRARY_PATH` override
is needed to launch it. `bluetoothctl show` can check adapter power. The backend does not
power adapters, erase bonds or invoke BlueZ Pair/RemoveDevice. Resolve access errors using
the distribution's normal Bluetooth policy, not by running Dolphin as root.

### Windows

The experimental target is Windows 11 x64 with Bluetooth LE and graphics drivers, plus
the [Microsoft Visual C++ x64 runtime](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist)
when required. Open the extracted directory's `Dolphin.exe`. Keep all DLLs, Qt plugins,
`Sys` and `Switch2KitNotices` together. The selected Swift runtime is included; launching
does not require Swift or a compiler-specific PATH. ARM64 and 32-bit Windows are not covered.

Enable Bluetooth in **Settings > Bluetooth & devices** and use Find/Sync. Honor legitimate
system access prompts. Run as a normal user; do not disable SmartScreen, antivirus or
Bluetooth security to bypass an error. A missing DLL before the window appears is a
packaging/prerequisite problem, not a pairing failure. Re-extract the complete artifact and
check its launch results. Windows Server CI does not establish physical Windows 11 pairing.

## Build from source

Start from a checkout containing this integration and follow the ordinary Dolphin build
prerequisites in [Readme.md](../Readme.md). Initialize the recorded dependencies:

```sh
git submodule update --init --recursive
```

Keep the pinned Switch2Kit revision; do not apply the SDK's separate Dolphin patch scripts.
Disabled builds do not require Swift or raise the platform deployment target. Enabled builds
require SDL3, Qt and the platform toolchain below.

**macOS:** use Xcode 26+ with Swift 6.2+, finish Xcode setup and select its Command Line Tools.
On Apple Silicon, use a native Terminal and Homebrew rather than Rosetta.

```sh
brew install cmake ninja nasm automake libtool qt@6
cmake -S . -B build-switch2kit -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_OSX_DEPLOYMENT_TARGET=15.0 -DCMAKE_OSX_ARCHITECTURES="$(uname -m)" \
  -DENABLE_SWITCH2KIT=ON -DENABLE_SDL=ON -DENABLE_QT=ON \
  -DUSE_SYSTEM_SDL3=OFF -DCMAKE_PREFIX_PATH="$(brew --prefix qt@6)" \
  -DENABLE_VULKAN=OFF -DENABLE_TESTS=OFF -DPOSTPROCESS_BUNDLE=ON
cmake --build build-switch2kit --target dolphin-emu --parallel 3
open build-switch2kit/Binaries/DolphinQt.app
```

**Linux:** install Swift 6.2.1 using the [official instructions](https://www.swift.org/install/linux/),
then the Ubuntu application job's build dependencies:

```sh
sudo apt-get install build-essential cmake ninja-build python3 pkg-config \
  qt6-base-dev qt6-base-private-dev qt6-svg-dev libbluetooth-dev libevdev-dev \
  libudev-dev libusb-1.0-0-dev libasound2-dev libpulse-dev libx11-dev libxi-dev \
  libxrandr-dev libegl1-mesa-dev libgl1-mesa-dev libsystemd0 dbus
bash Tools/build-switch2kit-linux.sh --run
```

The helper installs and opens `build-switch2kit/install/bin/dolphin-emu`. Keep the complete
install prefix. The workflow's Xvfb/window-manager tools are only needed for CI GUI tests.

**Windows:** install Visual Studio 2026 Desktop development with C++, Windows SDK 10.0.22621
or newer, Git, CMake, Ninja, Python 3, PowerShell 7 and native x64 Swift 6.3.3 using
[Swift's instructions](https://www.swift.org/install/windows/). In 64-bit PowerShell, run:

```powershell
./Tools/build-switch2kit-windows.ps1 -Run
```

The helper selects compatible Visual Studio and Swift installations, builds the controller
library and Dolphin, and opens `build-switch2kit-windows/Binaries/Dolphin.exe`. Swift 6.2's
compiler is incompatible with VS 2026 STL headers. A standalone clang on PATH does not
replace Swift's compiler; do not bypass either project's compiler checks.

To update, quit Dolphin, run `git pull --ff-only` and `git submodule update --init --recursive`,
then repeat the build command. Do not erase Dolphin's user configuration.

## Qualification and troubleshooting

A missing **Switch 2 Controllers** section means the binary lacks this backend. For a
controller absent after a search, check adapter power/access, Sync mode, competing
connections and the displayed status, then retry Find. Installing a dashboard or replacing
system SDL is not a remedy.

See [testing and CI](Switch2KitCI.md) for the upstream unit-test baseline, focused CTest
commands, automatic change selection and compiler caching. Selected native workflows
check full builds and extracted-package launch using private test settings.
They do not establish pristine first-use dialogs, downloaded-app approval, Bluetooth
hardware or gameplay. Mapping and host regressions cover cancellation, backup/rollback,
identity, saved consent, explicit stop and shutdown ordering; keep those checks when
changing the integration.

Record hardware acceptance for each controller model, firmware, OS, adapter and commit:
first pairing and denied-access retry; every press/release, stick and trigger; rumble and
stop; two identical controllers reconnecting in reverse order; saved assignments after
restart; Bluetooth loss/recovery; explicit Disconnect remaining stopped; normal quit; and
gameplay. For automatic connection, leave a controller off longer than 60 seconds and
reconnect without opening settings, then disable automatic discovery with a controller
still connected. A passing build or launch check does not complete this checklist.
