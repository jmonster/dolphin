# Native Switch 2 controller input on macOS

This optional backend embeds [Switch2Kit](https://github.com/jmonster/Switch2Kit)
inside Dolphin. Bluetooth discovery and input belong to Dolphin; no standalone
dashboard, UDP server, SDL dynamic-library override, Accessibility permission, or
system virtual-HID device is used. The existing SDL3 backend receives
Switch2Kit's in-process virtual gamepads. No console emulation code is changed.

## Playing a GameCube game

Use a Dolphin application built with this option (not an ordinary upstream build).
Close other applications that are managing the same controller. In Dolphin's
Controller Settings, click **Find Switch 2 Controllers**, allow Bluetooth access,
and hold Sync on the wireless controller. Discovery lasts 60 seconds.

Choose **Standard Controller** for the desired GameCube port, open **Configure**,
load the bundled **Switch2Kit GameCube** profile, and select the SDL device named
**Switch2Kit GameCube**. This is not the wired **GameCube Adapter for Wii U** mode.
The preset maps the physical Nintendo face buttons, both sticks, Start, Z, and
D-pad; analog L/R travel and digital full clicks are separate bindings. Load the
game normally. Your port bindings are saved using Dolphin's existing settings.
Use Find again after restarting Dolphin; support does not scan or request
Bluetooth permission merely because the application was launched.

The controller's physical identity is assigned a persistent Dolphin device number
in `Switch2Kit.ini` in Dolphin's user configuration directory. Reconnecting two
identical controllers in reverse order does not change their intended saved
assignments. An unreadable/unwritable configuration or exhaustion of the 64 saved
slots falls back to Dolphin's ordinary device numbering; in that case verify the
selected device. No controller identifiers are written to diagnostic messages.

## Building

The backend is OFF by default. Disabled builds do not require Swift and retain
Dolphin's existing macOS deployment target and other platforms. Enabled builds
require macOS 15+, Xcode 26+ with Swift 6.2+, and Dolphin's normal build dependencies.
The submodule pins Switch2Kit to `00c383f4773b5e712c8f673c33791b810297ed2c`.

```sh
git submodule update --init --recursive
cmake -S . -B build-switch2kit -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_OSX_DEPLOYMENT_TARGET=15.0 \
  -DENABLE_SWITCH2KIT=ON -DENABLE_SDL=ON -DENABLE_QT=ON \
  -DCMAKE_PREFIX_PATH="$(brew --prefix qt@6)" \
  -DPOSTPROCESS_BUNDLE=ON
cmake --build build-switch2kit --target dolphin-emu --parallel 3
```

Select `CMAKE_OSX_ARCHITECTURES` as usual; the library integration builds matching
slices. Its C facade and required Swift runtime libraries are copied into the
application before Dolphin's ordinary relocation and signing steps. No signing
identity, entitlement, Gatekeeper setting, or notarization claim is added.
The **Native Switch2Kit** workflow builds separate arm64/x86_64 application ZIPs
for this fork. A workflow artifact is a development build, not a notarized release.

## Scope and validation

Pro Controller 2 and individual Joy-Con 2 halves use the same engine but need
appropriate Dolphin bindings. This change does not pair Joy-Con halves or add Wii
motion integration. GameCube firmware rumble clips are not cancellable continuous
SDL effects, so the GameCube preset deliberately has no rumble binding. Pro/Joy-Con
continuous rumble uses the shared adapter and its live-input-loop renewal limit.

The adapter processes bounded batches and commits each SDL transition; Dolphin
still samples state at its existing cadence. This does not guarantee a game sees
a press/release shorter than that cadence. Device loss and overflow recovery are
handled by the shared adapter. On final shutdown its SDL devices are destroyed
before the C context and SDL; asynchronous Bluetooth teardown never blocks the
main run loop. The linked Swift library remains resident for process lifetime.

`python3 Tools/test_switch2kit.py` checks the preset and build/lifecycle wiring.
The native workflow compiles the complete application and inspects the embedded
library and Bluetooth description. These checks do not establish physical
controller behavior, clean-Mac startup, latency, or gameplay acceptance.

Before treating a build as ready to play, test a real NSO GameCube controller:
pair/permission refusal and retry; every button and axis; light L/R travel without
a click and independent full clicks; disconnect while holding input; reconnect;
two identical controllers; app restart; normal quit; and an actual game session.
Retain the distinction between build success and these hardware results.

This contribution was prepared with AI assistance. The build glue, host wrapper,
UI integration, profile, documentation and checks require human review. The
controller protocol/Swift engine is reused from the pinned Switch2Kit dependency.
