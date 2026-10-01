$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'ServiceControl.psm1') -Force
if (-not (Get-LineStatus).Local) { throw '請先在控制台啟動 LINE 服務。' }
$path = Join-Path $PSScriptRoot 'line-oa-archive\instance\admin-access.json'
if (-not (Test-Path -LiteralPath $path)) { throw '請重啟 LINE 服務以啟用管理後台。' }
$access = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
Start-Process "http://127.0.0.1:$($access.port)/#$($access.token)"
