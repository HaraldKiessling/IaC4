#!/usr/bin/env pwsh
# Feature: Code-Server (Phase 2d, Issue #65) – Traefik-Router /code + TS-TLS
# Verifiziert: HTTPS <fqdn>/code/ -> Login-Seite (Auth greift, TS-TLS-Terminierung),
# Port 8443 von aussen dicht (kein ports:-Publish), Container Up + Image-Pin (ADR-017),
# Extension-Infrastruktur (install-extension, /config/extensions), Sudo + Init-Konvention
# (LinuxServer-Image: abc in sudo-Gruppe, /config/custom-cont-init.d).
# Hinweis: curl -k auf dem Runner (Tailscale-CA ist keine oeffentliche CA);
# MagicDNS fehlt auf Runnern -> --resolve auf die Tailscale-IP (VpsIp).
param(
    [Parameter(Mandatory)][string]$VpsIp,
    [Parameter(Mandatory)][string]$VpsUser,
    [Parameter(Mandatory)][string]$SshKeyPath,
    [Parameter(Mandatory)][string]$PublicIp,
    [Parameter(Mandatory)][string]$ExpectedHostname,
    [Parameter(Mandatory)][string]$Tailnet,
    # Pin – SSoT: ansible/group_vars/all.yml code_server_version (Update = PR + Deploy)
    [string]$ExpectedImageVersion = "4.131.0-ls354"
)

. "$PSScriptRoot/bdd-lib.ps1"

# TS_TAILNET enthaelt bereits ".ts.net" (GitHub-Secret) -> FQDN robust bauen
if ($Tailnet -match '\.ts\.net$') { $Fqdn = "$ExpectedHostname.$Tailnet" } else { $Fqdn = "$ExpectedHostname.$Tailnet.ts.net" }

Write-Host "Feature: Code-Server (Phase 2d) – Target: $Fqdn" -ForegroundColor Cyan

# ── C1: HTTPS <fqdn>/code/ antwortet mit Login-Seite (Auth greift) ──
Write-Host "`nScenario: Code-Server via Traefik erreichbar – Auth greift (Login-Seite)" -ForegroundColor Yellow
Given "Router: Host(<fqdn>) && PathPrefix(/code) + stripprefix /code auf web-EntryPoint (TS-Serve-TLS)"
$resp = @(& curl -skL --connect-timeout 8 --resolve "${Fqdn}:443:${VpsIp}" -w "`n%{http_code}" "https://${Fqdn}/code/" 2>&1)
$respJoined = $resp -join "`n"
$code = ($respJoined -split "`n")[-1].Trim()
When "HTTPS-GET auf https://${Fqdn}/code/ ausgefuehrt wird (Runner im Tailnet, Redirects gefolgt)"
Then-True "HTTP 200 (Login-Seite, war: $code)" ($code -eq '200') $code
Then-True "Auth greift – Login-Formular verlangt Passwort (Body enthaelt 'password')" ($respJoined -match 'password') $respJoined

# ── C2: Port 8443 von aussen (Public-IP) dicht (kein Host-Port-Publish) ──
Write-Host "`nScenario: Code-Server-Port 8443 ist von aussen nicht erreichbar" -ForegroundColor Yellow
Given "Kein ports:-Publish (kein 8443:8443); code-server nur intern im traefik-network (Harald-Entscheidung 2026-08-01)"
$ports = @('8443')
$ext = @()
foreach ($port in $ports) {
    $code8443 = & curl -s --connect-timeout 4 -o /dev/null -w '%{http_code}' "http://${PublicIp}:${port}/" 2>&1
    & timeout 3 bash -c "echo > /dev/tcp/$PublicIp/$port" 2>$null
    $tcp = if ($LASTEXITCODE -eq 0) { 'OPEN' } else { 'closed' }
    $ext += "$port=$($code8443.Trim())/$tcp"
}
$extJoined = $ext -join ', '
When "die Public-IP-Ports vom Runner (Internet) abgerufen werden"
Then-True "Kein HTTP-Response und TCP dicht: $extJoined" ($extJoined -notmatch '=(200|4\d\d|5\d\d)' -and $extJoined -notmatch 'OPEN') $extJoined

# ── C3: Container Up + Image-Pin (ADR-017) ──
Write-Host "`nScenario: Code-Server-Container laeuft mit gepinntem Image" -ForegroundColor Yellow
Given "ADR-017: Image lscr.io/linuxserver/code-server:$ExpectedImageVersion (= code_server_version)"
$r = Invoke-SSH "sudo docker ps --filter name=^code-server$ --format '{{.Image}}|{{.Status}}'" $VpsUser $VpsIp $SshKeyPath
When "docker ps fuer code-server abgefragt wird"
Then-True "Container ist Up" ($r.Output -match 'Up') $r.Output
Then-True "Image-Tag = Pin $ExpectedImageVersion" ($r.Output -match [regex]::Escape("code-server:$ExpectedImageVersion")) $r.Output

# ── C4: install-extension + /config/extensions (read-only-Checks) ──
Write-Host "`nScenario: Extension-Infrastruktur vorhanden (install-extension, /config/extensions)" -ForegroundColor Yellow
Given "LinuxServer-Image: /usr/local/bin/install-extension; /config/extensions persistiert (Named Volume code-server-data)"
$r = Invoke-SSH "sudo docker exec code-server sh -c 'test -x /usr/local/bin/install-extension && echo OK_IE; test -d /config/extensions && test -w /config/extensions && echo OK_EXT'" $VpsUser $VpsIp $SshKeyPath
When "die Extension-Pfade im Container geprueft werden (read-only)"
Then-True "install-extension vorhanden und ausfuehrbar" ($r.Output -match 'OK_IE') $r.Output
Then-True "/config/extensions existiert und ist beschreibbar" ($r.Output -match 'OK_EXT') $r.Output

# ── C5: sudo-Mechanik (LinuxServer: sudoers.d-Datei, NICHT sudo-Gruppe) + custom-cont-init.d ──
Write-Host "`nScenario: Sudo fuer abc (sudoers.d-Mechanik) + custom-cont-init.d (LinuxServer-Konvention)" -ForegroundColor Yellow
Given "SUDO_PASSWORD gesetzt -> /etc/sudoers.d/abc; custom-cont-init.d wird beim Start ausgefuehrt (nur wenn vorhanden)"
$r = Invoke-SSH "sudo docker exec code-server sh -c 'test -n `"`$SUDO_PASSWORD`" && echo OK_ENV; test -f /etc/sudoers.d/abc && echo OK_SUDOERS; sudo -n -l -U abc >/dev/null 2>&1 && echo OK_SUDO_L; test -d /config/custom-cont-init.d && echo OK_INIT'" $VpsUser $VpsIp $SshKeyPath
When "SUDO_PASSWORD-Env, sudoers.d und Init-Verzeichnis im Container geprueft werden (read-only)"
Then-True "SUDO_PASSWORD-Env ist durchgereicht (Secret im Container)" ($r.Output -match 'OK_ENV') $r.Output
Then-True "sudo aktiv (maßgeblich: sudo -n -l -U abc liefert Regeln; sudoers.d-Datei als Diagnose)" ($r.Output -match 'OK_SUDO_L') $r.Output
Then-True "/config/custom-cont-init.d existiert (Rolle legt es an, BDD-Befund 2026-08-04)" ($r.Output -match 'OK_INIT') $r.Output
