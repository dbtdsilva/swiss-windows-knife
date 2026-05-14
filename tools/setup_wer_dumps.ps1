# Enable Windows Error Reporting LocalDumps for SwissWindowsKnife.exe so the
# next native crash (Qt stack overflow, segfault, etc.) leaves a full minidump
# under %LOCALAPPDATA%\CrashDumps that can be opened in WinDbg. The LocalDumps
# key lives in HKLM, so this script must run elevated. Idempotent.

#Requires -RunAsAdministrator

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$exeKey = 'HKLM:\SOFTWARE\Microsoft\Windows\Windows Error Reporting\LocalDumps\SwissWindowsKnife.exe'
$dumpDir = '%LOCALAPPDATA%\CrashDumps'

if (-not (Test-Path $exeKey)) {
    New-Item -Path $exeKey -Force | Out-Null
}
New-ItemProperty -Path $exeKey -Name DumpFolder -PropertyType ExpandString -Value $dumpDir -Force | Out-Null
New-ItemProperty -Path $exeKey -Name DumpCount  -PropertyType DWord        -Value 5        -Force | Out-Null
New-ItemProperty -Path $exeKey -Name DumpType   -PropertyType DWord        -Value 2        -Force | Out-Null

$expanded = [Environment]::ExpandEnvironmentVariables($dumpDir)
Write-Host "Configured WER LocalDumps for SwissWindowsKnife.exe." -ForegroundColor Green
Write-Host "Future crash dumps will land in: $expanded"
