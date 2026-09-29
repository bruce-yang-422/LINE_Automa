# Temporary LINE service only; never controls Cloudflared or the real database.
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
$fixture = Join-Path ([IO.Path]::GetTempPath()) ('line-control-test-' + [guid]::NewGuid())
$appRoot = Join-Path $fixture 'line-oa-archive'
$null = New-Item -ItemType Directory -Path $appRoot -Force
foreach ($name in @('app.py','schema.sql','control_runtime.py','recipients.py','admin_server.py','line_api.py','send_image.py','remote_auth.py')) {
    Copy-Item -LiteralPath (Join-Path $repo "line-oa-archive\$name") -Destination $appRoot
}
Set-Content -LiteralPath (Join-Path $appRoot '.env') -Value "LINE_CHANNEL_SECRET=test-secret`nDATABASE_PATH=data/test.db" -Encoding UTF8
$listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, 0)
$listener.Start()
$port = $listener.LocalEndpoint.Port
$listener.Stop()
$module = Import-Module (Join-Path $repo 'ServiceControl.psm1') -Force -PassThru
try {
    & $module { param($root, $python, $port)
        $script:AppRoot = $root
        $script:Python = $python
        $script:Port = $port
        $script:AdminPort = 0
        $script:PublicUrl = "http://127.0.0.1:$port"
    } $appRoot (Join-Path $repo '.venv\Scripts\python.exe') $port
    $null = Invoke-LineAction Start
    $first = Get-Content -LiteralPath (Join-Path $appRoot 'instance\control-processes.json') -Raw | ConvertFrom-Json
    $null = Invoke-LineAction Start
    $second = Get-Content -LiteralPath (Join-Path $appRoot 'instance\control-processes.json') -Raw | ConvertFrom-Json
    if (($first.processes.id -join ',') -ne ($second.processes.id -join ',')) { throw 'Duplicate start created extra processes.' }
    $state = Get-LineStatus -Public
    if (-not ($state.Local -and $state.Public -and $state.Configured)) { throw 'Managed service is not healthy.' }
    & $module {
        $entry = (Get-LineRegistry).processes[0]
        $entry.created = '0'
        if (Test-LineIdentity $entry) { throw 'Mismatched identity accepted.' }
        $script:PublicUrl = 'http://127.0.0.1:1'
    }
    $state = Get-LineStatus -Public
    if ($state.Public -or -not $state.Local) { throw 'Public outage not reported independently.' }
    $null = Invoke-LineAction Restart
    $third = Get-Content -LiteralPath (Join-Path $appRoot 'instance\control-processes.json') -Raw | ConvertFrom-Json
    if ($third.instance -eq $first.instance) { throw 'Restart did not create a new instance.' }
    # Stop remains available even after settings are removed.
    Remove-Item -LiteralPath (Join-Path $appRoot '.env')
    $null = Invoke-LineAction Stop
    if ((Get-LineStatus).Managed) { throw 'Stop left managed processes alive.' }
    $null = Invoke-LineAction Stop
    # An unknown listener must neither be killed nor accepted as the managed service.
    $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, $port)
    $listener.Start()
    try {
        Set-Content -LiteralPath (Join-Path $appRoot '.env') -Value 'LINE_CHANNEL_SECRET=test-secret'
        foreach ($action in @('Start','Stop')) {
            $refused = $false
            try { $null = Invoke-LineAction $action } catch { $refused = $true }
            if (-not $refused) { throw "Unknown listener was accepted for $action." }
        }
    } finally { $listener.Stop() }
    'PASS: start, duplicate start, identity mismatch, public outage, restart, stop without settings, repeated stop, occupied port.'
} finally {
    # Cleanup only identities created by this isolated test.
    & $module {
        foreach ($entry in (Get-LineRegistry).processes) {
            if (Test-LineIdentity $entry) { Stop-Process -Id $entry.id -ErrorAction SilentlyContinue }
        }
    }
    $resolved = [IO.Path]::GetFullPath($fixture)
    $prefix = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\') + '\line-control-test-'
    if ($resolved.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) { Remove-Item -LiteralPath $resolved -Recurse -Force }
}
