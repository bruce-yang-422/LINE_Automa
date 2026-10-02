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

# Modern Color Palette
$cBg = [Drawing.Color]::FromArgb(248, 250, 252)        # Slate 50
$cCard = [Drawing.Color]::FromArgb(255, 255, 255)      # White
$cBorder = [Drawing.Color]::FromArgb(226, 232, 240)    # Slate 200
$cText = [Drawing.Color]::FromArgb(15, 23, 42)         # Slate 900
$cTextMuted = [Drawing.Color]::FromArgb(100, 116, 139) # Slate 500
$cLineGreen = [Drawing.Color]::FromArgb(0, 185, 0)     # LINE Green
$cLineGreenHover = [Drawing.Color]::FromArgb(0, 160, 0)
$cGreen = [Drawing.Color]::FromArgb(22, 163, 74)       # Green 600
$cGreenBg = [Drawing.Color]::FromArgb(240, 253, 244)   # Green 50
$cOrange = [Drawing.Color]::FromArgb(217, 119, 6)      # Amber 600
$cOrangeBg = [Drawing.Color]::FromArgb(255, 251, 235)  # Amber 50
$cRed = [Drawing.Color]::FromArgb(225, 29, 72)         # Rose 600

$form = New-Object Windows.Forms.Form
$form.SuspendLayout()
$form.AutoScaleMode = [Windows.Forms.AutoScaleMode]::None
$form.Text = 'LINE 自動化控制台'
$form.BackColor = $cBg
$brandIconPath = Join-Path $PSScriptRoot 'line-oa-archive\web\assets\brand\line-automation-logo-light.ico'
if (Test-Path -LiteralPath $brandIconPath) {
    $brandIcon = [Drawing.Icon]::new($brandIconPath)
    $form.Icon = $brandIcon
    $form.Add_Disposed({ $brandIcon.Dispose() }.GetNewClosure())
}
$form.ClientSize = New-UiSize 650 495
$form.StartPosition = 'CenterScreen'
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false
$form.Font = New-Object Drawing.Font('Microsoft JhengHei UI', 10)

# ==================== Top Header Toolbar ====================
$topBar = New-Object Windows.Forms.Panel
$topBar.Location = New-UiPoint 0 0
$topBar.Size = New-UiSize 650 72
$topBar.BackColor = $cCard
$form.Controls.Add($topBar)

$topBorder = New-Object Windows.Forms.Panel
$topBorder.Location = New-UiPoint 0 71
$topBorder.Size = New-UiSize 650 1
$topBorder.BackColor = $cBorder
$form.Controls.Add($topBorder)

$titleLabel = New-Object Windows.Forms.Label
$titleLabel.Location = New-UiPoint 18 13
$titleLabel.Size = New-UiSize 260 26
$titleLabel.Text = 'LINE 自動化控制台'
$titleLabel.Font = New-Object Drawing.Font('Microsoft JhengHei UI', 12.5, [Drawing.FontStyle]::Bold)
$titleLabel.ForeColor = $cText
$topBar.Controls.Add($titleLabel)

$subTitleLabel = New-Object Windows.Forms.Label
$subTitleLabel.Location = New-UiPoint 19 40
$subTitleLabel.Size = New-UiSize 260 20
$subTitleLabel.Text = '本機服務與公開連線管理'
$subTitleLabel.Font = New-Object Drawing.Font('Microsoft JhengHei UI', 9)
$subTitleLabel.ForeColor = $cTextMuted
$topBar.Controls.Add($subTitleLabel)

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

# Top Quick Actions (Start / Stop / Restart)
$btnStart = New-Object Windows.Forms.Button
$btnStart.Location = New-UiPoint 284 17
$btnStart.Size = New-UiSize 110 38
$btnStart.Text = '▶  啟動'
$btnStart.Font = New-Object Drawing.Font('Microsoft JhengHei UI', 10, [Drawing.FontStyle]::Bold)
$btnStart.FlatStyle = [Windows.Forms.FlatStyle]::Flat
$btnStart.FlatAppearance.BorderSize = 0
$btnStart.BackColor = $cLineGreen
$btnStart.ForeColor = [Drawing.Color]::White
$btnStart.Tag = 'Start'
$topBar.Controls.Add($btnStart)

$btnStop = New-Object Windows.Forms.Button
$btnStop.Location = New-UiPoint 402 17
$btnStop.Size = New-UiSize 110 38
$btnStop.Text = '⏹  停止'
$btnStop.Font = New-Object Drawing.Font('Microsoft JhengHei UI', 10, [Drawing.FontStyle]::Bold)
$btnStop.FlatStyle = [Windows.Forms.FlatStyle]::Flat
$btnStop.FlatAppearance.BorderColor = [Drawing.Color]::FromArgb(254, 205, 211)
$btnStop.FlatAppearance.BorderSize = 1
$btnStop.BackColor = [Drawing.Color]::White
$btnStop.ForeColor = $cRed
$btnStop.Tag = 'Stop'
$topBar.Controls.Add($btnStop)

