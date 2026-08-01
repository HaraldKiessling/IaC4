#!/usr/bin/env pwsh
# Feature: Docker/Traefik/Ollama (Phase 2c/2d, ADR-015..024)
# Verifiziert: Docker-Installation (keine docker-Gruppe!), Shared Network, DOCKER-USER-Firewall,
# Traefik HTTP-only + Dashboard-Auth + UFW-CGNAT + Tailscale Serve, Ollama (API, Modell pre-warmed).
# Hinweis: Docker-Kommandos laufen via sudo (ADR-016: deploy-user hat KEINE docker-Gruppe;
# B4 beweist NOPASSWD-sudo).
param(
    [Parameter(Mandatory)][string]$VpsIp,
    [Parameter(Mandatory)][string]$VpsUser,
    [Parameter(Mandatory)][string]$SshKeyPath,
    [Parameter(Mandatory)][string]$PublicIp,
    [Parameter(Mandatory)][string]$ExpectedHostname,
    [Parameter(Mandatory)][string]$Tailnet,
    [string]$DockerNetwork = "traefik-network",
    [string]$OllamaModel = "nomic-embed-text"
)

. "$PSScriptRoot/bdd-lib.ps1"

Write-Host "Feature: Docker/Traefik/Ollama (Phase 2c/2d) – Target: $VpsIp" -ForegroundColor Cyan

# ── D1: Docker Engine + Compose installiert ──
Write-Host "`nScenario: Docker Engine + Compose-Plugin installiert (ADR-015)" -ForegroundColor Yellow
Given "docker-Rolle hat das offizielle Docker-Repo eingerichtet"
$r = Invoke-SSH "sudo docker version --format '{{.Server.Version}}'" $VpsUser $VpsIp $SshKeyPath
When "docker version abgefragt wird"
Then-True "Docker-Server antwortet" ($r.ExitCode -eq 0 -and $r.Output -match '^\d+\.\d+') $r.Output
$r = Invoke-SSH "docker compose version" $VpsUser $VpsIp $SshKeyPath
When "docker compose version abgefragt wird"
Then-True "Compose-Plugin vorhanden" ($r.ExitCode -eq 0 -and $r.Output -match 'v2') $r.Output

# ── D2: deploy-user NICHT in docker-Gruppe (ADR-016) ──
Write-Host "`nScenario: deploy-user hat keine docker-Gruppen-Mitgliedschaft (ADR-016)" -ForegroundColor Yellow
Given "ADR-016 verbietet docker-Gruppe (root-Äquivalent)"
$r = Invoke-SSH "id -nG $VpsUser" $VpsUser $VpsIp $SshKeyPath
When "die Gruppen von $VpsUser abgefragt werden"
Then-True "docker-Gruppe ist nicht enthalten" ($r.Output -notmatch '(^|\s)docker(\s|$)') $r.Output

# ── D3: Shared Network (ADR-015) ──
Write-Host "`nScenario: Shared Network $DockerNetwork existiert" -ForegroundColor Yellow
Given "docker-Rolle hat das Shared Network angelegt"
$r = Invoke-SSH "sudo docker network ls --format '{{.Name}}'" $VpsUser $VpsIp $SshKeyPath
When "docker network ls abgefragt wird"
Then-True "Network $DockerNetwork ist vorhanden" ($r.Output -match [regex]::Escape($DockerNetwork)) $r.Output

# ── D4: Traefik-Container läuft (gepinnt) ──
Write-Host "`nScenario: Traefik-Container läuft (ADR-017/018)" -ForegroundColor Yellow
Given "traefik-Rolle wurde deployed"
$r = Invoke-SSH "sudo docker ps --filter name=^traefik$ --format '{{.Image}}|{{.Status}}'" $VpsUser $VpsIp $SshKeyPath
When "docker ps für traefik abgefragt wird"
Then-True "Traefik-Container ist Up" ($r.Output -match 'traefik:') $r.Output

