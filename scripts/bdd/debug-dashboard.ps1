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

$Fqdn = "$ExpectedHostname.$Tailnet.ts.net"
Write-Host "`n════ DIAGNOSE Dashboard ($Fqdn) ════" -ForegroundColor Magenta

Write-Host "`n[1] Runner-DNS (MagicDNS):"
$dns = & getent hosts $Fqdn 2>&1
Write-Host "  $($dns -join ' ')"

Write-Host "`n[2] Runner curl -v https (TLS/Connect):"
$v = & curl -sv --connect-timeout 8 -o /dev/null "https://$Fqdn/dashboard/" 2>&1
$v | Select-String -Pattern 'Trying|Connected|SSL connection|HTTP/|refused|timed out|Could not|error' | ForEach-Object { Write-Host "  $($_.Line.Trim())" }

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

Write-Host "`n════ DIAGNOSE ENDE ════" -ForegroundColor Magenta
