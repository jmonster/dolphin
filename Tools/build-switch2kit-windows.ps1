param([switch]$Run, [string[]]$CMakeArgs = @())
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
Set-Location (Join-Path $PSScriptRoot '..')
if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT -or
    -not [Environment]::Is64BitOperatingSystem -or -not [Environment]::Is64BitProcess) {
    throw 'Use 64-bit PowerShell on x64 Windows.'
}
foreach ($tool in @('git', 'cmake', 'ninja', 'swift')) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { throw "Missing build tool: $tool" }
}
# Resolve one Swift installation before VsDevCmd changes PATH. Pass the same
# executables to CMake, including when reusing a previously configured build.
$swift = (Get-Command swift -CommandType Application).Source
$swiftc = Join-Path (Split-Path $swift) 'swiftc.exe'
if (-not (Test-Path $swiftc)) { throw 'The selected Swift installation has no swiftc.exe.' }
$swiftVersion = & $swift --version
if ($LASTEXITCODE -ne 0) { throw 'Could not query the Swift toolchain version.' }
Write-Output ($swiftVersion -join "`n")
if (($swiftVersion -join "`n") -notmatch 'Swift version (\d+\.\d+(?:\.\d+)?)' -or
    [version]$Matches[1] -lt [version]'6.3') {
    throw 'Windows Dolphin requires Swift 6.3 or newer (CI: 6.3.3). Swift 6.2 bundles Clang 19, which the Visual Studio 2026 STL rejects.'
}
$vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
if (-not (Test-Path $vswhere)) { throw 'Install Visual Studio 2026 Desktop development with C++ and a Windows SDK.' }
$vs = & $vswhere -latest -products '*' -version '[18.0,19.0)' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if ($LASTEXITCODE -ne 0 -or -not $vs) { throw 'Install the latest Visual Studio 2026 C++ x64 tools and Windows 11 SDK (22621 or newer).' }
cmd /c "`"$vs\Common7\Tools\VsDevCmd.bat`" -arch=x64 -host_arch=x64 >nul && set" | ForEach-Object {
    if ($_ -match '^([^=]+)=(.*)$') { [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2], 'Process') }
}
if ($LASTEXITCODE -ne 0) { throw 'Could not initialize the Visual C++ environment.' }
$targetInfo = & $swiftc -print-target-info
if ($LASTEXITCODE -ne 0) { throw 'Could not query the Swift target.' }
$target = $targetInfo | ConvertFrom-Json
if ($target.target.triple -notmatch '^x86_64-.*windows-msvc$') {
    throw 'Install the native x64 Swift toolchain; ARM64 and cross-compilation are not supported here.'
}
Write-Output "Visual Studio: $vs"
Write-Output "Swift target: $($target.target.triple)"
# Keep runtime lookup local to this process and its launched application.
$env:PATH = (($target.paths.runtimeLibraryPaths | Where-Object { Test-Path $_ }) -join ';') + ';' + $env:PATH
if ($env:GITHUB_ACTIONS -eq 'true') {
    python Tools/checkout_native.py --verify
} else {
    git submodule update --init --recursive
}
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
cmake -S . -B build-switch2kit-windows -G Ninja -DCMAKE_BUILD_TYPE=Release `
    -DENABLE_SWITCH2KIT=ON -DENABLE_SDL=ON -DENABLE_QT=ON -DUSE_SYSTEM_SDL3=OFF `
    -DENABLE_TESTS=OFF -DENABLE_CLI_TOOL=OFF -DENABLE_AUTOUPDATE=OFF `
    "-DSWITCH2KIT_SWIFT=$swift" "-DSWITCH2KIT_SWIFTC=$swiftc" @CMakeArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
# Compile the real Swift/C++ WinRT library first. Fail on toolchain/SDK
# incompatibility before spending time on Dolphin's other dependencies; do not
# bypass the Microsoft STL or Dolphin compiler guards. This target is reused by
# the application build, with the same SwiftPM configuration and scratch path.
cmake --build build-switch2kit-windows --target Switch2KitCBuild --parallel ([Environment]::ProcessorCount)
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
cmake --build build-switch2kit-windows --target dolphin-emu --parallel ([Environment]::ProcessorCount)
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$app = Join-Path $PWD 'build-switch2kit-windows/Binaries/Dolphin.exe'
if (-not (Test-Path $app) -or -not (Test-Path (Join-Path (Split-Path $app) 'Switch2KitC.dll'))) {
    throw 'The controller-enabled application or its native DLL is missing.'
}
Write-Host "Built: $app"
if ($Run) { Start-Process -FilePath $app -WorkingDirectory (Split-Path $app) }
