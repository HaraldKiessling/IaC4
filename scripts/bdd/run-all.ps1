#!/usr/bin/env pwsh
# run-all.ps1 – Führt alle Feature-Skripte (scripts/bdd/*.bdd.ps1) aus.
# Wird vom Workflow 04-bdd-tests.yml aufgerufen. Exit-Code 1 bei mind. einem fehlgeschlagenen Szenario.
# Konvention/Testkatalog: qa/bdd-testkonzept.md

param(
    [Parameter(Mandatory)][string]$VpsIp,
    [Parameter(Mandatory)][string]$VpsUser,
    [Parameter(Mandatory)][string]$SshKeyPath,
    [Parameter(Mandatory)][string]$PublicIp,
    [string]$Tailnet = $env:TS_TAILNET,
    [string]$ApiKey = $env:TS_API_KEY,
    [Parameter(Mandatory)][string]$ExpectedHostname,
    [string]$ExpectedTz = "Europe/Berlin"
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrEmpty($ApiKey)) { Write-Host "❌ TS_API_KEY fehlt (env) – Abbruch"; exit 1 }
if ([string]::IsNullOrEmpty($Tailnet)) { Write-Host "❌ TS_TAILNET fehlt (env) – Abbruch"; exit 1 }

Write-Host "═══ IaC4 BDD-Tests – Target: $ExpectedHostname ($VpsIp) ═══" -ForegroundColor Cyan
Write-Host "Start: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz')`n"

& "$PSScriptRoot/tailscale-bootstrap.bdd.ps1" -VpsIp $VpsIp -VpsUser $VpsUser -SshKeyPath $SshKeyPath `
    -PublicIp $PublicIp -Tailnet $Tailnet -ApiKey $ApiKey -ExpectedHostname $ExpectedHostname
& "$PSScriptRoot/system-baseline.bdd.ps1" -VpsIp $VpsIp -VpsUser $VpsUser -SshKeyPath $SshKeyPath -ExpectedTz $ExpectedTz

Write-Host "`n═══ Zusammenfassung ═══" -ForegroundColor Cyan
Write-Host "  ✅ Bestanden: $global:BDD_PASS"
Write-Host "  ❌ Fehlgeschlagen: $global:BDD_FAIL"
if ($global:BDD_FAILURES.Count -gt 0) {
    Write-Host "`nFehlgeschlagene Szenarien:" -ForegroundColor Red
    $global:BDD_FAILURES | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
}
Write-Host "Ende: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz')"
if ($global:BDD_FAIL -gt 0) { exit 1 } else { exit 0 }
