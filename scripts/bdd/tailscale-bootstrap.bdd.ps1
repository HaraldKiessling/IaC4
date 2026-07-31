#!/usr/bin/env pwsh
# Feature: Tailscale-Bootstrap (Workflow 02)
# Verifiziert: VPS im Tailnet (online, tag:ia3), SSH via Tailscale erreichbar, Public-SSH geschlossen.
param(
    [Parameter(Mandatory)][string]$VpsIp,        # Tailscale-IP (100.x)
    [Parameter(Mandatory)][string]$VpsUser,      # z.B. deploy-user
    [Parameter(Mandatory)][string]$SshKeyPath,   # Pfad zum privaten SSH-Key
    [Parameter(Mandatory)][string]$PublicIp,     # Public-IP des VPS
    [Parameter(Mandatory)][string]$Tailnet,      # z.B. tailcfea8a.ts.net
    [Parameter(Mandatory)][string]$ApiKey,       # Tailscale-API-Key
    [Parameter(Mandatory)][string]$ExpectedHostname # z.B. vps-dev
)

. "$PSScriptRoot/bdd-lib.ps1"

Write-Host "Feature: Tailscale-Bootstrap (Workflow 02) – Target: $ExpectedHostname" -ForegroundColor Cyan

# ── Szenario 1: SSH via Tailscale erreichbar ──
Write-Host "`nScenario: SSH via Tailscale erreichbar" -ForegroundColor Yellow
Given "Workflow 02 (Tailscale Bootstrap) ist erfolgreich gelaufen"
Given "Runner ist im Tailnet (tag:ci) und kennt die Tailscale-IP $VpsIp"
$r = Invoke-SSH "hostname" $VpsUser $VpsIp $SshKeyPath
When "SSH als $VpsUser auf $VpsIp ausgeführt wird"
Then-True "SSH-Verbindung erfolgreich (Exit 0)" ($r.ExitCode -eq 0) $r.Output
Write-Host "        Info: OS-Hostname ist $($r.Output.Trim()) (nicht assertiert – Tailscale-Name ist die Soll-Quelle)" -ForegroundColor DarkGray

$r2 = Invoke-SSH "tailscale status --json" $VpsUser $VpsIp $SshKeyPath
When "der Tailscale-Node-Name (Self.DNSName) abgefragt wird"
if ($r2.ExitCode -eq 0) {
    try {
        $ts = $r2.Output | ConvertFrom-Json
        $dns = $ts.Self.DNSName
        Then-True "Tailscale-Node ist $ExpectedHostname" ($dns -like "$ExpectedHostname*") $dns
    }
    catch {
        Then-True "Tailscale-Node ist $ExpectedHostname" $false "JSON-Parsing fehlgeschlagen: $($_.Exception.Message)"
    }
}
else {
    Then-True "Tailscale-Node ist $ExpectedHostname" $false $r2.Output
}

$r3 = Invoke-SSH "tailscale ip -4" $VpsUser $VpsIp $SshKeyPath
When "tailscale ip -4 auf dem VPS ausgeführt wird"
Then-True "Tailscale-IPv4 gemeldet (100.x)" ($r3.Output -match '^100\.\d+\.\d+\.\d+') $r3.Output

# ── Szenario 2: Public-SSH geschlossen (SSH-Restrict) ──
Write-Host "`nScenario: SSH auf Public-IP ist geschlossen (SSH-Restrict, UFW)" -ForegroundColor Yellow
Given "Phase 2b (SSH-Restrict) hat UFW auf der Public-IP aktiviert"
Given "Public-IP ist $PublicIp"
When "SSH auf $PublicIp:22 versucht wird"
Then-True "Verbindung fehlgeschlagen (Port 22 dicht)" (Test-SshPortClosed $VpsUser $PublicIp $SshKeyPath)

# ── Szenario 3: Node online und korrekt getaggt ──
Write-Host "`nScenario: VPS-Node ist online und mit tag:ia3 getaggt" -ForegroundColor Yellow
Given "Tailscale-API-Key ist verfügbar"
$devices = $null
try {
    $devices = Invoke-RestMethod -Uri "https://api.tailscale.com/api/v2/tailnet/$Tailnet/devices?fields=hostname,tags,online,lastSeen" `
        -Headers @{ Authorization = "Bearer $ApiKey" } -TimeoutSec 20
}
catch {
    Write-Host "  ❌ Tailscale-API nicht erreichbar: $($_.Exception.Message)" -ForegroundColor Red
}
When "die Tailscale-API nach dem Node $ExpectedHostname befragt wird"
if ($devices) {
    $node = $devices.devices | Where-Object { $_.hostname -eq $ExpectedHostname -or $_.hostname -eq "$ExpectedHostname-1" } | Select-Object -First 1
    Then-True "Node $ExpectedHostname existiert" ($null -ne $node)
    if ($node) {
        if ($null -eq $node.online) {
            # CI-Key liefert online ggf. nicht (Workflow-02-Kommentar) → lastSeen-Frische als Proxy
            $fresh = $false
            if ($node.lastSeen) {
                try { $fresh = ((Get-Date).ToUniversalTime() - [DateTime]$node.lastSeen).TotalMinutes -lt 10 }
                catch { $fresh = $false }
            }
            Then-True "Node ist online (Proxy: lastSeen < 10 min)" $fresh "lastSeen=$($node.lastSeen)"
        }
        else {
            Then-True "Node ist online" ($node.online -eq $true) "online=$($node.online)"
        }
        Then-True "Node trägt tag:ia3" (($node.tags -join ",") -match 'tag:ia3') ($node.tags -join ",")
    }
}
else {
    Then-True "Node $ExpectedHostname existiert" $false "API-Antwort leer"
}
