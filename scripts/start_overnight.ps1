$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $Root "monitoring"
New-Item -ItemType Directory -Force $LogDir | Out-Null

$BotOut = Join-Path $LogDir "overnight_bot.out.log"
$BotErr = Join-Path $LogDir "overnight_bot.err.log"
$DashOut = Join-Path $LogDir "overnight_dashboard.out.log"
$DashErr = Join-Path $LogDir "overnight_dashboard.err.log"
$BotPid = Join-Path $LogDir "overnight_bot.pid"
$DashPid = Join-Path $LogDir "overnight_dashboard.pid"

Remove-Item $BotOut,$BotErr,$DashOut,$DashErr -Force -ErrorAction SilentlyContinue

if (Test-Path $BotPid) {
    $ExistingBot = Get-Content $BotPid
    Get-Process -Id $ExistingBot -ErrorAction SilentlyContinue | Stop-Process -Force
}
if (Test-Path $DashPid) {
    $ExistingDash = Get-Content $DashPid
    Get-Process -Id $ExistingDash -ErrorAction SilentlyContinue | Stop-Process -Force
}

$Bot = Start-Process -FilePath python `
    -ArgumentList "main.py" `
    -WorkingDirectory $Root `
    -RedirectStandardOutput $BotOut `
    -RedirectStandardError $BotErr `
    -PassThru `
    -WindowStyle Hidden

$Dash = Start-Process -FilePath python `
    -ArgumentList "-m","streamlit","run","app.py","--server.port","8501","--server.headless","true" `
    -WorkingDirectory $Root `
    -RedirectStandardOutput $DashOut `
    -RedirectStandardError $DashErr `
    -PassThru `
    -WindowStyle Hidden

Set-Content -Path $BotPid -Value $Bot.Id
Set-Content -Path $DashPid -Value $Dash.Id

Write-Host "Paper bot started. PID: $($Bot.Id)"
Write-Host "Dashboard started. PID: $($Dash.Id)"
Write-Host "Open: http://localhost:8501"
Write-Host "Logs:"
Write-Host "  $BotOut"
Write-Host "  $BotErr"
Write-Host "  $DashOut"
Write-Host "  $DashErr"

