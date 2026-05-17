$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$port = 8080
$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $port)
$listener.Start()

Write-Host "Serving $root at http://localhost:$port"
Write-Host "Press Ctrl+C to stop."

$contentTypes = @{
  ".html" = "text/html; charset=utf-8"
  ".css"  = "text/css; charset=utf-8"
  ".js"   = "application/javascript; charset=utf-8"
  ".json" = "application/json; charset=utf-8"
  ".png"  = "image/png"
  ".jpg"  = "image/jpeg"
  ".jpeg" = "image/jpeg"
  ".svg"  = "image/svg+xml"
}

function Invoke-ProxyGet {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Url
  )

  try {
    $response = Invoke-WebRequest -UseBasicParsing -Headers @{ "User-Agent" = "axi-local-server/1.0" } -Uri $Url
    return @{
      StatusCode = [int]$response.StatusCode
      Body = [System.Text.Encoding]::UTF8.GetBytes([string]$response.Content)
    }
  }
  catch {
    $statusCode = 502
    if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
      $statusCode = [int]$_.Exception.Response.StatusCode
    }

    $message = if ($_.Exception.Message) { $_.Exception.Message } else { "Proxy request failed." }
    return @{
      StatusCode = $statusCode
      Body = [System.Text.Encoding]::UTF8.GetBytes($message)
    }
  }
}

function Get-QueryParams {
  param(
    [Parameter(Mandatory = $true)]
    [string]$RawPath
  )

  $params = @{}
  if (-not $RawPath.Contains("?")) {
    return $params
  }

  $query = $RawPath.Substring($RawPath.IndexOf("?") + 1)
  foreach ($pair in $query.Split("&", [System.StringSplitOptions]::RemoveEmptyEntries)) {
    $parts = $pair.Split("=", 2)
    $key = [System.Uri]::UnescapeDataString($parts[0])
    $value = if ($parts.Length -gt 1) { [System.Uri]::UnescapeDataString($parts[1]) } else { "" }
    $params[$key] = $value
  }

  return $params
}

function Send-Response {
  param(
    [Parameter(Mandatory = $true)]
    [System.Net.Sockets.NetworkStream]$Stream,
    [Parameter(Mandatory = $true)]
    [int]$StatusCode,
    [Parameter(Mandatory = $true)]
    [byte[]]$Body,
    [Parameter(Mandatory = $true)]
    [string]$ContentType
  )

  $reason = switch ($StatusCode) {
    200 { "OK" }
    400 { "Bad Request" }
    404 { "Not Found" }
    502 { "Bad Gateway" }
    default { "OK" }
  }

  $headerText = @(
    "HTTP/1.1 $StatusCode $reason"
    "Content-Type: $ContentType"
    "Content-Length: $($Body.Length)"
    "Connection: close"
    ""
    ""
  ) -join "`r`n"

  $headerBytes = [System.Text.Encoding]::ASCII.GetBytes($headerText)
  $Stream.Write($headerBytes, 0, $headerBytes.Length)
  $Stream.Write($Body, 0, $Body.Length)
}

