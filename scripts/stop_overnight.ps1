$Root = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $Root "monitoring"
$PidFiles = @(
    Join-Path $LogDir "overnight_bot.pid"
    Join-Path $LogDir "overnight_dashboard.pid"
    Join-Path $LogDir "dashboard.pid"
)

foreach ($PidFile in $PidFiles) {
    if (Test-Path $PidFile) {
        $PidValue = Get-Content $PidFile
        Get-Process -Id $PidValue -ErrorAction SilentlyContinue | Stop-Process -Force
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "Stopped overnight bot/dashboard processes if they were running."

