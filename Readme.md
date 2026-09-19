# Dolphin - A GameCube and Wii Emulator

**This fork embeds [Switch2Kit](https://github.com/jmonster/Switch2Kit) for NSO GameCube and Nintendo Switch 2 Pro controllers on macOS 15+, with experimental Linux x86-64 and Windows x64 builds.**

Get this controller-enabled Dolphin, connect your controller, select a GameCube port, and play. No separate Switch2Kit dashboard, network bridge, SDL override or virtual-controller driver is needed. Individual Joy-Con 2 halves remain available through manual bindings.

## Quick start

Use the application artifacts below from **this fork**, not upstream Dolphin binaries. Sign in to GitHub, select a successful run for `feature/switch2kit-desktop-platforms` while this PR is unmerged, and download the named application artifact. Open the run's jobs to check the build and launch results for that revision. Source and diagnostics archives are not applications. These are expiring development artifacts, not published, notarized or production-signed releases; use [Build from source](#build-from-source-alternative) when no matching artifact is available.

### macOS

On macOS 15 or newer, use [Native Switch2Kit builds](https://github.com/jmonster/dolphin/actions/workflows/native-switch2kit.yml): **Dolphin-Switch2Kit-arm64** for Apple Silicon, or **Dolphin-Switch2Kit-x86_64** for Intel. Extract the downloaded artifact ZIP, then the `Dolphin-Switch2Kit-<architecture>.zip` inside it. Move `DolphinQt.app` to Applications and open it. Enable Bluetooth and allow Dolphin's Bluetooth request. A denied permission can be changed under **System Settings > Privacy & Security > Bluetooth**.

The development app is ad-hoc signed, not notarized. Use Apple's [per-app Open Anyway procedure](https://support.apple.com/en-us/102445) only for a source you trust; do not disable Gatekeeper globally.

### Linux

Use Ubuntu 24.04 x86-64 with a desktop session, graphics drivers, a powered Bluetooth LE adapter, the running BlueZ service and normal system-bus access. Install the distribution runtime prerequisites listed in the [Linux guide](Docs/Switch2Kit.md#linux). Use [Switch2Kit Linux application builds](https://github.com/jmonster/dolphin/actions/workflows/switch2kit-linux.yml), artifact **Dolphin-Switch2Kit-linux-x86_64**. Extract the outer download ZIP, then run:

```sh
tar -xzf Dolphin-Switch2Kit-linux-x86_64.tar.gz
./Dolphin-Switch2Kit-linux-x86_64/bin/dolphin-emu
```

Keep the whole extracted directory, including `bin/Sys`, `lib` and `share/Switch2KitNotices`. The packaged Swift runtime does not require a Swift installation or `LD_LIBRARY_PATH` override. This is not a universal Linux/AppImage package; system desktop libraries and drivers are still required.

### Windows

Use Windows 11 x64 for the experimental desktop instructions, with Bluetooth LE enabled, its adapter driver, graphics drivers and the Microsoft Visual C++ x64 runtime. Native CI uses Windows Server runners; physical Windows 11 controller acceptance is not claimed. Use [Switch2Kit Windows application builds](https://github.com/jmonster/dolphin/actions/workflows/switch2kit-windows.yml), artifact **Dolphin-Switch2Kit-windows-x86_64**. Extract the outer artifact ZIP, then `Dolphin-Switch2Kit-windows-x86_64.zip` inside it. Open `Dolphin-Switch2Kit-windows-x86_64/Dolphin.exe`.

Keep its DLLs, `Sys`, Qt plugins and `Switch2KitNotices` together. The package includes the selected Swift runtime; do not install Swift or add a compiler directory to PATH merely to launch it. Do not run Dolphin as administrator or disable SmartScreen/antivirus to bypass a failure. See the [Windows guide](Docs/Switch2Kit.md#windows) for prerequisites and the source fallback.

### Connect and play

1. Close other apps or consoles managing this controller. In Dolphin, open **Controllers**, click **Find Switch 2 Controllers**, and hold the controller's **Sync** button until its player lights sweep. Allow any legitimate Bluetooth access prompt. Discovery lasts 60 seconds; click Find again to retry. Bluetooth Settings power/access and Dolphin's discovery are separate; no global permission or pairing bypass is required.
2. Beside the desired **GameCube port**, select the physical **Switch2Kit GameCube** or **Switch2Kit Pro Controller 2**. Dolphin selects **Standard Controller** and applies recommended controls and rumble. Do not select **GameCube Adapter for Wii U** mode for these wireless controllers.
3. Open that port's **Configure** window. Verify presses/releases, sticks, D-pad, rumble and triggers, then open your GameCube game. NSO GameCube L/R analog travel and full clicks are independent; Pro ZL/ZR are digital and cannot reproduce an analog squeeze.

Reopen the same extracted application on later launches. Saved physical assignments and custom mappings persist. Enable **Automatically connect Switch 2 controllers** for Dolphin's opt-in reconnection policy; it is off by default, so otherwise use Find again. **Disconnect Switch 2 Controllers** stops the backend without deleting mappings. Explicit **Use Recommended Mapping** and slot replacement preserve the existing confirmation/backup behavior; discovery does not silently replace custom bindings.

For Wii games, configure an **Emulated Wii Remote** and its SDL input normally; the GameCube-port shortcut does not configure Wii motion. Discover each Joy-Con 2 half with Find/Sync and map each desired device manually. Do not assume a paired virtual controller or calibrated motion is created automatically. The [controller guide](Docs/Switch2Kit.md#controller-differences-and-motion) explains these distinctions.

### Build from source (alternative)

The [build guide](Docs/Switch2Kit.md#build-from-source) contains complete platform prerequisites and commands. Clone the implementation branch while the PR is unmerged:

```sh
git clone --branch feature/switch2kit-desktop-platforms --recurse-submodules https://github.com/jmonster/dolphin.git dolphin-switch2kit
cd dolphin-switch2kit
```

Do not apply the SDK's separate pinned-upstream patches to this maintained fork. Ordinary upstream-style builds below leave Switch2Kit disabled unless requested. Linux and Windows remain experimental; automated build/launch checks do not establish physical pairing, rumble, reconnect or gameplay acceptance.

## Upstream Dolphin documentation

The information below describes Dolphin generally, including builds without this fork's Switch2Kit feature. Controller-enabled builds use the platform requirements above.

[Homepage](https://dolphin-emu.org/) | [Project Site](https://github.com/dolphin-emu/dolphin) | [Buildbot](https://dolphin.ci/) | [Forums](https://forums.dolphin-emu.org/) | [Wiki](https://wiki.dolphin-emu.org/) | [GitHub Wiki](https://github.com/dolphin-emu/dolphin/wiki) | [Issue Tracker](https://bugs.dolphin-emu.org/projects/emulator/issues) | [Coding Style](https://github.com/dolphin-emu/dolphin/blob/master/Contributing.md) | [Transifex Page](https://app.transifex.com/dolphinemu/dolphin-emu/dashboard/) | [Analytics](https://mon.dolphin-emu.org/)

Dolphin is an emulator for running GameCube and Wii games on Windows,
Linux, macOS, and recent Android devices. It's licensed under the terms
of the GNU General Public License, version 2 or later (GPLv2+).

Please read the [FAQ](https://dolphin-emu.org/docs/faq/) before using Dolphin.

## System Requirements

### Desktop

* OS
    * Windows (10 1903 or higher).
    * Linux.
    * macOS (11.0 Big Sur or higher).
    * Unix-like systems other than Linux are not officially supported but might work.
* Processor
    * A CPU with SSE2 support.
    * A modern CPU (3 GHz and Dual Core, not older than 2008) is highly recommended.
* Graphics
    * A reasonably modern graphics card (Direct3D 11.1 / OpenGL 3.3).
    * A graphics card that supports Direct3D 11.1 / OpenGL 4.4 is recommended.

### Android

* OS
    * Android (7.0 Nougat or higher).
* Processor
    * A processor with support for 64-bit applications (either ARMv8 or x86-64).
* Graphics
    * A graphics processor that supports OpenGL ES 3.0 or higher. Performance varies heavily with [driver quality](https://dolphin-emu.org/blog/2013/09/26/dolphin-emulator-and-opengl-drivers-hall-fameshame/).
    * A graphics processor that supports standard desktop OpenGL features is recommended for best performance.

Dolphin can only be installed on devices that satisfy the above requirements. Attempting to install on an unsupported device will fail and display an error message.

## Building

You may find building instructions on the appropriate wiki page for your operating system:

* [Windows](https://github.com/dolphin-emu/dolphin/wiki/Building-for-Windows)
* [Linux](https://github.com/dolphin-emu/dolphin/wiki/Building-for-Linux)
* [macOS](https://github.com/dolphin-emu/dolphin/wiki/Building-for-macOS)
* [Android](#android-specific-instructions) <!-- TODO: Create a "Building for Android" wiki page and link it here -->
* [OpenBSD](https://github.com/dolphin-emu/dolphin/wiki/Building-for-OpenBSD) (unsupported)

Before building, make sure to pull all submodules:

```sh
git submodule update --init --recursive
```

### Android-specific instructions

These instructions assume familiarity with Android development. If you do not have an
Android dev environment set up, see [AndroidSetup.md](AndroidSetup.md).

If using Android Studio, import the Gradle project located in `./Source/Android`.

Android apps are compiled using a build system called Gradle. Dolphin's native component,
however, is compiled using CMake. The Gradle script will attempt to run a CMake build
automatically while building the Java code.

## Uninstalling

On Windows, simply remove the extracted directory, unless it was installed with the NSIS installer,
in which case you can uninstall Dolphin like any other Windows application.

Linux users can run `cat install_manifest.txt | xargs -d '\n' rm` as root from the build directory
to uninstall Dolphin from their system.

macOS users can simply delete Dolphin.app to uninstall it.

Additionally, you'll want to remove the global user directory if you don't plan on reinstalling Dolphin.

## Command Line Usage

```
Usage: Dolphin.exe [options]... [FILE]...

Options:
  --version             show program's version number and exit
  -h, --help            show this help message and exit
  -u USER, --user=USER  User folder path
  -m MOVIE, --movie=MOVIE
                        Play a movie file
  -e <file>, --exec=<file>
                        Load the specified file
  -n <16-character ASCII title ID>, --nand_title=<16-character ASCII title ID>
                        Launch a NAND title
  -C <System>.<Section>.<Key>=<Value>, --config=<System>.<Section>.<Key>=<Value>
                        Set a configuration option
  -s <file>, --save_state=<file>
                        Load the initial save state
  -d, --debugger        Show the debugger pane and additional View menu options
  -l, --logger          Open the logger
  -b, --batch           Run Dolphin without the user interface (Requires
                        --exec or --nand-title)
  -c, --confirm         Set Confirm on Stop
  -v VIDEO_BACKEND, --video_backend=VIDEO_BACKEND
                        Specify a video backend
  -a AUDIO_EMULATION, --audio_emulation=AUDIO_EMULATION
                        Choose audio emulation from [HLE|LLE]
```

Available DSP emulation engines are HLE (High Level Emulation) and
LLE (Low Level Emulation). HLE is faster but less accurate whereas
LLE is slower but close to perfect. Note that LLE has two submodes (Interpreter and Recompiler)
but they cannot be selected from the command line.

Available video backends are "D3D" and "D3D12" (they are only available on Windows), "OGL", and "Vulkan".
There's also "Null", which will not render anything, and
"Software Renderer", which uses the CPU for rendering and
is intended for debugging purposes only.

## DolphinTool Usage
```
usage: dolphin-tool COMMAND -h

commands supported: [convert, verify, header, extract]
```

```
Usage: convert [options]... [FILE]...

Options:
  -h, --help            show this help message and exit
  -u USER, --user=USER  User folder path, required for temporary processing
                        files.Will be automatically created if this option is
                        not set.
  -i FILE, --input=FILE
                        Path to disc image FILE.
  -o FILE, --output=FILE
                        Path to the destination FILE.
  -f FORMAT, --format=FORMAT
                        Container format to use. Default is RVZ. [iso|gcz|wia|rvz]
  -s, --scrub           Scrub junk data as part of conversion.
  -b BLOCK_SIZE, --block_size=BLOCK_SIZE
                        Block size for GCZ/WIA/RVZ formats, as an integer.
                        Suggested value for RVZ: 131072 (128 KiB)
  -c COMPRESSION, --compression=COMPRESSION
                        Compression method to use when converting to WIA/RVZ.
                        Suggested value for RVZ: zstd [none|zstd|bzip|lzma|lzma2]
  -l COMPRESSION_LEVEL, --compression_level=COMPRESSION_LEVEL
                        Level of compression for the selected method. Ignored
                        if 'none'. Suggested value for zstd: 5
```

```
Usage: verify [options]...

Options:
  -h, --help            show this help message and exit
  -u USER, --user=USER  User folder path, required for temporary processing
                        files.Will be automatically created if this option is
                        not set.
  -i FILE, --input=FILE
                        Path to disc image FILE.
  -a ALGORITHM, --algorithm=ALGORITHM
                        Optional. Compute and print the digest using the
                        selected algorithm, then exit. [crc32|md5|sha1|rchash]
```

```
Usage: header [options]...

Options:
  -h, --help            show this help message and exit
  -i FILE, --input=FILE
                        Path to disc image FILE.
  -b, --block_size      Optional. Print the block size of GCZ/WIA/RVZ formats,
then exit.
  -c, --compression     Optional. Print the compression method of GCZ/WIA/RVZ
                        formats, then exit.
  -l, --compression_level
                        Optional. Print the level of compression for WIA/RVZ
                        formats, then exit.
```

```
Usage: extract [options]...

Options:
  -h, --help            show this help message and exit
  -i FILE, --input=FILE
                        Path to disc image FILE.
  -o FOLDER, --output=FOLDER
                        Path to the destination FOLDER.
  -p PARTITION, --partition=PARTITION
                        Which specific partition you want to extract.
  -s SINGLE, --single=SINGLE
                        Which specific file/directory you want to extract.
  -l, --list            List all files in volume/partition. Will print the
                        directory/file specified with --single if defined.
  -q, --quiet           Mute all messages except for errors.
  -g, --gameonly        Only extracts the DATA partition.
```
