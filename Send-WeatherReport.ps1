param(
    [ValidateSet('user','group','both','subscribers')][string]$Target = 'user',
    [string]$ImagePath = 'D:\Tools\ai_weather_report\output\weather_report.png',
    [switch]$PrepareOnly,
    [switch]$ListTargets
)
$ErrorActionPreference = 'Stop'
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$sender = Join-Path $PSScriptRoot 'line-oa-archive\send_image.py'
if ($ListTargets) { & $python $sender --list-targets }
elseif ($PrepareOnly) { & $python $sender $ImagePath --prepare-only }
else { & $python $sender $ImagePath --target $Target }
if ($LASTEXITCODE -ne 0) { throw '天氣圖片操作未完成，請依上方訊息確認。' }
