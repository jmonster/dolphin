param([switch]$Run)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
Set-Location (Join-Path $PSScriptRoot '..')
if (-not [Environment]::Is64BitOperatingSystem -or -not [Environment]::Is64BitProcess) {
    throw 'Use 64-bit PowerShell on x64 Windows.'
}
foreach ($tool in @('git', 'cmake', 'ninja', 'swift', 'swiftc')) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { throw "Missing build tool: $tool" }
}
$vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
if (-not (Test-Path $vswhere)) { throw 'Install Visual Studio 2022 Desktop development with C++ and a Windows SDK.' }
# Swift 6.2.1 bundles Clang 19. VS 2026's STL requires Clang 20 or newer.
# Select VS 2022 explicitly, including on hosts with both versions installed.
$vs = & $vswhere -latest -version '[17.0,18.0)' -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if ($LASTEXITCODE -ne 0 -or -not $vs) { throw 'Visual Studio 2022 C++ x64 tools were not found. Install the Desktop development with C++ workload and a Windows SDK; VS 2026 is not compatible with Swift 6.2.1.' }
Write-Host "Using Visual Studio 2022: $vs"
cmd /c "`"$vs\Common7\Tools\VsDevCmd.bat`" -arch=x64 -host_arch=x64 >nul && set" | ForEach-Object {
    if ($_ -match '^([^=]+)=(.*)$') { [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2], 'Process') }
}
if ($LASTEXITCODE -ne 0) { throw 'Could not initialize the Visual C++ environment.' }
$target = swiftc -print-target-info | ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or $target.target.triple -notmatch '^x86_64-.*windows-msvc$') {
    throw 'Install the native x64 Swift toolchain; ARM64 and cross-compilation are not supported here.'
}
# Keep runtime lookup local to this process and its launched application.
$env:PATH = (($target.paths.runtimeLibraryPaths | Where-Object { Test-Path $_ }) -join ';') + ';' + $env:PATH
git submodule update --init --recursive
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
cmake -S . -B build-switch2kit-windows -G Ninja -DCMAKE_BUILD_TYPE=Release `
    -DENABLE_SWITCH2KIT=ON -DENABLE_SDL=ON -DENABLE_QT=ON -DUSE_SYSTEM_SDL3=OFF `
    -DENABLE_TESTS=OFF -DENABLE_CLI_TOOL=OFF -DENABLE_AUTOUPDATE=OFF
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
cmake --build build-switch2kit-windows --target dolphin-emu --parallel 3
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$app = Join-Path $PWD 'build-switch2kit-windows/Binaries/Dolphin.exe'
if (-not (Test-Path $app) -or -not (Test-Path (Join-Path (Split-Path $app) 'Switch2KitC.dll'))) {
    throw 'The controller-enabled application or its native DLL is missing.'
}
Write-Host "Built: $app"
if ($Run) { Start-Process -FilePath $app -WorkingDirectory (Split-Path $app) }
