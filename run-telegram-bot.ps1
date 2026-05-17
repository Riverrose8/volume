param(
  [ValidateSet("bsc", "base")]
  [string]$Network = "bsc",
  [switch]$Install
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

function Get-PythonCommand {
  $py = Get-Command py -ErrorAction SilentlyContinue
  if ($py) {
    return "py"
  }

  $python = Get-Command python -ErrorAction SilentlyContinue
  if ($python) {
    return "python"
  }

  $bundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
  if (Test-Path -LiteralPath $bundledPython) {
    return $bundledPython
  }

  throw "Python was not found. Install Python 3.8+ first."
}

function Invoke-SystemPython {
  param([Parameter(Mandatory = $true)][string[]]$Arguments)

  $pythonCommand = Get-PythonCommand
  if ($pythonCommand -eq "py") {
    & py -3 @Arguments
  }
  else {
    & $pythonCommand @Arguments
  }
}

$envFile = if ($Network -eq "base") { ".env_base" } else { ".env" }
$entrypoint = if ($Network -eq "base") { "main_base.py" } else { "main.py" }

if (-not (Test-Path -LiteralPath $envFile)) {
  throw "$envFile is missing. Run .\setup-telegram.ps1 first."
}

if ($Install) {
  if (-not (Test-Path -LiteralPath ".venv")) {
    Invoke-SystemPython -Arguments @("-m", "venv", ".venv")
  }

  & ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
  & ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
  & ".\.venv\Scripts\python.exe" $entrypoint
  exit $LASTEXITCODE
}

if (Test-Path -LiteralPath ".\.venv\Scripts\python.exe") {
  & ".\.venv\Scripts\python.exe" $entrypoint
  exit $LASTEXITCODE
}

Invoke-SystemPython -Arguments @($entrypoint)
exit $LASTEXITCODE
