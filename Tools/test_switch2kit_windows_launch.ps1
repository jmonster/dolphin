param([Parameter(Mandatory=$true)][string]$Executable)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$exe = (Resolve-Path $Executable).Path
$directory = Split-Path $exe
$expected = (Resolve-Path (Join-Path $directory 'Switch2KitC.dll')).Path
$report = @()
for ($attempt = 1; $attempt -le 2; $attempt++) {
    $process = Start-Process -FilePath $exe -WorkingDirectory $directory -PassThru
    try {
        $deadline = [DateTime]::UtcNow.AddSeconds(60)
        do {
            Start-Sleep -Milliseconds 250
            $process.Refresh()
            if ($process.HasExited) { throw "Application exited before opening a window: $($process.ExitCode)" }
        } until ($process.MainWindowHandle -ne 0 -or [DateTime]::UtcNow -gt $deadline)
        if ($process.MainWindowHandle -eq 0) { throw 'No application window appeared within 60 seconds.' }
        $loaded = @($process.Modules | Where-Object { $_.ModuleName -eq 'Switch2KitC.dll' })
        if ($loaded.Count -ne 1 -or $loaded[0].FileName -ne $expected) {
            throw 'The running application did not load its own Switch2Kit DLL.'
        }
        if (-not $process.CloseMainWindow()) { throw 'The application rejected a normal close request.' }
        if (-not $process.WaitForExit(20000)) { throw 'The application did not shut down normally.' }
        if ($process.ExitCode -ne 0) { throw "Application failed during shutdown: $($process.ExitCode)" }
        $report += @{ attempt=$attempt; visibleWindow=$true; localControllerDLL=$true; exitCode=$process.ExitCode }
    } finally {
        if (-not $process.HasExited) { $process.Kill(); $process.WaitForExit() }
        $process.Dispose()
    }
}
$report | ConvertTo-Json | Set-Content windows-launch.json
Write-Host 'PASS relocated application launch, local DLL loading, normal quit and relaunch (no physical controller).'
