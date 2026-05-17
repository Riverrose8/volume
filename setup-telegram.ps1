param(
  [ValidateSet("bsc", "base", "both")]
  [string]$Network = "both",
  [string]$BotToken = "",
  [string]$ChatId = "",
  [string]$TestChatId = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

if ([string]::IsNullOrWhiteSpace($BotToken)) {
  $BotToken = Read-Host "Telegram bot token from BotFather"
}

if ([string]::IsNullOrWhiteSpace($ChatId)) {
  $ChatId = Read-Host "Telegram chat ID or channel username"
}

if ([string]::IsNullOrWhiteSpace($BotToken) -or [string]::IsNullOrWhiteSpace($ChatId)) {
  throw "Telegram bot token and chat ID are required."
}

function Backup-IfExists {
  param([Parameter(Mandatory = $true)][string]$Path)

  if (Test-Path -LiteralPath $Path) {
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    Copy-Item -LiteralPath $Path -Destination "$Path.backup-$timestamp"
  }
}

function Write-BotEnv {
  param(
    [Parameter(Mandatory = $true)][string]$Path,
    [Parameter(Mandatory = $true)][string]$NetworkName
  )

  $isBase = $NetworkName -eq "base"
  $scanInterval = if ($isBase) { "15" } else { "30" }
  $minNewVolume = if ($isBase) { "30000" } else { "300000" }
  $maxAgeHours = if ($isBase) { "4" } else { "2" }
  $minMarketCap = if ($isBase) { "60000" } else { "100000" }
  $minLiquidity = if ($isBase) { "10000" } else { "5000" }
  $minHolders = if ($isBase) { "40" } else { "50" }

  $lines = @(
    "# Telegram",
    "TELEGRAM_BOT_TOKEN=$BotToken",
    "TELEGRAM_CHAT_ID=$ChatId",
    "TELEGRAM_ALERT_CHAT_ID=$ChatId",
    "TELEGRAM_TEST_CHAT_ID=$TestChatId",
    "TEST_MODE=false",
    "",
    "# Bot settings",
    "SCAN_INTERVAL_SECONDS=$scanInterval",
    "MIN_5M_VOLUME_USD_NEW=$minNewVolume",
    "MAX_TOKEN_AGE_HOURS=$maxAgeHours",
    "MIN_STABILITY_CHECKS=2",
    "STABILITY_CHECKS=1",
    "MIN_5M_VOLUME_USD_ESTABLISHED=2000000",
    "MIN_HOLDERS=$minHolders",
    "MIN_MARKET_CAP_USD=$minMarketCap",
    "MIN_LIQUIDITY_USD=$minLiquidity",
    "MAX_BUY_TAX=3",
    "MAX_SELL_TAX=3",
    "EXCLUDE_HONEYPOTS=true",
    "DEDUP_TTL_HOURS=24",
    "DEDUP_ALERT_MINUTES=10",
    "",
    "# Optional API keys",
    "DEXTOOLS_API_KEY=",
    "BSCSCAN_API_KEY=",
    "BITQUERY_API_KEY=",
    "APIFY_API_TOKEN=",
    "",
    "# Optional trading bot button templates",
    "MAESTRO_URL_TEMPLATE=",
    "AXIOM_URL_TEMPLATE=https://axiom.trade/t/{token}/@zodchii",
    "BLOOM_URL_TEMPLATE=",
    "",
    "# Optional Krystal settings",
    "KRYSTAL_API_BASE=https://cloud-api.krystal.app",
    "KRYSTAL_API_KEY=",
    "KRYSTAL_CHAIN=bsc",
    "KRYSTAL_DEX=pancakeswap"
  )

  Backup-IfExists -Path $Path
  Set-Content -LiteralPath $Path -Value $lines -Encoding UTF8
  Write-Host "Wrote $Path"
}

if ($Network -eq "bsc" -or $Network -eq "both") {
  Write-BotEnv -Path (Join-Path $root ".env") -NetworkName "bsc"
}

if ($Network -eq "base" -or $Network -eq "both") {
  Write-BotEnv -Path (Join-Path $root ".env_base") -NetworkName "base"
}

Write-Host ""
Write-Host "Telegram setup complete."
Write-Host "Run BSC/PancakeSwap: powershell -ExecutionPolicy Bypass -File .\run-telegram-bot.ps1 -Network bsc"
Write-Host "Run Base:           powershell -ExecutionPolicy Bypass -File .\run-telegram-bot.ps1 -Network base"
