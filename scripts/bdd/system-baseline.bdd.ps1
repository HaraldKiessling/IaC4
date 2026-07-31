#!/usr/bin/env pwsh
# Feature: System-Baseline (Workflow 03, Phase 1)
# Verifiziert: Baseline-Pakete, Zeitzone, Swap, deploy-user-Sudo, UFW-Restrict (Regelreihenfolge).
param(
    [Parameter(Mandatory)][string]$VpsIp,       # Tailscale-IP (100.x)
    [Parameter(Mandatory)][string]$VpsUser,     # z.B. deploy-user
    [Parameter(Mandatory)][string]$SshKeyPath,  # Pfad zum privaten SSH-Key
    [Parameter(Mandatory)][string]$ExpectedTz = "Europe/Berlin"
)

. "$PSScriptRoot/bdd-lib.ps1"

Write-Host "Feature: System-Baseline (Workflow 03, Phase 1) – Target: $VpsIp" -ForegroundColor Cyan

# ── Szenario 1: Baseline-Pakete installiert ──
Write-Host "`nScenario: Baseline-Pakete sind installiert" -ForegroundColor Yellow
Given "Workflow 03 (Baseline Deploy) ist erfolgreich gelaufen"
$packages = @("curl", "wget", "htop", "ufw", "unzip", "fail2ban")
foreach ($pkg in $packages) {
    $r = Invoke-SSH "dpkg-query -W -f='`${Status}' $pkg" $VpsUser $VpsIp $SshKeyPath
    When "Paketstatus für $pkg abgefragt wird"
    Then-True "$pkg ist installiert" ($r.Output -match 'install ok installed') $r.Output
}

# ── Szenario 2: Zeitzone ──
Write-Host "`nScenario: Zeitzone ist $ExpectedTz" -ForegroundColor Yellow
Given "vps-baseline-Rolle hat die Zeitzone gesetzt"
$r = Invoke-SSH "timedatectl show -p Timezone --value" $VpsUser $VpsIp $SshKeyPath
When "die Zeitzone abgefragt wird"
Then-True "Zeitzone ist $ExpectedTz" ($r.Output.Trim() -eq $ExpectedTz) $r.Output

# ── Szenario 3: Swap aktiv ──
Write-Host "`nScenario: Swap-Datei ist aktiv" -ForegroundColor Yellow
Given "vps-baseline-Rolle hat /swapfile (2G) eingerichtet"
$r = Invoke-SSH "swapon --show" $VpsUser $VpsIp $SshKeyPath
When "swapon --show ausgeführt wird"
Then-True "/swapfile ist aktiv" ($r.Output -match '/swapfile') $r.Output

# ── Szenario 4: deploy-user mit sudo ──
Write-Host "`nScenario: deploy-user hat funktionierendes sudo" -ForegroundColor Yellow
Given "deploy-user ist in der sudoers (Ansible become)"
$r = Invoke-SSH "sudo -n true && echo SUDO_OK" $VpsUser $VpsIp $SshKeyPath
When "sudo -n true als $VpsUser ausgeführt wird"
Then-True "sudo ohne Passwort funktioniert" ($r.Output -match 'SUDO_OK') $r.Output

# ── Szenario 5: UFW aktiv, öffentliches SSH blockiert (Regelreihenfolge) ──
Write-Host "`nScenario: UFW aktiv – öffentliches SSH blockiert, keine generische Allow-Regel" -ForegroundColor Yellow
Given "cloud-config aktiviert UFW und setzt generisches allow ssh (Bootstrap-Zugang)"
$r = Invoke-SSH "sudo ufw status verbose" $VpsUser $VpsIp $SshKeyPath
When "ufw status verbose abgefragt wird"
Then-True "UFW ist aktiv (Status: active)" ($r.Output -match 'Status: active') $r.Output
Then-True "Keine generische Allow-Regel für Port 22 mehr (cloud-config-Regel gelöscht)" ($r.Output -notmatch '22/tcp\s+ALLOW IN\s+Anywhere') $r.Output
Then-True "Keine generische Allow-Regel für Port 22 (v6) mehr" ($r.Output -notmatch '22/tcp \(v6\)\s+ALLOW IN') $r.Output
Then-True "Deny-Regel auf öffentlichem Interface vorhanden" ($r.Output -match '22/tcp\s+DENY IN on ') $r.Output
Then-True "CGNAT-Allow für Tailscale (100.64.0.0/10) vorhanden (Defense-in-Depth)" ($r.Output -match '22/tcp\s+ALLOW IN\s+100\.64\.0\.0/10') $r.Output
