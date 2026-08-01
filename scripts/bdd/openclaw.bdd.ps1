#!/usr/bin/env pwsh
# Feature: OpenClaw-Gateways (Phase 2e, ADR-025 revidiert) – Docker-Container, Multi-Instanz
# Verifiziert: Health je Instanz via HTTPS (TS-Serve-TLS), Ports von außen dicht,
# openclaw.json je Instanz (SSoT), Instanz-Liste (OC1/OC2 aktiv, OC3 geplant).
# MagicDNS fehlt auf GH-Runnern -> --resolve auf die Tailscale-IP (VpsIp).
param(
    [Parameter(Mandatory)][string]$VpsIp,
    [Parameter(Mandatory)][string]$VpsUser,
    [Parameter(Mandatory)][string]$SshKeyPath,
    [Parameter(Mandatory)][string]$PublicIp,
    [Parameter(Mandatory)][string]$ExpectedHostname,
    [Parameter(Mandatory)][string]$Tailnet,
    [string]$Instances = "oc1,oc2",
    [string]$DisabledInstances = "oc3"
)

. "$PSScriptRoot/bdd-lib.ps1"

# TS_TAILNET enthaelt bereits ".ts.net" (GitHub-Secret) -> FQDN robust bauen
if ($Tailnet -match '\.ts\.net$') { $Fqdn = "$ExpectedHostname.$Tailnet" } else { $Fqdn = "$ExpectedHostname.$Tailnet.ts.net" }

Write-Host "Feature: OpenClaw-Gateways (Phase 2e) – Target: $Fqdn" -ForegroundColor Cyan

# Instanz -> Port (SSoT: group_vars/all.yml openclaw_instances)
$instPorts = @{ oc1 = 18789; oc2 = 18790; oc3 = 18791 }

# ── O1: Health je aktiver Instanz via HTTPS (TS-Serve-TLS) ──
foreach ($inst in $Instances.Split(',')) {
    $inst = $inst.Trim()
    $port = $instPorts[$inst]
    Write-Host "`nScenario: Instanz $inst – Health via HTTPS (TS-TLS, Port $port)" -ForegroundColor Yellow
    Given "Gateway-Container openclaw-$inst laeuft; TS-Serve terminiert TLS auf $port"
    $code = & curl -sk --connect-timeout 8 --resolve "${Fqdn}:${port}:${VpsIp}" -o /dev/null -w '%{http_code}' "https://$Fqdn:$port/" 2>&1
    When "HTTPS-GET auf https://$Fqdn:$port/ ausgefuehrt wird (Runner im Tailnet)"
    Then-True "HTTP 200 (war: $code)" ($code.Trim() -eq '200') $code
}

# ── O2: Ports von aussen (Public-IP) dicht ──
Write-Host "`nScenario: Gateway-Ports sind von aussen nicht erreichbar" -ForegroundColor Yellow
Given "DOCKER-USER + UFW: Gateway-Ports nur localhost + TS-Serve (tailnet only)"
$ports = @('18789', '18790', '18791')
$ext = @()
foreach ($port in $ports) {
    $code = & curl -s --connect-timeout 4 -o /dev/null -w '%{http_code}' "http://$PublicIp:$port/" 2>&1
    & timeout 3 bash -c "echo > /dev/tcp/$PublicIp/$port" 2>$null
    $tcp = if ($LASTEXITCODE -eq 0) { 'OPEN' } else { 'closed' }
    $ext += "$port=$($code.Trim())/$tcp"
}
$extJoined = $ext -join ', '
When "die Public-IP-Ports vom Runner (Internet) abgerufen werden"
Then-True "Kein HTTP-Response und TCP dicht: $extJoined" ($extJoined -notmatch '=(200|4\d\d|5\d\d)' -and $extJoined -notmatch 'OPEN') $extJoined

# ── O3: Instanz-Konfiguration (openclaw.json) existiert je aktiver Instanz ──
foreach ($inst in $Instances.Split(',')) {
    $inst = $inst.Trim()
    Write-Host "`nScenario: Instanz $inst – openclaw.json (SSoT) vorhanden" -ForegroundColor Yellow
    Given "Rolle deployt openclaw.json je Instanz (Config-Volume)"
    $r = Invoke-SSH "sudo test -f /srv/openclaw/$inst/config/openclaw.json && echo OK" $VpsUser $VpsIp $SshKeyPath
    When "die Config-Datei auf dem VPS geprueft wird"
    Then-True "openclaw.json existiert" ($r.Output -match 'OK') $r.Output
}

# ── O4: Geplante Instanz nicht deployed (OC3 disabled) ──
foreach ($inst in $DisabledInstances.Split(',')) {
    $inst = $inst.Trim()
    Write-Host "`nScenario: Instanz $inst – nicht deployed (geplant)" -ForegroundColor Yellow
    Given "enabled=false in openclaw_instances (Harald 2026-08-01)"
    $r = Invoke-SSH "sudo docker ps --filter name=^openclaw-$inst$ --format '{{.Names}}'" $VpsUser $VpsIp $SshKeyPath
    When "docker ps fuer openclaw-$inst abgefragt wird"
    Then-True "Kein Container openclaw-$inst" ($r.Output -notmatch 'openclaw') $r.Output
}
