$ErrorActionPreference = 'Stop'
$taskScript = Join-Path $PSScriptRoot 'bot.py'
$taskPidFile = Join-Path $PSScriptRoot '.runtime\bot.pid'
if (-not (Test-Path -LiteralPath $taskPidFile)) {
    Write-Output 'Bot is not running.'
    return
}
$taskBotPid = [int](Get-Content -LiteralPath $taskPidFile -Raw).Trim()
$taskProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $taskBotPid"
if ($taskProcess -and $taskProcess.CommandLine -and $taskProcess.CommandLine.Contains($taskScript)) {
    $taskChildren = Get-CimInstance Win32_Process -Filter "ParentProcessId = $taskBotPid"
    foreach ($taskChild in $taskChildren) {
        if ($taskChild.CommandLine -and $taskChild.CommandLine.Contains($taskScript)) {
            Stop-Process -Id $taskChild.ProcessId -Force -ErrorAction SilentlyContinue
        }
    }
    Stop-Process -Id $taskBotPid -Force -ErrorAction SilentlyContinue
    Write-Output "Bot stopped (PID $taskBotPid)."
} else {
    Write-Output 'Saved bot process is no longer running.'
}
Remove-Item -LiteralPath $taskPidFile -Force
