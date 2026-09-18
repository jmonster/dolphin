# Dolphin - A GameCube and Wii Emulator

**This fork supports the Nintendo Switch Online GameCube controller and Nintendo Switch 2 Pro Controller on macOS through [Switch2Kit](https://github.com/jmonster/Switch2Kit).**

Controller support is built into Dolphin. There is no separate Switch2Kit app or controller driver to install, and GameCube/Pro controller setup includes recommended mappings and rumble.

## Quick start (macOS 15+)

### Get a controller-enabled build

1. Sign in to GitHub, open this fork's [Native Switch2Kit builds](https://github.com/jmonster/dolphin/actions/workflows/native-switch2kit.yml), and select a successful run with a green check.
2. Under **Artifacts**, download **Dolphin-Switch2Kit-arm64** for an Apple Silicon Mac or **Dolphin-Switch2Kit-x86_64** for an Intel Mac. Choose the application artifact, not a diagnostics or SDK-test artifact.
3. Extract the downloaded ZIP, then extract the **Dolphin-Switch2Kit-arm64.zip** or **Dolphin-Switch2Kit-x86_64.zip** inside it. Move **DolphinQt.app** to Applications and open it. Reopen this same app for later sessions.

Downloads currently come from GitHub Actions, not a published release. Artifacts expire; when no application download is available, use [Build from source](#build-from-source-alternative) below. Ordinary upstream Dolphin downloads do not include this Switch2Kit integration.

These are development builds, not notarized releases. For an unverified-developer warning, use Apple's [per-app Open Anyway instructions](https://support.apple.com/en-us/102445) only when you trust the download's source. Do not disable Gatekeeper globally.

### Connect and play

1. Turn on your Mac's Bluetooth and close other apps managing the controller, including the Switch2Kit dashboard or Cemu. In Dolphin, open **Controllers** (Controller Settings), click **Find Switch 2 Controllers**, allow Bluetooth access, and hold the controller's **Sync** button until its player lights sweep. The search lasts 60 seconds; click Find again to retry.
2. Beside the desired **GameCube port**, choose **Switch2Kit GameCube** or **Switch2Kit Pro Controller 2** in the physical-controller dropdown. Dolphin selects **Standard Controller** and applies the button, stick, trigger, and rumble mappings automatically. This is not **GameCube Adapter for Wii U** mode.
3. Open that port's **Configure** window to check button presses and releases, sticks, and triggers, then open your GameCube game. On the NSO GameCube controller, partial L/R travel and the full-click buttons are separate inputs. Pro Controller ZL/ZR are on/off and cannot reproduce an analog squeeze.

For automatic reconnection on later launches or after a long pause, enable **Automatically connect Switch 2 controllers** in Controller Settings and turn the controller on when you return. This option is off by default; otherwise use **Find Switch 2 Controllers** each session. **Disconnect Switch 2 Controllers** stops the current session without deleting mappings.

For Wii games, configure an **Emulated Wii Remote** and its SDL device through Dolphin's normal Wii Remote settings; the GameCube-port shortcut above does not configure a Wii Remote or add calibrated Wii motion. Individual Joy-Con 2 halves also need normal manual bindings.

**No Find button?** Open the controller-enabled app above, not an upstream or backend-disabled build. **No controller?** Check Bluetooth access for Dolphin in **System Settings > Privacy & Security > Bluetooth**, close competing controller apps, and retry Find while holding Sync. Saved custom mappings are not replaced on reconnect; **Use Recommended Mapping** in Configure is the explicit reset-to-preset action.

### Build from source (alternative)

<details>
<summary>Build and launch the controller-enabled app on your Mac</summary>

Use macOS 15+, [Xcode](https://developer.apple.com/xcode/) 26+ with Swift 6.2+, and [Homebrew](https://brew.sh/). Open Xcode once to finish setup and select it under **Xcode > Settings > Locations > Command Line Tools**. On Apple Silicon, use a native Terminal and native Homebrew, not Rosetta.

Run these commands in Terminal:

```sh
brew install cmake ninja nasm automake libtool qt@6
git clone --recurse-submodules https://github.com/jmonster/dolphin.git dolphin-switch2kit
cd dolphin-switch2kit
cmake -S . -B build-switch2kit -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_OSX_DEPLOYMENT_TARGET=15.0 \
  -DCMAKE_OSX_ARCHITECTURES="$(uname -m)" \
  -DENABLE_SWITCH2KIT=ON -DENABLE_SDL=ON -DENABLE_QT=ON \
  -DUSE_SYSTEM_SDL3=OFF \
  -DCMAKE_PREFIX_PATH="$(brew --prefix qt@6)" \
  -DENABLE_VULKAN=OFF -DENABLE_TESTS=OFF -DPOSTPROCESS_BUNDLE=ON
cmake --build build-switch2kit --target dolphin-emu --parallel 3
open build-switch2kit/Binaries/DolphinQt.app
```

This follows the native workflow's build options, including using OpenGL rather than Vulkan. The clone includes the pinned Switch2Kit dependency; do not apply the SDK's separate emulator patches to this fork. The resulting app is **build-switch2kit/Binaries/DolphinQt.app**. Once it opens, follow [Connect and play](#connect-and-play).

For later launches, reopen that app. The usual upstream build instructions below leave `ENABLE_SWITCH2KIT` off unless you explicitly enable it.

</details>

See the [full Switch2Kit controller guide](Docs/Switch2Kit.md) for custom mappings, profile backups, multiplayer, rumble, reconnection, and testing limits. Automated build/launch checks do not establish physical-controller or gameplay acceptance. Switch2Kit support in this fork is macOS-only; the SDK's experimental Linux work is separate.

## Upstream Dolphin documentation

The information below describes Dolphin generally, including builds without this fork's Switch2Kit feature. Controller-enabled builds have the macOS 15+ requirements above.

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
