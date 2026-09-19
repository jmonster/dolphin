param([Parameter(Mandatory=$true)][string]$Archive,
      [string]$Report = 'windows-launch.json',
      [string]$ForbiddenRoot = '')
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$qualifier = Join-Path $root 'Externals/Switch2Kit/tests/emulator-launch/windows.ps1'
if (-not (Test-Path $qualifier)) { throw 'Initialize the pinned Switch2Kit submodule before qualification.' }
# The SDK supervisor extracts the exact archive into a new path with spaces,
# launches with an isolated profile and OS-only PATH, inspects loaded DLLs,
# then normally closes and relaunches the real GUI. A failure is not a pass.
& $qualifier -Emulator dolphin -Archive $Archive -Report $Report -ForbiddenRoot $ForbiddenRoot
