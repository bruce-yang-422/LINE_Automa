param([switch]$SmokeTest)
$ErrorActionPreference = 'Stop'
# Windows PowerShell hosts do not opt in to DPI awareness by default.
# Set awareness before creating any WinForms handles so Windows does not stretch a bitmap.
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class LineControlDpi {
    [DllImport("user32.dll")]
    public static extern bool SetProcessDPIAware();
    [DllImport("user32.dll")]
    public static extern IntPtr SetThreadDpiAwarenessContext(IntPtr context);
    [DllImport("user32.dll")]
    public static extern uint GetDpiForWindow(IntPtr window);
}
'@
$null = [LineControlDpi]::SetProcessDPIAware()
$null = [LineControlDpi]::SetThreadDpiAwarenessContext([IntPtr]::new(-2))
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[Windows.Forms.Application]::EnableVisualStyles()
[Windows.Forms.Application]::SetCompatibleTextRenderingDefault($false)
$dpiGraphics = [Drawing.Graphics]::FromHwnd([IntPtr]::Zero)
try { $script:uiScale = $dpiGraphics.DpiX / 96.0 } finally { $dpiGraphics.Dispose() }
function New-UiSize([int]$Width, [int]$Height) {
    New-Object Drawing.Size([int][Math]::Round($Width * $script:uiScale), [int][Math]::Round($Height * $script:uiScale))
}
function New-UiPoint([int]$X, [int]$Y) {
    New-Object Drawing.Point([int][Math]::Round($X * $script:uiScale), [int][Math]::Round($Y * $script:uiScale))
}
$script:modulePath = Join-Path $PSScriptRoot 'ServiceControl.psm1'
$script:tasks = @{}
$script:lastLocal = [datetime]::MinValue
$script:lastPublic = [datetime]::MinValue
$script:publicOK = $false
$script:publicInstance = ''
$script:buttons = @()
$form = New-Object Windows.Forms.Form
$form.SuspendLayout()
# Scale this fixed layout explicitly; Framework Label controls otherwise scale twice.
$form.AutoScaleMode = [Windows.Forms.AutoScaleMode]::None
$form.Text = 'LINE 自動化控制台'
$brandIconPath = Join-Path $PSScriptRoot 'line-oa-archive\web\assets\brand\line-automation-logo-light.ico'
if (Test-Path -LiteralPath $brandIconPath) {
    $brandIcon = [Drawing.Icon]::new($brandIconPath)
    $form.Icon = $brandIcon
    $form.Add_Disposed({ $brandIcon.Dispose() }.GetNewClosure())
}
$form.ClientSize = New-UiSize 600 495
$form.StartPosition = 'CenterScreen'
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false
$form.Font = New-Object Drawing.Font('Microsoft JhengHei UI', 11)
function New-Label([int]$Y, [string]$Text) {
    $label = New-Object Windows.Forms.Label
    $form.Controls.Add($label)
    $label.Location = New-UiPoint 22 $Y
    $label.Size = New-UiSize 558 30
    $label.Text = $Text
    return $label
}
$config = New-Label 20 '設定：檢查中'
$local = New-Label 55 'LINE 本機服務：檢查中'
$public = New-Label 90 '公開連線：檢查中'
$null = New-Label 125 'reports.stack-base.com  →  本機 127.0.0.1:18474'
function Begin-Task([string]$Name, [string]$Action) {
    $ps = [PowerShell]::Create()
    $null = $ps.AddScript({ param($modulePath, $name, $action)
        Import-Module $modulePath -Force
        if ($name -eq 'action') { Invoke-LineAction $action }
        elseif ($name -eq 'public') { Get-LineStatus -Public }
        else { Get-LineStatus }
    }).AddArgument($script:modulePath).AddArgument($Name).AddArgument($Action)
    $script:tasks[$Name] = @{ PowerShell = $ps; Handle = $ps.BeginInvoke() }
}
function New-Button([int]$X, [int]$Y, [string]$Text) {
    $button = New-Object Windows.Forms.Button
    $form.Controls.Add($button)
    $button.Location = New-UiPoint $X $Y
    $button.Size = New-UiSize 174 40
    $button.Text = $Text
    return $button
}
foreach ($spec in @(@(22, '啟動 LINE', 'Start'), @(212, '停止 LINE', 'Stop'), @(402, '重啟 LINE', 'Restart'))) {
    $button = New-Button $spec[0] 175 $spec[1]
    $button.Tag = $spec[2]
    $button.Add_Click({
        if ($script:tasks.ContainsKey('action')) { return }
        foreach ($item in $script:buttons) { $item.Enabled = $false }
        $recent.Text = '操作中，請稍候…'
        $progress.Style = 'Marquee'
        $script:publicOK = $false
        Begin-Task action $this.Tag
    })
    $script:buttons += $button
}
$settings = New-Button 22 230 '編輯 LINE 設定'
$settings.Add_Click({
    $path = Join-Path $PSScriptRoot 'line-oa-archive\.env'
    if (-not (Test-Path -LiteralPath $path)) {
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'line-oa-archive\.env.example') -Destination $path
    }
    # This editor is intentionally visible for the user's settings entry.
    Start-Process notepad.exe -ArgumentList "`"$path`""
    $recent.Text = '填入 Channel secret 並儲存；修改後請重啟 LINE。'
})
$script:buttons += $settings
$health = New-Button 212 230 '開啟連線檢查'
$health.Add_Click({ Start-Process 'https://reports.stack-base.com/healthz' })
$logs = New-Button 402 230 '查看操作紀錄'
$logs.Add_Click({
    $dialog = New-Object Windows.Forms.Form
    $dialog.SuspendLayout()
    $dialog.AutoScaleMode = [Windows.Forms.AutoScaleMode]::None
    $dialog.Font = New-Object Drawing.Font('Microsoft JhengHei UI', 11)
    $dialog.Text = 'LINE 操作紀錄'
    $dialog.Size = New-UiSize 720 450
    $box = New-Object Windows.Forms.TextBox
    $box.Multiline = $true
    $box.ReadOnly = $true
    $box.ScrollBars = 'Both'
    $box.Dock = 'Fill'
    $path = Join-Path $PSScriptRoot 'line-oa-archive\instance\control.log'
    $box.Text = if (Test-Path -LiteralPath $path) { (Get-Content -LiteralPath $path -Tail 100) -join "`r`n" } else { '尚無操作紀錄。' }
    $dialog.Controls.Add($box)
    $dialog.ResumeLayout($false)
    $null = $dialog.ShowDialog($form)
    $dialog.Dispose()
})
$recipients = New-Button 22 285 '收件者與發送'
$recipients.Add_Click({
    try { & (Join-Path $PSScriptRoot 'Open-Recipients.ps1') }
    catch { $recent.Text = '請先啟動或重啟 LINE 服務，再開啟收件者管理。' }
})
$script:buttons += $recipients
$recent = New-Label 340 '最近操作：尚無'
$recent.Height = [int][Math]::Round(65 * $script:uiScale)
$progress = New-Object Windows.Forms.ProgressBar
$form.Controls.Add($progress)
$progress.Location = New-UiPoint 22 410
$progress.Size = New-UiSize 554 12
$null = New-Label 435 '關閉視窗不會停止 LINE；共用 Tunnel 不受啟停控制。'
$timer = New-Object Windows.Forms.Timer
$timer.Interval = 250
$timer.Add_Tick({
    foreach ($name in @($script:tasks.Keys)) {
        $task = $script:tasks[$name]
        if (-not $task.Handle.IsCompleted) { continue }
        try {
            $result = @($task.PowerShell.EndInvoke($task.Handle))
            if ($task.PowerShell.HadErrors) { throw '背景操作失敗' }
            if ($name -eq 'action') { $recent.Text = ($result -join ' ') }
            elseif ($result.Count) {
                $state = $result[-1]
                if ($name -eq 'public') {
                    $script:publicOK = $state.Public
                    $script:publicInstance = $state.Instance
                }
                $config.Text = '設定：' + $(if ($state.Configured) { '已填入必要設定' } else { '未完成，請按「編輯 LINE 設定」' })
                $local.Text = 'LINE 本機服務：' + $(if ($state.Stopping) { '停止中' } elseif ($state.Local) { '已啟動' } elseif ($state.Managed) { '啟動中或健康檢查異常' } else { '已停止或未受管理' })
                $ready = $state.Local -and -not $state.Stopping -and $script:publicOK -and $state.Instance -eq $script:publicInstance
                $public.Text = '公開連線：' + $(if (-not $state.Local) { '等待本機服務啟動' } elseif ($ready) { '正常' } else { '未就緒，請確認 Tunnel 路由' })
                $public.ForeColor = if ($ready) { [Drawing.Color]::ForestGreen } else { [Drawing.Color]::DarkOrange }
                $local.ForeColor = if ($state.Local -and -not $state.Stopping) { [Drawing.Color]::ForestGreen } else { [Drawing.Color]::DarkOrange }
            }
        } catch {
            if ($name -eq 'action') {
                $recent.Text = '操作未完成，請查看設定與操作紀錄。'
                if ($task.PowerShell.Streams.Error.Count) {
                    $message = $task.PowerShell.Streams.Error[0].Exception.Message
                    if ($message.StartsWith('LINE：')) { $recent.Text = $message }
                }
            } else { $public.Text = '狀態檢查失敗，請查看設定。'; $script:publicOK = $false }
        } finally {
            $task.PowerShell.Dispose()
            $script:tasks.Remove($name)
            if ($name -eq 'action') {
                foreach ($item in $script:buttons) { $item.Enabled = $true }
                $progress.Style = 'Blocks'
                $script:lastLocal = [datetime]::MinValue
                $script:lastPublic = [datetime]::MinValue
            }
        }
    }
    if (-not $script:tasks.ContainsKey('local') -and ((Get-Date) - $script:lastLocal).TotalSeconds -ge 3) { $script:lastLocal = Get-Date; Begin-Task local '' }
    if (-not $script:tasks.ContainsKey('public') -and ((Get-Date) - $script:lastPublic).TotalSeconds -ge 15) { $script:lastPublic = Get-Date; Begin-Task public '' }
})
$form.Add_FormClosing({
    if ($script:tasks.ContainsKey('action')) { $_.Cancel = $true; $recent.Text = '請等待本次操作完成或逾時後再關閉視窗。' }
})
$form.Add_FormClosed({
    $timer.Stop()
    foreach ($task in $script:tasks.Values) { $task.PowerShell.Stop(); $task.PowerShell.Dispose() }
    $timer.Dispose()
})
$form.ResumeLayout($false)
if ($SmokeTest) {
    $dpi = [LineControlDpi]::GetDpiForWindow($form.Handle)
    if ($dpi -le 0) { throw 'Unable to determine window DPI.' }
    foreach ($control in $form.Controls) {
        if ($control.Right -gt $form.ClientSize.Width -or $control.Bottom -gt $form.ClientSize.Height) {
            throw 'A control extends beyond the scaled window.'
        }
    }
    "LINE ControlPanel UI constructed; DPI=$dpi; client=$($form.ClientSize.Width)x$($form.ClientSize.Height)"
    $form.Dispose()
    exit
}
$timer.Start()
[Windows.Forms.Application]::Run($form)
