$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root ".venv\Scripts\python.exe"
$stdout = Join-Path $root "bot-bsc.log"
$stderr = Join-Path $root "bot-bsc.err.log"

if (-not (Test-Path -LiteralPath $python)) {
  throw "Virtual environment is missing. Run .\run-telegram-bot.ps1 -Network bsc -Install first."
}

$psi = [System.Diagnostics.ProcessStartInfo]::new()
$psi.FileName = $python
$psi.Arguments = "main.py"
$psi.WorkingDirectory = $root
$psi.UseShellExecute = $false
$psi.CreateNoWindow = $true
$psi.RedirectStandardOutput = $false
$psi.RedirectStandardError = $false

$process = [System.Diagnostics.Process]::Start($psi)
$process.Id | Set-Content -LiteralPath (Join-Path $root "bot-bsc.pid") -Encoding ASCII

"Started BSC/PancakeSwap bot with PID $($process.Id)." | Tee-Object -FilePath $stdout -Append
"Logs may also be written by the bot to its configured log file." | Tee-Object -FilePath $stdout -Append
