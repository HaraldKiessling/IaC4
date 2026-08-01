#!/usr/bin/env pwsh
# Feature: Qdrant (Phase 2d, ADR-011) – HTTPS auf 6333 via Tailscale-Serve-TLS
# Verifiziert: TLS-Terminierung durch TS (Zertifikat fuer MagicDNS-Name), /healthz,
# Collection zoocode-3072d (3072d, Cosine – RFC 0034b/#195, prod-SSoT).
# Hinweis: curl -k auf dem Runner (Tailscale-CA ist keine oeffentliche CA);
# Q2 (Subject-Check) liefert die eigentliche TLS-Evidenz. MagicDNS fehlt auf Runnern
# -> --resolve auf die Tailscale-IP (VpsIp).
param(
    [Parameter(Mandatory)][string]$VpsIp,
    [Parameter(Mandatory)][string]$VpsUser,
    [Parameter(Mandatory)][string]$SshKeyPath,
    [Parameter(Mandatory)][string]$ExpectedHostname,
    [Parameter(Mandatory)][string]$Tailnet,
    [string]$Collection = "zoocode-3072d"
)

. "$PSScriptRoot/bdd-lib.ps1"

# TS_TAILNET enthaelt bereits ".ts.net" (GitHub-Secret) -> FQDN robust bauen
if ($Tailnet -match '\.ts\.net$') { $Fqdn = "$ExpectedHostname.$Tailnet" } else { $Fqdn = "$ExpectedHostname.$Tailnet.ts.net" }
$Base = "https://${Fqdn}:6333"

Write-Host "Feature: Qdrant (Phase 2d) – Target: $Fqdn" -ForegroundColor Cyan

# ── Q1: HTTPS 6333 antwortet (TS-TLS-Terminierung) ──
Write-Host "`nScenario: Qdrant spricht HTTPS auf 6333 (Tailscale-Serve-TLS)" -ForegroundColor Yellow
Given "Tailscale Serve terminiert TLS auf 6333 (tailnet only), Qdrant bleibt HTTP"
$code = & curl -sk --connect-timeout 8 --resolve "${Fqdn}:6333:${VpsIp}" -o /dev/null -w '%{http_code}' "$Base/" 2>&1
When "HTTPS-GET auf $Base/ ausgefuehrt wird (Runner im Tailnet)"
Then-True "HTTP 200 ueber TLS (war: $code)" ($code.Trim() -eq '200') $code

# ── Q2: Zertifikat passt zum MagicDNS-Namen (Tailscale-CA, Terminierung durch TS) ──
Write-Host "`nScenario: TLS-Zertifikat ist fuer $Fqdn ausgestellt" -ForegroundColor Yellow
Given "Tailscale stellt Zertifikate nur fuer eigene MagicDNS-Namen aus"
$r = & openssl s_client -connect "${VpsIp}:6333" -servername $Fqdn 2>&1 | openssl x509 -noout -subject 2>&1
When "das Server-Zertifikat vom Runner inspiziert wird"
Then-True "Subject enthaelt $Fqdn" ($r -match [regex]::Escape($Fqdn)) $r

# ── Q3: Health-Endpoint /healthz liefert ok (Qdrant intern HTTP) ──
Write-Host "`nScenario: Health-Endpoint /healthz ist ok" -ForegroundColor Yellow
Given "Qdrant-Container laeuft mit production.yaml (HTTP intern)"
$r = Invoke-SSH "curl -s http://localhost:6333/healthz" $VpsUser $VpsIp $SshKeyPath
When "GET /healthz lokal abgefragt wird"
Then-True "Health-Check bestanden (Qdrant 1.18: 'healthz check passed')" ($r.ExitCode -eq 0 -and $r.Output -match 'healthz check passed') $r.Output

# ── Q4: Collection zoocode-3072d existiert (3072d, Cosine) ──
Write-Host "`nScenario: Collection $Collection existiert (3072d, Cosine)" -ForegroundColor Yellow
Given "Rolle legt die Collection idempotent an (RFC 0034b/#195)"
$r = Invoke-SSH "curl -s http://localhost:6333/collections/$Collection" $VpsUser $VpsIp $SshKeyPath
When "GET /collections/$Collection lokal abgefragt wird"
Then-True "Collection ist vorhanden (HTTP 200)" ($r.ExitCode -eq 0 -and $r.Output -match '"status"\s*:\s*"ok"') $r.Output
Then-True "Vektor-Dimension 3072" ($r.Output -match '3072') $r.Output
Then-True "Distance Cosine" ($r.Output -match 'Cosine') $r.Output

# ── Q5: gRPC-Port 6334 via TS-TCP-Forward erreichbar (WG-verschluesselt) ──
Write-Host "`nScenario: gRPC-Port 6334 ist ueber das Tailnet erreichbar (TCP-Forward)" -ForegroundColor Yellow
Given "Tailscale Serve forwardet tcp://localhost:6334 (gRPC, kein TLS – WG schuetzt)"
$r = & timeout 5 bash -c "echo > /dev/tcp/${VpsIp}/6334" 2>&1
When "eine TCP-Verbindung vom Runner zu ${VpsIp}:6334 aufgebaut wird"
Then-True "TCP-Connect erfolgreich (Exit 0)" ($LASTEXITCODE -eq 0) $r
