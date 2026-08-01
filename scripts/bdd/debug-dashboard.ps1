#!/usr/bin/env pwsh
# DEBUG (temporär, 2026-08-01) – Dashboard-Diagnose: DNS/TLS vom Runner, Serve-Status,
# Whitelist-Verhalten, Traefik-Log. Schreibt nur Infos, keine Failures.
param(
    [Parameter(Mandatory)][string]$VpsIp,
    [Parameter(Mandatory)][string]$VpsUser,
    [Parameter(Mandatory)][string]$SshKeyPath,
    [Parameter(Mandatory)][string]$ExpectedHostname,
    [Parameter(Mandatory)][string]$Tailnet
)
. "$PSScriptRoot/bdd-lib.ps1"

# TS_TAILNET enthaelt bereits ".ts.net" (GitHub-Secret) -> FQDN robust bauen
if ($Tailnet -match '\.ts\.net$') { $Fqdn = "$ExpectedHostname.$Tailnet" } else { $Fqdn = "$ExpectedHostname.$Tailnet.ts.net" }
Write-Host "`n════ DIAGNOSE Dashboard ($Fqdn) ════" -ForegroundColor Magenta

Write-Host "`n[1] Runner-DNS (MagicDNS):"
$dns = & getent hosts $Fqdn 2>&1
Write-Host "  $($dns -join ' ')"

Write-Host "`n[2] Runner curl -v https mit --resolve (TLS/Connect):"
$v = & curl -sv --connect-timeout 8 --resolve "${Fqdn}:443:${VpsIp}" -o /dev/null "https://$Fqdn/dashboard/" 2>&1
$v | Select-String -Pattern 'Trying|Connected|SSL connection|HTTP/|refused|timed out|Could not|error|alert' | ForEach-Object { if ($_.Line) { Write-Host "  $($_.Line.Trim())" } }

Write-Host "`n[2b] Tailscale-API: httpsCertsEnabled? (Tailnet-weit)"
$api = & curl -sS --max-time 15 "https://api.tailscale.com/api/v2/tailnet/$env:TS_TAILNET/dns/config" -H "Authorization: Bearer $env:TS_TOKEN" 2>&1
try { $cfg = $api | ConvertFrom-Json; Write-Host "  magicDnsEnabled=$($cfg.magicDnsEnabled) httpsCertsEnabled=$($cfg.httpsCertsEnabled)" } catch { Write-Host "  API-Fehler: $api" }

Write-Host "`n[3] VPS tailscale serve status:"
$r = Invoke-SSH "sudo tailscale serve status" $VpsUser $VpsIp $SshKeyPath
Write-Host "  $($r.Output -replace "`n", "`n  ")"

Write-Host "`n[4] VPS localhost:8080 (Code+remote_ip):"
$r2 = Invoke-SSH "curl -s -o /dev/null -w 'code=%{http_code} remote=%{remote_ip}' http://127.0.0.1:8080/dashboard/" $VpsUser $VpsIp $SshKeyPath
Write-Host "  $($r2.Output)"

Write-Host "`n[5] VPS HTTPS via Serve (localhost:443):"
$r3 = Invoke-SSH "curl -sk -o /dev/null -w 'code=%{http_code}' https://127.0.0.1/dashboard/" $VpsUser $VpsIp $SshKeyPath
Write-Host "  $($r3.Output)"

Write-Host "`n[6] Traefik-Log (error/warn, letzte 6):"
$r4 = Invoke-SSH "sudo docker logs traefik --tail 40 2>&1 | grep -iE 'error|warn' | tail -6" $VpsUser $VpsIp $SshKeyPath
Write-Host "  $($r4.Output -replace "`n", "`n  ")"

Write-Host "`n[7] Gerenderte Traefik-Config auf VPS:"
$r5 = Invoke-SSH "sudo cat /opt/traefik/config/config.yml" $VpsUser $VpsIp $SshKeyPath
Write-Host "  $($r5.Output -replace "`n", "`n  ")"


Write-Host "`n[8] VPS tailscale version:"
$r8 = Invoke-SSH "tailscale version" $VpsUser $VpsIp $SshKeyPath
Write-Host "  $($r8.Output -replace "`n", " | ")"

Write-Host "`n[9] VPS tailscaled-Log (cert/serve/error, letzte 30):"
$r9 = Invoke-SSH "sudo journalctl -u tailscaled --since '30 min ago' --no-pager 2>/dev/null | grep -iE 'cert|serve|tls|error' | tail -15" $VpsUser $VpsIp $SshKeyPath
Write-Host "  $($r9.Output -replace "`n", "`n  ")"

Write-Host "`n[10] VPS manueller tailscale cert-Versuch (FQDN):"
$r10 = Invoke-SSH "sudo tailscale cert --cert-file=/tmp/ts-test.crt --key-file=/tmp/ts-test.key $Fqdn; echo EXIT=\$?" $VpsUser $VpsIp $SshKeyPath
Write-Host "  $($r10.Output -replace "`n", "`n  ")"

Write-Host "`n[11] VPS serve status --json (Zertifikat-Felder):"
$r11 = Invoke-SSH "sudo tailscale serve status --json | jq -c '.ServeConfig | {TCP, Web}' 2>/dev/null || sudo tailscale serve status --json | head -40" $VpsUser $VpsIp $SshKeyPath
Write-Host "  $($r11.Output -replace "`n", "`n  ")"

Write-Host "`n[12] Runner: Root + /dashboard/ + /dashboard (ohne Slash), mit Headern:"
foreach ($path in @('/', '/dashboard/', '/dashboard')) {
    $h = @(& curl -sk --connect-timeout 8 --resolve "${Fqdn}:443:${VpsIp}" -D - -o /dev/null "https://$Fqdn$path" 2>&1)
    if ($h.Count -eq 0) { $h = @('(keine Antwort)') }
    $code = ($h -join "`n" -split "`n")[0].Trim()
    $srvM = $h | Select-String -Pattern '^server:' | Select-Object -First 1
    $locM = $h | Select-String -Pattern '^location:' | Select-Object -First 1
    $srv = if ($srvM) { $srvM.Line.Trim() } else { '-' }
    $loc = if ($locM) { $locM.Line.Trim() } else { '-' }
    Write-Host "  $path -> $code | $srv | $loc"
}

Write-Host "`n[13] VPS localhost:8080/dashboard/ (ohne Middleware -> 200 erwartet):"
$r13 = Invoke-SSH "curl -s -o /dev/null -w 'code=%{http_code} ctype=%{content_type}' http://127.0.0.1:8080/dashboard/" $VpsUser $VpsIp $SshKeyPath
Write-Host "  $($r13.Output)"

Write-Host "`n[14] VPS serve status --json (roh, komplett):"
$r14 = Invoke-SSH "sudo tailscale serve status --json" $VpsUser $VpsIp $SshKeyPath
Write-Host "  $($r14.Output -replace "`n", "`n  ")"
Write-Host "`n════ DIAGNOSE ENDE ════" -ForegroundColor Magenta