try {
  while ($true) {
    $client = $listener.AcceptTcpClient()

    try {
      $stream = $client.GetStream()
      $reader = [System.IO.StreamReader]::new($stream, [System.Text.Encoding]::ASCII, $false, 1024, $true)
      $requestLine = $reader.ReadLine()

      while ($reader.ReadLine()) { }

      if ([string]::IsNullOrWhiteSpace($requestLine)) {
        continue
      }

      $parts = $requestLine.Split(" ")
      $rawPath = if ($parts.Length -ge 2) { $parts[1] } else { "/" }
      $method = if ($parts.Length -ge 1) { $parts[0] } else { "GET" }
      $requestPath = $rawPath.Split("?")[0]
      $queryParams = Get-QueryParams -RawPath $rawPath

      if ($requestPath -eq "/") {
        $requestPath = "/index.html"
      }

      if ($method -eq "GET" -and $requestPath -eq "/api/dex/tokens") {
        $tokenAddress = $queryParams["tokenAddress"]
        if (-not [string]::IsNullOrWhiteSpace($tokenAddress)) {
          $targetUrl = "https://api.dexscreener.com/latest/dex/tokens/$tokenAddress"
          $proxyResult = Invoke-ProxyGet -Url $targetUrl
          Send-Response -Stream $stream -StatusCode $proxyResult.StatusCode -Body $proxyResult.Body -ContentType "application/json; charset=utf-8"
          continue
        }
      }

      if ($method -eq "GET" -and $requestPath -eq "/api/dex/token-profiles") {
        $proxyResult = Invoke-ProxyGet -Url "https://api.dexscreener.com/token-profiles/latest/v1"
        Send-Response -Stream $stream -StatusCode $proxyResult.StatusCode -Body $proxyResult.Body -ContentType "application/json; charset=utf-8"
        continue
      }

      if ($method -eq "GET" -and $requestPath -eq "/api/dex/token-boosts") {
        $proxyResult = Invoke-ProxyGet -Url "https://api.dexscreener.com/token-boosts/latest/v1"
        Send-Response -Stream $stream -StatusCode $proxyResult.StatusCode -Body $proxyResult.Body -ContentType "application/json; charset=utf-8"
        continue
      }

      if ($method -eq "GET" -and $requestPath -eq "/api/dex/token-boosts-top") {
        $proxyResult = Invoke-ProxyGet -Url "https://api.dexscreener.com/token-boosts/top/v1"
        Send-Response -Stream $stream -StatusCode $proxyResult.StatusCode -Body $proxyResult.Body -ContentType "application/json; charset=utf-8"
        continue
      }

      if ($method -eq "GET" -and $requestPath -eq "/api/telegram/send") {
        $botToken = $queryParams["token"]
        $chatId = $queryParams["chatId"]
        $message = $queryParams["message"]

        if ([string]::IsNullOrWhiteSpace($botToken) -or [string]::IsNullOrWhiteSpace($chatId) -or [string]::IsNullOrWhiteSpace($message)) {
          $body = [System.Text.Encoding]::UTF8.GetBytes("Missing Telegram token, chatId, or message.")
          Send-Response -Stream $stream -StatusCode 400 -Body $body -ContentType "text/plain; charset=utf-8"
          continue
        }

        $telegramUrl = "https://api.telegram.org/bot$botToken/sendMessage?chat_id=$([System.Uri]::EscapeDataString($chatId))&text=$([System.Uri]::EscapeDataString($message))"
        $proxyResult = Invoke-ProxyGet -Url $telegramUrl
        Send-Response -Stream $stream -StatusCode $proxyResult.StatusCode -Body $proxyResult.Body -ContentType "application/json; charset=utf-8"
        continue
      }

      $safeRelativePath = [System.Uri]::UnescapeDataString($requestPath.TrimStart("/")).Replace("/", "\")
      $fullPath = [System.IO.Path]::GetFullPath((Join-Path $root $safeRelativePath))

      if ($fullPath.StartsWith($root) -and (Test-Path $fullPath) -and -not (Get-Item $fullPath).PSIsContainer) {
        $extension = [System.IO.Path]::GetExtension($fullPath).ToLowerInvariant()
        $contentType = $contentTypes[$extension]
        if (-not $contentType) {
          $contentType = "application/octet-stream"
        }

        $body = [System.IO.File]::ReadAllBytes($fullPath)
        Send-Response -Stream $stream -StatusCode 200 -Body $body -ContentType $contentType
      }
      else {
        $body = [System.Text.Encoding]::UTF8.GetBytes("Not found")
        Send-Response -Stream $stream -StatusCode 404 -Body $body -ContentType "text/plain; charset=utf-8"
      }
    }
    finally {
      if ($reader) {
        $reader.Dispose()
      }

      if ($stream) {
        $stream.Dispose()
      }

      $client.Close()
    }
  }
}
finally {
  $listener.Stop()
}
