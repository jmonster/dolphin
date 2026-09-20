# Native Switch 2 controllers in Dolphin

**This maintained Dolphin fork embeds [Switch2Kit](https://github.com/jmonster/Switch2Kit) for NSO GameCube and Nintendo Switch 2 Pro controllers on macOS 15+, with experimental Linux x86-64 and Windows x64 support.**

Start with the [download, extraction and launch instructions](../Readme.md#quick-start), then [connect and select a port](#playing-a-gamecube-game) below. Ordinary upstream Dolphin binaries do not contain this integration. Installing the library alone does not modify other applications. No separate dashboard, network bridge, system-wide SDL override, virtual-controller driver or Accessibility permission is required.

## Applications and prerequisites

Use this fork's successful **Native Switch2Kit** (macOS), **Switch2Kit Linux application** or **Switch2Kit Windows application** workflow on the implementation branch, not a source/diagnostics archive. GitHub artifact downloads require sign-in and expire (desktop application artifacts are retained for 14 days). An outer artifact ZIP contains the application ZIP or tarball. A configured job or earlier-revision pass is not proof that a particular download passed. These are development builds, not a published production release or a hardware-qualification claim.

### macOS

Use macOS 15 or newer on Apple Silicon (`arm64`) or Intel (`x86_64`). Download the matching **Dolphin-Switch2Kit-arm64** or **Dolphin-Switch2Kit-x86_64** artifact from [Native Switch2Kit](https://github.com/jmonster/dolphin/actions/workflows/native-switch2kit.yml), extract both ZIP layers, move `DolphinQt.app` to Applications and open it normally. The app embeds its controller library and Swift runtime. Enable Bluetooth and permit Dolphin under **System Settings > Privacy & Security > Bluetooth** when requested. Ad-hoc signing is not notarization; use Apple's [per-app approval procedure](https://support.apple.com/en-us/102445) only for an application you trust. Do not turn off Gatekeeper globally.

### Linux

The development target is Ubuntu 24.04 x86-64 with a graphical desktop and working graphics/audio drivers. Other distributions and architectures have not been qualified by these application jobs. The package is an installed directory, not a universal AppImage. Install the normal distribution runtimes; on Ubuntu 24.04:

```sh
sudo apt-get update
sudo apt-get install bluez libsystemd0 libqt6widgets6t64 libqt6svg6 qt6-qpa-plugins   libevdev2 libudev1 libusb-1.0-0 libasound2t64 libpulse0 libgl1 libegl1
```

Use the **Dolphin-Switch2Kit-linux-x86_64** application artifact from [the Linux workflow](https://github.com/jmonster/dolphin/actions/workflows/switch2kit-linux.yml). Extract the outer ZIP, then:

```sh
tar -xzf Dolphin-Switch2Kit-linux-x86_64.tar.gz
./Dolphin-Switch2Kit-linux-x86_64/bin/dolphin-emu
```

Keep `bin/Sys`, `lib` and `share/Switch2KitNotices` with the executable when relocating the directory. Swift runtime libraries are packaged; installing Swift or changing `LD_LIBRARY_PATH` is not a launch prerequisite. System libraries and graphics drivers are not bundled.

Turn Bluetooth on in your desktop's Bluetooth settings. BlueZ must be running, the adapter must support Bluetooth LE, and your normal account must have system-bus/GATT access. `bluetoothctl show` can confirm the powered adapter. Dolphin does not change adapter power, install permissive D-Bus rules, erase bonds or invoke BlueZ Pair/RemoveDevice. Start discovery in Dolphin and hold Sync; the controller-protocol handshake is separate from OS pairing. Resolve access failures through your distribution's normal Bluetooth policy, not by running the emulator as root.

### Windows

The experimental desktop target is Windows 11 x64, with a Bluetooth LE adapter/driver and graphics drivers. Native build/consumer jobs use Windows Server runners and are not evidence of physical Windows 11 pairing. ARM64 and 32-bit Windows are not covered. Install the [Microsoft Visual C++ x64 runtime](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist) when required by Windows or the application.

Download **Dolphin-Switch2Kit-windows-x86_64** from [the Windows application workflow](https://github.com/jmonster/dolphin/actions/workflows/switch2kit-windows.yml). Extract the outer ZIP and its inner `Dolphin-Switch2Kit-windows-x86_64.zip`. Open `Dolphin-Switch2Kit-windows-x86_64/Dolphin.exe`. Retain all DLLs, Qt plugins, `Sys` and `Switch2KitNotices`. The package stages the selected Swift runtime as well as `Switch2KitC.dll`; no Swift compiler installation or compiler-specific PATH is required to launch it.

Enable **Settings > Bluetooth & devices > Bluetooth**, close competing controller applications, then use Dolphin's Find/Sync procedure below. Honor any legitimate system pairing/access prompt. The backend does not silently change pairing policy or erase device bonds. Run as a normal user. Do not disable SmartScreen, antivirus or Bluetooth security to bypass an error. A missing DLL before a window appears is a package/runtime prerequisite problem, not a pairing failure: re-extract the complete controller-enabled artifact and check that revision's native launch job.

## Playing a GameCube game

Use a Dolphin application built with this option (not an ordinary upstream build).
Close other applications that are managing the same controller. In Dolphin's
Controller Settings, find the **Switch 2 Controllers** section above **Common**.
Click **Find Controllers**, allow Bluetooth access, and hold Sync on the wireless
controller. Discovery lasts 60 seconds.

Choose the connected **Switch2Kit GameCube** or **Switch2Kit Pro Controller 2**
in the physical-controller dropdown beside the desired GameCube port. This selects
**Standard Controller**, applies the correct button/stick/trigger preset and binds
**Motor** for rumble. No manual profile selection is needed. Each physical controller
can be assigned to only one active Standard Controller port through this shortcut;
set its old port to None before moving it. Other controller types and backends
continue to use Configure normally.

Pairing stays separate from the emulated controller type: **Standard Controller**
is what the game sees, while the adjacent dropdown selects the physical input
device. Changing the type does not start Bluetooth discovery.

In **Configure**, **Use Recommended Mapping** applies the same mapping to the
selected supported device. It is explicit: selecting a device, refreshing the list,
or reconnecting a controller does not overwrite bindings. Replacing custom buttons,
calibration, or other settings requires confirmation (Cancel is the default) and
creates a uniquely named **Before Switch2Kit Port …** profile. Use Profile → Load
to restore it. A missing preset or failed backup leaves the current mapping intact.

The GameCube preset preserves independent analog L/R travel and digital full
clicks. The Pro preset matches printed Nintendo A/B/X/Y labels; + is Start, R is
GameCube Z, and ZL/ZR provide on/off GameCube L/R. Pro triggers cannot produce
GameCube-style variable squeeze.

Open the game normally. Port bindings use Dolphin's existing settings.
This is not wired GameCube USB-adapter mode.

### Automatic connection and recovery

Enable **Automatically connect** in the **Switch 2 Controllers** section.
This starts listening now and saves your choice for future Dolphin launches. After
initial pairing, turn the controller on again after a long pause: Dolphin can
rediscover it without reopening settings or pressing Find. Discovery runs on the
SDK's Bluetooth queue, independently of emulation pause and the settings window.
There is no repeating Find timer or 60-second limit in automatic mode.

The option is off by default. With it off, Find still searches for 60 seconds,
and merely launching Dolphin does not start Bluetooth or request permission.
With it on, Dolphin starts once on the main run loop after SDL initialization.
The status distinguishes continuous listening from a finite manual search.

**Disconnect All** in that section stops input and discovery for the current
session, even with this option checked. Polling, returning to the app, resuming a
game or reopening settings cannot undo that explicit stop. Use Find or re-enable
the option to resume; the saved option still applies on the next app launch.
Unchecking the option stops automatic discovery without disconnecting ready
controllers. A connection handshake already admitted may finish.

Automatic discovery connects available **supported** controllers, not arbitrary
Bluetooth devices and not only a saved allowlist. Close competing controller apps.
It does not overwrite custom mappings or assign a new controller to a game port.
The transport retains its capacity limits, serialized handshakes, duplicate-filtered
scans and bounded retry behavior; continuous listening still uses Bluetooth radio
resources. It cannot wake a powered-off controller or bypass initial pairing or
Bluetooth permission.

The choice is stored as `[Settings] AutoConnect` in `Switch2Kit.ini`, alongside
but separate from physical identities. Failed reads/saves do not overwrite existing
settings or change the runtime choice. A saved choice whose start failed remains
visible; use Find to retry after resolving the reported problem.

The controller's physical identity is assigned a persistent Dolphin device number
in `Switch2Kit.ini` in Dolphin's user configuration directory. Reconnecting two
identical controllers in reverse order does not change their intended saved
assignments. An unreadable/unwritable configuration or exhaustion of the 64 saved
slots falls back to Dolphin's ordinary device numbering; in that case verify the
selected device. No controller identifiers are written to diagnostic messages.

## Controller differences and motion

The quick port selector supports GameCube and Pro controllers. Discover each Joy-Con 2 half using Find/Sync, then use the ordinary per-port **Configure** window and SDL device selection to assign that half's buttons and axes manually. This fork does not automatically combine the halves into one controller or create a system-wide virtual pair.

For Wii games, choose **Emulated Wii Remote** and configure its ordinary inputs separately. The GameCube-port shortcut is not Wii motion setup. This maintained fork does not supply the SDK's separate pinned-upstream Dolphin patch's calibrated-motion setup UI. Do not assume that selecting a controller or a test calibration file gives usable Wii motion. Cemu has its own explicit measured-motion workflow; that is a different integration.

NSO GameCube rumble uses the dedicated Bluetooth on/off motor channel, not HD waveforms or short firmware feedback clips. Pro/Joy-Con retain their HD-rumble path. Zero, disconnect and teardown stop output; stale requests cannot restart retired sessions. Check actual motor behavior on your hardware rather than treating an automated callback test as a physical result.

## Build from source

The optional backend is OFF by default; disabled builds do not require Swift or raise the platform deployment target. Enabled builds need SDL3, Qt and the platform toolchain below. Use the maintained fork's selected submodules, not the SDK's separate upstream patch scripts. While this PR is unmerged:

```sh
git clone --branch feature/switch2kit-desktop-platforms --recurse-submodules https://github.com/jmonster/dolphin.git dolphin-switch2kit
cd dolphin-switch2kit
```

**macOS:** install Xcode 26+ with Swift 6.2+, open Xcode to finish setup and select its Command Line Tools. Then:

```sh
brew install cmake ninja nasm automake libtool qt@6
cmake -S . -B build-switch2kit -G Ninja -DCMAKE_BUILD_TYPE=Release   -DCMAKE_OSX_DEPLOYMENT_TARGET=15.0 -DCMAKE_OSX_ARCHITECTURES="$(uname -m)"   -DENABLE_SWITCH2KIT=ON -DENABLE_SDL=ON -DENABLE_QT=ON   -DUSE_SYSTEM_SDL3=OFF -DENABLE_VULKAN=OFF -DENABLE_TESTS=OFF   -DCMAKE_PREFIX_PATH="$(brew --prefix qt@6)" -DPOSTPROCESS_BUNDLE=ON
cmake --build build-switch2kit --target dolphin-emu --parallel 3
open build-switch2kit/Binaries/DolphinQt.app
```

**Linux:** install Swift **6.2.1** using the [official Linux installation instructions](https://www.swift.org/install/linux/), then the build dependencies used by the Ubuntu application job:

```sh
sudo apt-get install build-essential cmake ninja-build python3 pkg-config   qt6-base-dev qt6-base-private-dev qt6-svg-dev libbluetooth-dev libevdev-dev   libudev-dev libusb-1.0-0-dev libasound2-dev libpulse-dev libx11-dev libxi-dev   libxrandr-dev libegl1-mesa-dev libgl1-mesa-dev libsystemd0 dbus
bash Tools/build-switch2kit-linux.sh --run
```

The helper builds, installs and opens `build-switch2kit/install/bin/dolphin-emu`. Keep the whole install prefix for later launches. `openbox`, `wmctrl`, `x11-utils`, `xvfb` and `xauth` are CI GUI-test dependencies, not a requirement for an ordinary desktop user.

**Windows:** install Visual Studio **2026 Desktop development with C++**, Windows SDK 10.0.22621 or newer, Git, CMake, Ninja, Python 3, PowerShell 7 and native x64 Swift **6.3.3** following [Swift's Windows instructions](https://www.swift.org/install/windows/). Open 64-bit PowerShell in the checkout:

```powershell
./Tools/build-switch2kit-windows.ps1 -Run
```

The helper selects VS 2026 and one compatible Swift installation, builds the native controller library and complete Dolphin target, then opens `build-switch2kit-windows/Binaries/Dolphin.exe`. Swift 6.2's compiler is incompatible with VS 2026 STL headers; a different standalone clang on PATH does not replace Swift's compiler. Do not bypass Dolphin's compiler guard or Microsoft's STL checks. Build-time runtime PATH setup is process-local; extracted packages are tested without it.

To update a source build, quit Dolphin, use `git pull --ff-only`, update the recorded submodules with `git submodule update --init --recursive`, and rerun the same build command. Do not erase your Dolphin user configuration.

## Qualification and troubleshooting

A missing **Switch 2 Controllers** section means the launched binary was built without this backend. A controller absent after a 60-second search warrants checking adapter power/access, Sync mode, competing connections and the reported status; retry Find after resolving the cause. Do not reinstall a dashboard or a system SDL override. A changed adapter or device address can change Linux/Windows physical identity: verify the selected player port instead of relying on a displayed ordinal.

The native workflows build real applications. Desktop launch qualification extracts the exact uploaded archive into a new directory, uses private test profiles, verifies the loaded controller/Swift libraries come from that package, opens a GUI, requests normal quit, and relaunches. It deliberately seeds noninteractive test settings; it does not establish pristine first-use dialogs, downloaded-app approval, Bluetooth hardware or gameplay. A run is qualified only after those checks pass for its exact head. The executable runtime-wiring regression also checks missing-runtime failure, deployment-error propagation, optional-backend isolation and relocatable resources; fixture DLLs are not substituted into the application artifact.

Retained mapping/host regressions exercise real mapping and host code against controlled UI/storage boundaries, including cancellation, backup/rollback, stable identity, saved consent, explicit stop and shutdown ordering. Protocol, rumble, calibration, bounded queues, permissions, signing and license coverage remain in the SDK/fork suites. No prose-length, heading-order or branding assertion is needed to protect these behaviors.

Record hardware acceptance separately for each model/firmware/OS/adapter and tested commit: first pairing and denied-access retry; every press/release and stick; independent GameCube analog travel and digital clicks; correct rumble and stop; two identical controllers returning in reverse order; saved assignments after app restart; Bluetooth loss/recovery; explicit Disconnect remaining stopped; normal quit; and gameplay. For Dolphin's automatic mode, power a controller off for longer than 60 seconds and reconnect without opening settings, then test disabling automatic discovery without dropping a live controller. These changes do not claim that checklist has been physically completed.
