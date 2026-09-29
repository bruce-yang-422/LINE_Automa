param([int]$TimeoutSeconds = 30)
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'ServiceControl.psm1') -Force
Invoke-LineAction Start -TimeoutSeconds $TimeoutSeconds