# ── D5: HTTP-only – kein 443-Listener außer tailscaled (ADR-018) ──
Write-Host "`nScenario: Traefik ist HTTP-only – kein 443-Listener außer tailscaled (ADR-018)" -ForegroundColor Yellow
Given "ADR-018 ersetzt LE/443 durch Tailscale Serve"
$r = Invoke-SSH "sudo ss -tlnp | grep ':443 ' | grep -v tailscaled || echo NO_443" $VpsUser $VpsIp $SshKeyPath
When "ss -tlnp auf Port 443 geprüft wird (tailscaled ausgenommen)"
Then-True "Kein 443-Listener außer tailscaled" ($r.Output -match 'NO_443') $r.Output

# ── D6: Dashboard-Auth greift (ADR-019) ──
Write-Host "`nScenario: Traefik-Dashboard verlangt Authentifizierung (ADR-019)" -ForegroundColor Yellow
Given "dashboard-Router hat BasicAuth-Middleware"
$r = Invoke-SSH "curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/dashboard/" $VpsUser $VpsIp $SshKeyPath
When "das Dashboard ohne Credentials abgerufen wird"
Then-True "HTTP 401 ohne Auth" ($r.Output.Trim() -eq '401') $r.Output

# ── D7: Firewall – UFW-CGNAT (R7-R9) + DOCKER-USER (R10/R11) ──
Write-Host "`nScenario: Firewall-Regeln für Service-Ports (Firewall-Konzept R7-R11)" -ForegroundColor Yellow
Given "Firewall-Konzept R7-R9 (UFW) und R10/R11 (DOCKER-USER, Docker-published Ports)"
$r = Invoke-SSH "sudo ufw status verbose" $VpsUser $VpsIp $SshKeyPath
When "ufw status verbose abgefragt wird"
Then-True "Port 80 CGNAT-Allow" ($r.Output -match '80/tcp\s+ALLOW\s+FROM\s+100\.64\.0\.0/10') $r.Output
Then-True "Port 8080 CGNAT-Allow" ($r.Output -match '8080/tcp\s+ALLOW\s+FROM\s+100\.64\.0\.0/10') $r.Output
Then-True "Port 11434 CGNAT-Allow" ($r.Output -match '11434/tcp\s+ALLOW\s+FROM\s+100\.64\.0\.0/10') $r.Output
$r = Invoke-SSH "sudo iptables -S DOCKER-USER" $VpsUser $VpsIp $SshKeyPath
When "iptables -S DOCKER-USER abgefragt wird"
Then-True "DOCKER-USER: CGNAT-ACCEPT für 80/8080/11434/6333/6334" ($r.Output -match '100\.64\.0\.0/10.*80,8080,11434,6333,6334.*ACCEPT') $r.Output
Then-True "DOCKER-USER: DROP interface-gebunden (nicht global)" ($r.Output -match '\-i\s+\S+.*80,8080,11434,6333,6334.*DROP') $r.Output

# ── D8: Tailscale Serve aktiv (ADR-018) ──
Write-Host "`nScenario: Tailscale Serve leitet HTTPS 443 → localhost:80 (ADR-018)" -ForegroundColor Yellow
Given "HTTPS-Certificates im Tailnet aktiviert (IaC3-Bestand)"
$r = Invoke-SSH "sudo tailscale serve status" $VpsUser $VpsIp $SshKeyPath
When "tailscale serve status abgefragt wird"
Then-True "Serve-Route auf localhost:80 vorhanden" ($r.Output -match 'localhost:80') $r.Output
Then-True "Serve-Mount /dashboard → localhost:8080" ($r.Output -match '/dashboard') $r.Output
Then-True "Serve-Mount /api → localhost:8080" ($r.Output -match '/api') $r.Output

# ── O1: Ollama-Container läuft, API antwortet (ADR-021) ──
Write-Host "`nScenario: Ollama-API ist erreichbar (ADR-021)" -ForegroundColor Yellow
Given "ollama-Rolle wurde deployed"
$r = Invoke-SSH "sudo docker ps --filter name=^ollama$ --format '{{.Status}}'" $VpsUser $VpsIp $SshKeyPath
When "docker ps für ollama abgefragt wird"
Then-True "Ollama-Container ist Up" ($r.Output -match 'Up') $r.Output
$r = Invoke-SSH "curl -fsS http://localhost:11434/api/tags" $VpsUser $VpsIp $SshKeyPath
When "GET /api/tags abgefragt wird"
Then-True "Ollama-API antwortet (HTTP 200)" ($r.ExitCode -eq 0) $r.Output

