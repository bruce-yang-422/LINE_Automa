param([int]$TimeoutSeconds = 30)
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'ServiceControl.psm1') -Force
Invoke-LineAction Stop -TimeoutSeconds $TimeoutSeconds
