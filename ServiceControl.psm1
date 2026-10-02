$ErrorActionPreference = 'Stop'
$script:Root = $PSScriptRoot
$script:AppRoot = Join-Path $script:Root 'line-oa-archive'
$script:Python = Join-Path $script:Root '.venv\Scripts\python.exe'
$script:Port = 18474
$script:AdminPort = 18475
$script:PublicUrl = 'https://reports.stack-base.com'

function Get-LineStatePath { Join-Path $script:AppRoot 'instance\control-processes.json' }
function Get-LineRegistry {
    $path = Get-LineStatePath
    if (Test-Path -LiteralPath $path) { return (Get-Content -LiteralPath $path -Raw | ConvertFrom-Json) }
    return [pscustomobject]@{ instance = ''; processes = @() }
}
function Save-LineRegistry($Registry) {
    $path = Get-LineStatePath
    $Registry | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath "$path.tmp" -Encoding UTF8
    Move-Item -LiteralPath "$path.tmp" -Destination $path -Force
}
function Test-LineIdentity($Entry) {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$([int]$Entry.id)" -ErrorAction SilentlyContinue
    return ($null -ne $process -and $process.ExecutablePath -eq $Entry.executable -and
        $process.CreationDate.ToUniversalTime().Ticks.ToString() -eq $Entry.created -and $process.CommandLine -eq $Entry.command)
}
function Get-LineHealth([string]$Url) {
    try {
        $data = Invoke-RestMethod -Uri "$Url/_control/healthz?probe=$([guid]::NewGuid())" -TimeoutSec 2 -ErrorAction Stop
        if ($data.application -eq 'LINE_Automation' -and $data.protocol -eq 1) { return $data }
    } catch { }
    return $null
}
function Get-LineCheck {
    if (-not (Test-Path -LiteralPath $script:Python)) { return $null }
    try {
        $result = & $script:Python (Join-Path $script:AppRoot 'control_runtime.py') --check 2>$null
        if ($LASTEXITCODE -ne 0) { return $null }
        return $result | ConvertFrom-Json
    } catch { return $null }
}
function Get-LineConfiguration {
    $check = Get-LineCheck
    return [bool]($check -and $check.configured -and $check.python_ok)
}
function Get-LineStatus([switch]$Public) {
    $registry = Get-LineRegistry
    $owned = @($registry.processes | Where-Object { Test-LineIdentity $_ }).Count -gt 0
    $local = Get-LineHealth "http://127.0.0.1:$script:Port"
    $online = $owned -and $local -and $registry.instance -and $local.instance -eq $registry.instance
    $stopping = $false
    if ($owned -and $registry.instance) {
        $instance = ([guid]$registry.instance).ToString()
        $stopping = Test-Path -LiteralPath (Join-Path $script:AppRoot "instance\stop-$instance")
    }
    $remote = $null
    if ($Public -and $online) { $remote = Get-LineHealth $script:PublicUrl }
    $check = Get-LineCheck
    [pscustomobject]@{
        Configured = [bool]($check -and $check.configured -and $check.python_ok)
        OAConfigured = [bool]($check -and $check.oa_configured)
        PublicBaseUrl = [bool]($check -and $check.public_base_url)
        Managed = $owned
        Local = [bool]$online
        Stopping = [bool]$stopping
        Public = [bool]($online -and -not $stopping -and $remote -and -not $remote.stopping -and $remote.instance -eq $registry.instance)
        Instance = [string]$registry.instance
    }
}
function Write-LineLog([string]$Message) {
    $path = Join-Path $script:AppRoot 'instance\control.log'
    if ((Test-Path $path) -and (Get-Item $path).Length -gt 1MB) { Move-Item -LiteralPath $path -Destination "$path.1" -Force }
    Add-Content -LiteralPath $path -Value "$(Get-Date -Format s) $Message" -Encoding UTF8
}
function Start-LineProcess($Registry) {
    $runner = Join-Path $script:AppRoot 'control_runtime.py'
    foreach ($suffix in @('out', 'error')) {
        $log = Join-Path $script:AppRoot "instance\service.$suffix.log"
        if (Test-Path $log) { Move-Item -LiteralPath $log -Destination "$log.1" -Force }
    }
    $process = Start-Process -FilePath $script:Python -ArgumentList "`"$runner`" --instance $($Registry.instance) --port $script:Port --admin-port $script:AdminPort" -WorkingDirectory $script:AppRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $script:AppRoot 'instance\service.out.log') -RedirectStandardError (Join-Path $script:AppRoot 'instance\service.error.log')
    for ($attempt = 0; $attempt -lt 10; $attempt++) {
        # A Windows venv may create a child interpreter. Record both identities.
        $processes = @(Get-CimInstance Win32_Process -Filter "ProcessId=$($process.Id) OR ParentProcessId=$($process.Id)")
        foreach ($item in $processes) {
            if ($item.ExecutablePath -and $item.CommandLine -and $item.CommandLine.Contains($runner) -and
                $item.CommandLine.Contains($Registry.instance) -and -not @($Registry.processes | Where-Object { $_.id -eq $item.ProcessId }).Count) {
                $Registry.processes = @($Registry.processes) + [pscustomobject]@{
                    id = $item.ProcessId; executable = $item.ExecutablePath
                    created = $item.CreationDate.ToUniversalTime().Ticks.ToString(); command = $item.CommandLine
                }
                Save-LineRegistry $Registry
            }
        }
        Start-Sleep -Milliseconds 150
    }
}
function Invoke-LineAction {
    param([ValidateSet('Start','Stop','Restart')][string]$Action, [int]$TimeoutSeconds = 30)
    $mutex = New-Object System.Threading.Mutex($false, "Local\LINEAutomationControl$script:Port")
    $locked = $false
    $fileLock = $null
    $null = New-Item -ItemType Directory -Path (Join-Path $script:AppRoot 'instance') -Force
    try {
        try { $locked = $mutex.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $locked = $true }
        if (-not $locked) { throw 'LINE：另一個控制台正在操作，請稍候。' }
        try { $fileLock = [IO.File]::Open((Join-Path $script:AppRoot 'instance\control.lock'), 'OpenOrCreate', 'ReadWrite', 'None') }
        catch { throw 'LINE：另一個控制台正在操作，請稍候。' }
        Write-LineLog "操作開始：$Action"
        $registry = Get-LineRegistry
        $registry.processes = @($registry.processes | Where-Object { Test-LineIdentity $_ })
        if ($Action -in @('Stop','Restart')) {
            if ($registry.processes.Count) {
                # Local filesystem signal only. No remotely callable shutdown endpoint.
                $instance = ([guid]$registry.instance).ToString()
                $null = New-Item -ItemType File -Path (Join-Path $script:AppRoot "instance\stop-$instance") -Force
                $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
                while (@($registry.processes | Where-Object { Test-LineIdentity $_ }).Count) {
                    if ((Get-Date) -ge $deadline) { throw 'LINE：停止逾時，已保留程序；等待處理完成後再查看狀態。' }
                    Start-Sleep -Milliseconds 250
                }
                $registry.processes = @()
                Save-LineRegistry $registry
            }
            if (Get-NetTCPConnection -LocalPort $script:Port -State Listen -ErrorAction SilentlyContinue) {
                throw 'LINE：連接埠由其他程序使用；請由原啟動方式停止，控制台不會接管。'
            }
            Write-LineLog 'LINE 服務已停止；Cloudflare Tunnel 保持原狀。'
        }
        if ($Action -in @('Start','Restart')) {
            if (-not (Get-LineConfiguration)) { throw 'LINE：Python 環境未就緒，請重新執行 Install-ControlPanel.ps1。' }
            if (-not $registry.processes.Count) {
                if ($script:AdminPort -gt 0 -and (Get-NetTCPConnection -LocalPort $script:AdminPort -State Listen -ErrorAction SilentlyContinue)) {
                    throw 'LINE：本機管理頁連接埠已被占用，請先確認其他程序。'
                }
                if (Get-NetTCPConnection -LocalPort $script:Port -State Listen -ErrorAction SilentlyContinue) {
                    throw 'LINE：連接埠由其他程序使用；請由原啟動方式停止，控制台不會接管。'
                }
                $registry.instance = [guid]::NewGuid().ToString()
                Save-LineRegistry $registry
                Start-LineProcess $registry
            }
            $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
            do {
                $state = Get-LineStatus
                if ($state.Local -and -not $state.Stopping) { break }
                if (-not $state.Managed) { throw 'LINE：啟動失敗，請檢查設定、資料庫權限及連接埠。' }
                Start-Sleep -Milliseconds 250
            } while ((Get-Date) -lt $deadline)
            if (-not $state.Local -or $state.Stopping) { throw 'LINE：服務尚未就緒或仍在停止中，請稍後檢查狀態。' }
            Write-LineLog 'LINE 本機服務已啟動；公開連線由控制台另行檢查。'
            return 'LINE 本機服務已啟動；請確認公開連線狀態。'
        }
        return 'LINE 服務已停止；Cloudflare Tunnel 保持原狀。'
    } catch {
        Write-LineLog '操作未完成，請檢查控制台狀態與設定。'
        throw
    } finally {
        if ($fileLock) { $fileLock.Dispose() }
        if ($locked) { $mutex.ReleaseMutex() }
        $mutex.Dispose()
    }
}
Export-ModuleMember -Function Get-LineStatus, Invoke-LineAction