# ── O2: Modell pre-warmed (ADR-023) ──
Write-Host "`nScenario: Modell $OllamaModel ist geladen (ADR-023)" -ForegroundColor Yellow
Given "Pre-Warm-Entrypoint hat das Modell gepullt"
$r = Invoke-SSH "sudo docker exec ollama ollama list" $VpsUser $VpsIp $SshKeyPath
When "ollama list abgefragt wird"
Then-True "Modell $OllamaModel ist vorhanden" ($r.Output -match [regex]::Escape($OllamaModel)) $r.Output

# ── O3: Embedding-Request schnell (< 2s, Pre-Warm-Wirkung) ──
Write-Host "`nScenario: Erster Embedding-Request ist schnell (Pre-Warm, ADR-023)" -ForegroundColor Yellow
Given "Modell wurde beim Container-Start vorgewärmt"
# JSON-Body separat bauen – keine Backslash-Escapes im Remote-Kommando (PowerShell: \" ist KEIN Escape)
$body = '{"model":"' + $OllamaModel + '","prompt":"bdd-warmup"}'
$cmd = "curl -fsS -o /dev/null -w '%{http_code}|%{time_total}' -X POST http://localhost:11434/api/embeddings -H 'Content-Type: application/json' -d '$body'"
$r = Invoke-SSH $cmd $VpsUser $VpsIp $SshKeyPath
When "ein Embedding-Request ausgeführt wird"
$parts = $r.Output.Trim() -split '\|'
$http = if ($parts.Count -ge 1) { $parts[0] } else { '000' }
$secs = 99.0
if ($parts.Count -ge 2 -and $parts[1] -match '^\d+\.\d+') { $secs = [double]$parts[1] }
Then-True "HTTP 200 (war: $http)" ($http -eq '200') $r.Output
Then-True "Antwortzeit < 2s (war: ${secs}s)" ($secs -lt 2.0) $r.Output

# ── D9: Service-Ports vom Internet NICHT erreichbar (Wirkungs-Check, K1-1-Fix) ──
Write-Host "`nScenario: Service-Ports sind von außen (Public-IP) nicht erreichbar" -ForegroundColor Yellow
Given "DOCKER-USER-Regeln R10/R11 (interface-gebunden) sind aktiv"
$ext = @()
foreach ($port in @('80', '11434', '6333')) {
    $code = & curl -s --connect-timeout 4 -o /dev/null -w '%{http_code}' "http://$PublicIp:$port/" 2>&1
    $ext += "$port=$($code.Trim())"
}
$extJoined = $ext -join ', '
When "die Public-IP-Ports vom Runner (Internet) abgerufen werden"
Then-True "Kein HTTP-Response von außen (Timeout/Filtered): $extJoined" ($extJoined -notmatch '=(200|4\d\d|5\d\d)') $extJoined

# ── D10: Dashboard via HTTPS über das Tailnet (ADR-019, Erwartung Harald 2026-08-01) ──
Write-Host "`nScenario: Dashboard ist via HTTPS erreichbar (https://<fqdn>/dashboard/ → 401 ohne Auth)" -ForegroundColor Yellow
Given "Serve-Mounts /dashboard und /api → localhost:8080 (Traefik dashboard-EntryPoint)"
$Fqdn = "$ExpectedHostname.$Tailnet.ts.net"
$code = & curl -sk --connect-timeout 8 -o /dev/null -w '%{http_code}' "https://$Fqdn/dashboard/" 2>&1
When "HTTPS-GET auf https://$Fqdn/dashboard/ ausgeführt wird (Runner im Tailnet)"
Then-True "HTTP 401 ohne Auth (war: $code)" ($code.Trim() -eq '401') $code
