$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
$taskPython = Join-Path $taskRoot '.venv\Scripts\python.exe'
$taskScript = Join-Path $taskRoot 'bot.py'
$taskRuntime = Join-Path $taskRoot '.runtime'
$taskPidFile = Join-Path $taskRuntime 'bot.pid'

if (-not (Test-Path -LiteralPath $taskPython)) {
    throw 'Install dependencies first: python -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r requirements.txt'
}
New-Item -ItemType Directory -Path $taskRuntime -Force | Out-Null
if (Test-Path -LiteralPath $taskPidFile) {
    $taskPreviousPid = [int](Get-Content -LiteralPath $taskPidFile -Raw).Trim()
    $taskPrevious = Get-CimInstance Win32_Process -Filter "ProcessId = $taskPreviousPid"
    if ($taskPrevious -and $taskPrevious.CommandLine -and $taskPrevious.CommandLine.Contains($taskScript)) {
        Write-Output "Bot is already running (PID $taskPreviousPid)."
        return
    }
}
$taskProcess = Start-Process -FilePath $taskPython -ArgumentList @('-u', ('"' + $taskScript + '"')) -WorkingDirectory $taskRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $taskRuntime 'bot.stdout.log') -RedirectStandardError (Join-Path $taskRuntime 'bot.stderr.log') -PassThru
$taskProcess.Id | Set-Content -LiteralPath $taskPidFile
for ($taskAttempt = 0; $taskAttempt -lt 12; $taskAttempt++) {
    Start-Sleep -Seconds 1
    $taskProcess.Refresh()
    if ($taskProcess.HasExited) {
        throw 'Bot exited. Check .runtime\bot.stderr.log.'
    }
    $taskLog = Get-Content -LiteralPath (Join-Path $taskRuntime 'bot.stderr.log') -Raw -ErrorAction SilentlyContinue
    if ($taskLog -match 'Run polling for bot') {
        Write-Output "Bot started (PID $($taskProcess.Id)). Logs: $taskRuntime"
        return
    }
}
throw 'Bot process is running, but polling has not started. Check .runtime\bot.stderr.log.'
