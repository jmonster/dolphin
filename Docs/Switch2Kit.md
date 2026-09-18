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

Choose the connected **Switch2Kit GameCube** or **Switch2Kit Pro Controller 2**
in the physical-controller dropdown beside the desired GameCube port. This selects
**Standard Controller**, applies the correct button/stick/trigger preset and binds
**Motor** for rumble. No manual profile selection is needed. Each physical controller
can be assigned to only one active Standard Controller port through this shortcut;
set its old port to None before moving it. Other controller types and backends
continue to use Configure normally.

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

Enable **Automatically connect Switch 2 controllers** in Controller Settings.
This starts listening now and saves your choice for future Dolphin launches. After
initial pairing, turn the controller on again after a long pause: Dolphin can
rediscover it without reopening settings or pressing Find. Discovery runs on the
SDK's Bluetooth queue, independently of emulation pause and the settings window.
There is no repeating Find timer or 60-second limit in automatic mode.

The option is off by default. With it off, Find still searches for 60 seconds,
and merely launching Dolphin does not start Bluetooth or request permission.
With it on, Dolphin starts once on the main run loop after SDL initialization.
The status distinguishes continuous listening from a finite manual search.

**Disconnect Switch 2 Controllers** stops input and discovery for the current
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

## Building

The backend is OFF by default. Disabled builds do not require Swift and retain
Dolphin's existing macOS deployment target and other platforms. Enabled builds
require macOS 15+, Xcode 26+ with Swift 6.2+, and Dolphin's normal build dependencies.
The submodule pins Switch2Kit to `a9d43b1f63d94f8844755a510bf6ecc876bc8c51`.

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

GameCube and Pro Controller 2 receive recommended mappings. Individual Joy-Con 2
halves still need appropriate Dolphin bindings; this does not pair the halves or
add Wii motion integration. GameCube rumble uses its dedicated Bluetooth **on/off
motor** channel, not HD-rumble waveforms or short firmware feedback clips. Pro/Joy-Con
HD rumble retains the existing adapter implementation. Both types use cancellable
outputs and the live-input-loop renewal limit. Zero stops the motor; stale requests,
disconnection, and teardown cannot queue a later restart.

The adapter processes bounded batches and commits each SDL transition; Dolphin
still samples state at its existing cadence. This does not guarantee a game sees
a press/release shorter than that cadence. Device loss and overflow recovery are
handled by the shared adapter. On final shutdown its SDL devices are destroyed
before the C context and SDL; asynchronous Bluetooth teardown never blocks the
main run loop. The linked Swift library remains resident for process lifetime.

`python3 Tools/test_switch2kit.py` checks presets and build/lifecycle wiring.
`python3 Tools/test_switch2kit_mapping.py --sanitize` executes the production mapping
helper against test-only UI/configuration boundaries, including cancellation and
backup failures. These boundaries do not replace the code in application builds.
`python3 Tools/test_switch2kit_host.py --sanitize` exercises the production host
wrapper against test-only SDK/SDL/file boundaries, including automatic policy,
saved consent, failed configuration, stable IDs, start-once and explicit stop.
`python3 Tools/test_switch2kit_autoconnect.py` checks guarded UI/startup wiring.
The native workflow compiles the complete application and inspects the embedded
library and Bluetooth description. These checks do not establish physical
controller behavior, clean-Mac startup, latency, or gameplay acceptance.

The user has confirmed input with the initial integration. The new automatic setup
and physical rumble still need acceptance on a real NSO GameCube controller:
pair/permission refusal and retry; every button and axis; light L/R travel without
a click and independent full clicks; disconnect while holding input; reconnect;
two identical controllers; app restart; normal quit; motor start/stop; and an actual game session.
Automatic recovery additionally needs a real Mac/controller test: play, pause,
leave the controller off longer than 60 seconds, resume, and power it on without
opening settings. Repeat several cycles, test Bluetooth off/on and two controllers
returning in reverse order, then verify Disconnect stays stopped and disabling
auto-connect preserves a live controller. These hardware checks have not been
performed for this change. Retain the distinction between build success and these
hardware results.

This contribution was prepared with AI assistance. The build glue, host wrapper,
UI integration, profile, documentation and checks require human review. The
controller protocol/Swift engine is reused from the pinned Switch2Kit dependency.
