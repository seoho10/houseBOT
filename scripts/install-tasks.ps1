# One-time installer: registers Windows Task Scheduler entries for houseBOT.
# Run this as the current user (no admin needed). Re-running replaces existing tasks.
#
# Usage:
#   .\scripts\install-tasks.ps1                       # default: 08:30 daily, check every 2h 09-21
#   .\scripts\install-tasks.ps1 -DailyAt "08:32"      # offset for second machine
#   .\scripts\install-tasks.ps1 -CheckOffsetMinutes 2 # check runs at 09:02, 11:02, ...

param(
    [string]$DailyAt = "08:30",
    [int]$CheckOffsetMinutes = 0
)

$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $PSScriptRoot
$DailyScript = Join-Path $PSScriptRoot "run_daily.ps1"
$CheckScript = Join-Path $PSScriptRoot "run_check.ps1"

Write-Host "Project dir: $ProjectDir"
Write-Host "Daily at:    $DailyAt"
Write-Host "Check offset: +$CheckOffsetMinutes min"
Write-Host ""

function Register-houseBOTTask {
    param([string]$Name, [string]$Script, [Microsoft.Management.Infrastructure.CimInstance[]]$Triggers)

    $action = New-ScheduledTaskAction `
        -Execute "powershell.exe" `
        -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Script`""

    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -WakeToRun `
        -ExecutionTimeLimit (New-TimeSpan -Minutes 20)

    # If task exists, replace it
    if (Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $Name -Confirm:$false
    }

    Register-ScheduledTask `
        -TaskName $Name `
        -Action $action `
        -Trigger $Triggers `
        -Settings $settings `
        -Description "houseBOT - https://github.com/seoho10/houseBOT" `
        -RunLevel Limited | Out-Null

    Write-Host "  Registered: $Name"
}

# Daily summary trigger
$dailyTrigger = New-ScheduledTaskTrigger -Daily -At $DailyAt
Register-houseBOTTask -Name "houseBOT-Daily" -Script $DailyScript -Triggers @($dailyTrigger)

# Light check: every 2 hours from 09:00 to 21:00 (7 triggers)
$checkTriggers = @()
foreach ($hour in 9,11,13,15,17,19,21) {
    $minute = $CheckOffsetMinutes
    $timeStr = "{0:00}:{1:00}" -f $hour, $minute
    $checkTriggers += New-ScheduledTaskTrigger -Daily -At $timeStr
}
Register-houseBOTTask -Name "houseBOT-Check" -Script $CheckScript -Triggers $checkTriggers

# WakeToRun only works if the active power plan allows wake timers. Enable on AC + battery.
$guid = (powercfg /getactivescheme) -replace '.*GUID: ([a-f0-9-]+).*', '$1'
powercfg /setacvalueindex $guid SUB_SLEEP RTCWAKE 1 2>$null
powercfg /setdcvalueindex $guid SUB_SLEEP RTCWAKE 1 2>$null
powercfg /setactive $guid 2>$null
Write-Host "  Wake timers enabled (so tasks can wake the PC from sleep)"

Write-Host ""
Write-Host "Done. View tasks: Get-ScheduledTask -TaskName 'houseBOT-*'"
Write-Host "Run now (smoke test):"
Write-Host "  Start-ScheduledTask -TaskName 'houseBOT-Daily'"