$btnRestart = New-Object Windows.Forms.Button
$btnRestart.Location = New-UiPoint 520 17
$btnRestart.Size = New-UiSize 110 38
$btnRestart.Text = '🔄  重啟'
$btnRestart.Font = New-Object Drawing.Font('Microsoft JhengHei UI', 10, [Drawing.FontStyle]::Bold)
$btnRestart.FlatStyle = [Windows.Forms.FlatStyle]::Flat
$btnRestart.FlatAppearance.BorderColor = $cBorder
$btnRestart.FlatAppearance.BorderSize = 1
$btnRestart.BackColor = [Drawing.Color]::White
$btnRestart.ForeColor = $cText
$btnRestart.Tag = 'Restart'
$topBar.Controls.Add($btnRestart)

$script:buttons = @($btnStart, $btnStop, $btnRestart)

foreach ($btn in @($btnStart, $btnStop, $btnRestart)) {
    $btn.Add_Click({
        if ($script:tasks.ContainsKey('action')) { return }
        foreach ($item in $script:buttons) { $item.Enabled = $false }
        $recentText.Text = '執行中，請稍候…'
        $progress.Style = 'Marquee'
        $script:publicOK = $false
        Begin-Task action $this.Tag
    })
}

# ==================== Left Column: Status & Network ====================
$leftCard = New-Object Windows.Forms.Panel
$leftCard.Location = New-UiPoint 18 84
$leftCard.Size = New-UiSize 302 334
$leftCard.BackColor = $cCard
$form.Controls.Add($leftCard)

$leftBorder = New-Object Windows.Forms.Panel
$leftBorder.Location = New-UiPoint 17 83
$leftBorder.Size = New-UiSize 304 336
$leftBorder.BackColor = $cBorder
$form.Controls.Add($leftBorder)
$leftCard.BringToFront()

$statusHeading = New-Object Windows.Forms.Label
$statusHeading.Location = New-UiPoint 14 12
$statusHeading.Size = New-UiSize 270 24
$statusHeading.Text = '連線與服務監控'
$statusHeading.Font = New-Object Drawing.Font('Microsoft JhengHei UI', 10.5, [Drawing.FontStyle]::Bold)
$statusHeading.ForeColor = $cText
$leftCard.Controls.Add($statusHeading)

function New-StatusRow([int]$Y, [string]$Title) {
    $titleLbl = New-Object Windows.Forms.Label
    $titleLbl.Location = New-UiPoint 14 $Y
    $titleLbl.Size = New-UiSize 100 22
    $titleLbl.Text = $Title
    $titleLbl.Font = New-Object Drawing.Font('Microsoft JhengHei UI', 9.5)
    $titleLbl.ForeColor = $cTextMuted
    $leftCard.Controls.Add($titleLbl)

    $valLbl = New-Object Windows.Forms.Label
    $valLbl.Location = New-UiPoint 116 $Y
    $valLbl.Size = New-UiSize 172 22
    $valLbl.Text = '檢查中…'
    $valLbl.Font = New-Object Drawing.Font('Microsoft JhengHei UI', 9.5, [Drawing.FontStyle]::Bold)
    $valLbl.ForeColor = $cOrange
    $leftCard.Controls.Add($valLbl)
    return $valLbl
}

$local = New-StatusRow 44 '本機服務：'
$public = New-StatusRow 74 '公開連線：'
$config = New-StatusRow 104 '系統設定：'

$dividerLeft = New-Object Windows.Forms.Panel
$dividerLeft.Location = New-UiPoint 14 136
$dividerLeft.Size = New-UiSize 274 1
$dividerLeft.BackColor = $cBorder
$leftCard.Controls.Add($dividerLeft)

$netHeading = New-Object Windows.Forms.Label
$netHeading.Location = New-UiPoint 14 146
$netHeading.Size = New-UiSize 270 22
$netHeading.Text = '網址與 Tunnel 映射'
$netHeading.Font = New-Object Drawing.Font('Microsoft JhengHei UI', 10, [Drawing.FontStyle]::Bold)
$netHeading.ForeColor = $cText
$leftCard.Controls.Add($netHeading)

