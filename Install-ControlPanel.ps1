$ErrorActionPreference = 'Stop'
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    & py -3 -m venv (Join-Path $PSScriptRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw '請先安裝 Python 3.11 以上版本及 Python Launcher。' }
}
& $python -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'
if ($LASTEXITCODE -ne 0) { throw '控制台需要 Python 3.11 以上版本。' }
& $python -m pip install -r (Join-Path $PSScriptRoot 'line-oa-archive\requirements.txt')
if ($LASTEXITCODE -ne 0) { throw '圖片發送套件安裝失敗，請確認網路。' }
$envPath = Join-Path $PSScriptRoot 'line-oa-archive\.env'
if (-not (Test-Path -LiteralPath $envPath)) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'line-oa-archive\.env.example') -Destination $envPath
}
$null = New-Item -ItemType Directory -Path (Join-Path $PSScriptRoot 'line-oa-archive\instance') -Force
$desktop = [Environment]::GetFolderPath('Desktop')
$shell = New-Object -ComObject WScript.Shell
$shortcutPath = Join-Path $desktop 'LINE 自動化控制台.lnk'
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$shortcut.Arguments = "-NoProfile -STA -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$(Join-Path $PSScriptRoot 'ControlPanel.ps1')`""
$shortcut.WorkingDirectory = $PSScriptRoot
$shortcut.Description = 'LINE 自動化服務啟動、停止與連線狀態'
$shortcut.IconLocation = "$(Join-Path $PSScriptRoot 'line-oa-archive\web\assets\brand\line-automation-logo-light.ico'),0"
$shortcut.WindowStyle = 7
$shortcut.Save()
Write-Output "已建立捷徑：$shortcutPath"
Write-Output '請在 line-oa-archive\.env 填入 PUBLIC_BASE_URL（與需要時的 ADMIN_PUBLIC_HOST）；首次使用請按「啟動 LINE」，再按「開啟管理後台」完成首次設定與 LINE OA 連線。'
