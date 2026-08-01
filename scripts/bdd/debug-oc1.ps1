#!/usr/bin/env pwsh
# DEBUG (temporär): OC1-Container-Diagnose
param(
    [Parameter(Mandatory)][string]$VpsIp,
    [Parameter(Mandatory)][string]$VpsUser,
    [Parameter(Mandatory)][string]$SshKeyPath
)
. "$PSScriptRoot/bdd-lib.ps1"

Write-Host "`n════ DIAGNOSE OC1 ════" -ForegroundColor Magenta

Write-Host "`n[1] docker ps -a (openclaw):"
$r = Invoke-SSH "sudo docker ps -a --filter name=openclaw --format '{{.Names}}|{{.Status}}|{{.Image}}'" $VpsUser $VpsIp $SshKeyPath
Write-Host "  $($r.Output -replace "`n", "`n  ")"

Write-Host "`n[2] docker logs openclaw-oc1 (tail 60):"
$r = Invoke-SSH "sudo docker logs openclaw-oc1 --tail 60 2>&1" $VpsUser $VpsIp $SshKeyPath
Write-Host "  $($r.Output -replace "`n", "`n  ")"

Write-Host "`n[3] Config-Struktur (Werte maskiert):"
$r = Invoke-SSH "sudo python3 -c \"import json;d=json.load(open('/srv/openclaw/oc1/config/openclaw.json'));print(json.dumps(d,indent=1)[:2000])\" 2>&1" $VpsUser $VpsIp $SshKeyPath
$masked = $r.Output -replace '(?i)(apiKey|token|botToken)\s*:\s*"[^"]{4}[^"]*"', '$1: "****(maskiert)"'
Write-Host "  $($masked -replace "`n", "`n  ")"

Write-Host "`n[4] Volume-Berechtigungen:"
$r = Invoke-SSH "sudo ls -la /srv/openclaw/oc1/ /srv/openclaw/oc1/config/ | head -12" $VpsUser $VpsIp $SshKeyPath
Write-Host "  $($r.Output -replace "`n", "`n  ")"

Write-Host "`n════ DIAGNOSE ENDE ════" -ForegroundColor Magenta