$urlBox = New-Object Windows.Forms.Label
$urlBox.Location = New-UiPoint 14 174
$urlBox.Size = New-UiSize 274 54
$urlBox.BackColor = [Drawing.Color]::FromArgb(241, 245, 249)
$urlBox.ForeColor = [Drawing.Color]::FromArgb(51, 65, 85)
$urlBox.Font = New-Object Drawing.Font('Consolas', 9.5)
$urlBox.Text = "`r`n reports.stack-base.com`r`n ➔ 127.0.0.1:18474"
$leftCard.Controls.Add($urlBox)

$health = New-Object Windows.Forms.Button
$health.Location = New-UiPoint 14 238
$health.Size = New-UiSize 274 36
$health.Text = '🩺  開啟連線檢查 (healthz)'
$health.Font = New-Object Drawing.Font('Microsoft JhengHei UI', 9.5)
$health.FlatStyle = [Windows.Forms.FlatStyle]::Flat
$health.FlatAppearance.BorderColor = $cBorder
$health.FlatAppearance.BorderSize = 1
$health.BackColor = [Drawing.Color]::White
$health.ForeColor = $cText
$health.Add_Click({ Start-Process 'https://reports.stack-base.com/healthz' })
$leftCard.Controls.Add($health)

$logs = New-Object Windows.Forms.Button
$logs.Location = New-UiPoint 14 282
$logs.Size = New-UiSize 274 36
$logs.Text = '📋  查看操作紀錄'
$logs.Font = New-Object Drawing.Font('Microsoft JhengHei UI', 9.5)
$logs.FlatStyle = [Windows.Forms.FlatStyle]::Flat
$logs.FlatAppearance.BorderColor = $cBorder
$logs.FlatAppearance.BorderSize = 1
$logs.BackColor = [Drawing.Color]::White
$logs.ForeColor = $cText
$logs.Add_Click({
    $dialog = New-Object Windows.Forms.Form
    $dialog.SuspendLayout()
    $dialog.AutoScaleMode = [Windows.Forms.AutoScaleMode]::None
    $dialog.Font = New-Object Drawing.Font('Microsoft JhengHei UI', 10)
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
$leftCard.Controls.Add($logs)

# ==================== Right Column: Actions & Logs ====================
$rightCard = New-Object Windows.Forms.Panel
$rightCard.Location = New-UiPoint 330 84
$rightCard.Size = New-UiSize 302 334
$rightCard.BackColor = $cCard
$form.Controls.Add($rightCard)

$rightBorder = New-Object Windows.Forms.Panel
$rightBorder.Location = New-UiPoint 329 83
$rightBorder.Size = New-UiSize 304 336
$rightBorder.BackColor = $cBorder
$form.Controls.Add($rightBorder)
$rightCard.BringToFront()

# Primary CTA Button
$recipients = New-Object Windows.Forms.Button
$recipients.Location = New-UiPoint 14 14
$recipients.Size = New-UiSize 274 54
$recipients.Text = '🚀  開啟管理後台'
$recipients.Font = New-Object Drawing.Font('Microsoft JhengHei UI', 12, [Drawing.FontStyle]::Bold)
$recipients.FlatStyle = [Windows.Forms.FlatStyle]::Flat
$recipients.FlatAppearance.BorderSize = 0
$recipients.BackColor = $cLineGreen
$recipients.ForeColor = [Drawing.Color]::White
$recipients.Add_Click({
    try { & (Join-Path $PSScriptRoot 'Open-Recipients.ps1') }
    catch { Set-Recent '請先啟動或重啟 LINE 服務，再開啟管理後台。' }
})
$rightCard.Controls.Add($recipients)
$script:buttons += $recipients

$dividerRight = New-Object Windows.Forms.Panel
$dividerRight.Location = New-UiPoint 14 80
$dividerRight.Size = New-UiSize 274 1
$dividerRight.BackColor = $cBorder
$rightCard.Controls.Add($dividerRight)

$activityHeading = New-Object Windows.Forms.Label
$activityHeading.Location = New-UiPoint 14 92
$activityHeading.Size = New-UiSize 270 22
$activityHeading.Text = '即時操作與動態'
$activityHeading.Font = New-Object Drawing.Font('Microsoft JhengHei UI', 10, [Drawing.FontStyle]::Bold)
$activityHeading.ForeColor = $cText
$rightCard.Controls.Add($activityHeading)

$recentText = New-Object Windows.Forms.Label
$recentText.Location = New-UiPoint 14 120
$recentText.Size = New-UiSize 274 198
$recentText.BackColor = [Drawing.Color]::FromArgb(248, 250, 252)
$recentText.ForeColor = [Drawing.Color]::FromArgb(51, 65, 85)
$recentText.Font = New-Object Drawing.Font('Microsoft JhengHei UI', 9.5)
$recentText.Text = "系統就緒。`r`n`r`n點擊上方「▶ 啟動」可開啟服務；點擊「🚀 開啟管理後台」進入網頁工作台。"
$rightCard.Controls.Add($recentText)

function Set-Recent([string]$Message) {
    $recentText.Text = "最近操作（" + (Get-Date -Format 'HH:mm:ss') + "）：`r`n`r`n" + $Message
}

# ==================== Bottom Footer ====================
$progress = New-Object Windows.Forms.ProgressBar
$form.Controls.Add($progress)
$progress.Location = New-UiPoint 18 428
$progress.Size = New-UiSize 614 6

$hintLabel = New-Object Windows.Forms.Label
$form.Controls.Add($hintLabel)
$hintLabel.Location = New-UiPoint 18 440
$hintLabel.Size = New-UiSize 614 24
$hintLabel.Text = '💡 提示：關閉視窗不會停止 LINE 服務；共用 Tunnel 不受啟停控制。'
$hintLabel.Font = New-Object Drawing.Font('Microsoft JhengHei UI', 9)
$hintLabel.ForeColor = $cTextMuted

# Errors inside UI handlers
[Windows.Forms.Application]::add_ThreadException({ param($source, $e)
    $record = $e.Exception.ErrorRecord
    $where = if ($record) { ($record.InvocationInfo.PositionMessage + ' | ' + $record.ScriptStackTrace) -replace '\s+', ' ' } else { $e.Exception.StackTrace -replace '\s+', ' ' }
    try {
        $path = Join-Path $PSScriptRoot 'line-oa-archive\instance\control.log'
        Add-Content -LiteralPath $path -Value "$(Get-Date -Format s) 控制台錯誤：$($e.Exception.Message) $where" -Encoding UTF8
    } catch { }
    Set-Recent ('控制台發生錯誤，已寫入操作紀錄：' + $e.Exception.Message)
})

$timer = New-Object Windows.Forms.Timer
$timer.Interval = 250
$timer.Add_Tick({
    foreach ($name in @($script:tasks.Keys)) {
        $task = $script:tasks[$name]
        if (-not $task.Handle.IsCompleted) { continue }
        try {
            $result = @($task.PowerShell.EndInvoke($task.Handle))
            if ($task.PowerShell.HadErrors) { throw '背景操作失敗' }
            if ($name -eq 'action') { Set-Recent ($result -join ' ') }
            elseif ($result.Count) {
                $state = $result[-1]
                if ($name -eq 'public') {
                    $script:publicOK = $state.Public
                    $script:publicInstance = $state.Instance
                }
                $config.Text = if (-not $state.Configured) { 'Python 環境未就緒' } elseif (-not $state.PublicBaseUrl) { '未填 PUBLIC_BASE_URL' } elseif ($state.OAConfigured) { '已設定 LINE OA' } else { '尚未設定 LINE OA' }
                $config.ForeColor = if ($state.OAConfigured) { $cGreen } else { $cOrange }

                $localText = if ($state.Stopping) { '● 停止中' } elseif ($state.Local) { '● 已啟動' } elseif ($state.Managed) { '● 啟動中' } else { '● 已停止' }
                $local.Text = $localText
                $local.ForeColor = if ($state.Local -and -not $state.Stopping) { $cGreen } else { $cOrange }

                $ready = $state.Local -and -not $state.Stopping -and $script:publicOK -and $state.Instance -eq $script:publicInstance
                $publicText = if (-not $state.Local) { '● 等待服務啟動' } elseif ($ready) { '● 正常' } else { '● 未就緒' }
                $public.Text = $publicText
                $public.ForeColor = if ($ready) { $cGreen } else { $cOrange }
            }
        } catch {
            if ($name -eq 'action') {
                $message = '操作未完成，請查看設定與操作紀錄。'
                if ($task.PowerShell.Streams.Error.Count) {
                    $error0 = $task.PowerShell.Streams.Error[0].Exception.Message
                    if ($error0.StartsWith('LINE：')) { $message = $error0 }
                }
                Set-Recent $message
            } else {
                $public.Text = '● 檢查失敗'
                $public.ForeColor = $cRed
                $script:publicOK = $false
            }
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
    if ($script:tasks.ContainsKey('action')) { $_.Cancel = $true; $recentText.Text = '請等待本次操作完成或逾時後再關閉視窗。' }
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
            throw "A control ($($control.Name) at $($control.Right),$($control.Bottom)) extends beyond the scaled window ($($form.ClientSize.Width),$($form.ClientSize.Height))."
        }
    }
    "LINE ControlPanel UI constructed; DPI=$dpi; client=$($form.ClientSize.Width)x$($form.ClientSize.Height)"
    $form.Dispose()
    exit
}

$timer.Start()
[Windows.Forms.Application]::Run($form)

