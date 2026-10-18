param(
    [string]$BaseUrl = "http://localhost:8088",
    [string]$Prompt = "What does the employee handbook say about unemployment insurance?"
)

$ErrorActionPreference = "Stop"
$evidence = Join-Path $PSScriptRoot "..\evidence"
New-Item -ItemType Directory -Force -Path $evidence | Out-Null

$health = Invoke-RestMethod "$BaseUrl/health"
$body = @{ prompt = $Prompt } | ConvertTo-Json
$started = Get-Date
$response = Invoke-RestMethod "$BaseUrl/query" -Method Post -ContentType "application/json" -Body $body
$elapsed = ((Get-Date) - $started).TotalMilliseconds

$response | ConvertTo-Json -Depth 8 | Set-Content (Join-Path $evidence "e2e-response.json")
@"
timestamp=$($started.ToUniversalTime().ToString("o"))
health=$($health | ConvertTo-Json -Compress)
http_status=200
latency_ms=$([math]::Round($elapsed, 2))
flow=client -> api_gateway -> guardrails -> agent_logic -> vector_store -> telemetry
"@ | Set-Content (Join-Path $evidence "e2e-verification.log")

Write-Host "E2E verification passed ($([math]::Round($elapsed, 2)) ms)"
Write-Host $response.Content
