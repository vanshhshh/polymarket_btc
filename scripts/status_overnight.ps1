$Root = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $Root "monitoring"
$BotPid = Join-Path $LogDir "overnight_bot.pid"
$DashPid = Join-Path $LogDir "overnight_dashboard.pid"

if (Test-Path $BotPid) {
    $PidValue = Get-Content $BotPid
    $Process = Get-Process -Id $PidValue -ErrorAction SilentlyContinue
    if ($Process) { Write-Host "Bot running. PID: $PidValue" } else { Write-Host "Bot is not running." }
} else {
    Write-Host "Bot PID file not found."
}

if (Test-Path $DashPid) {
    $PidValue = Get-Content $DashPid
    $Process = Get-Process -Id $PidValue -ErrorAction SilentlyContinue
    if ($Process) { Write-Host "Dashboard running. PID: $PidValue" } else { Write-Host "Dashboard is not running." }
} else {
    Write-Host "Dashboard PID file not found."
}

python tools/evaluate_paper_performance.py

