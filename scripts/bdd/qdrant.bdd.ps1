#!/usr/bin/env pwsh
# Feature: Qdrant (Phase 2d, ADR-011) – HTTPS auf 6333 via Tailscale-TLS
# Verifiziert: TLS-Terminierung (Tailscale-Zertifikat fuer MagicDNS-Name), /healthz,
# Collection zoocode-3072d (3072d, Cosine – RFC 0034b/#195, prod-SSoT).
# Hinweis: curl -k auf dem Runner (Tailscale-CA ist keine oeffentliche CA);
# der Zertifikats-Subject-Check (Q2) liefert die eigentliche TLS-Evidenz.
param(
    [Parameter(Mandatory)][string]$VpsIp,
    [Parameter(Mandatory)][string]$VpsUser,
    [Parameter(Mandatory)][string]$SshKeyPath,
    [Parameter(Mandatory)][string]$ExpectedHostname,
    [Parameter(Mandatory)][string]$Tailnet,
    [string]$Collection = "zoocode-3072d"
)

. "$PSScriptRoot/bdd-lib.ps1"

$Fqdn = "$ExpectedHostname.$Tailnet.ts.net"
$Base = "https://${Fqdn}:6333"

Write-Host "Feature: Qdrant (Phase 2d) – Target: $Fqdn" -ForegroundColor Cyan

# ── Q1: HTTPS 6333 antwortet ueber das Tailnet (TS-TLS-Terminierung) ──
Write-Host "`nScenario: Qdrant spricht HTTPS auf 6333 (Tailscale-Zertifikat)" -ForegroundColor Yellow
Given "Qdrant-Rolle hat Tailscale-Zertifikat + enable_tls konfiguriert"
$code = & curl -sk --connect-timeout 8 -o /dev/null -w '%{http_code}' "$Base/" 2>&1
When "HTTPS-GET auf $Base/ ausgefuehrt wird (Runner im Tailnet)"
Then-True "HTTP 200 ueber TLS (war: $code)" ($code.Trim() -eq '200') $code

# ── Q2: Zertifikat passt zum MagicDNS-Namen (Tailscale-CA) ──
Write-Host "`nScenario: TLS-Zertifikat ist fuer $Fqdn ausgestellt" -ForegroundColor Yellow
Given "Tailscale stellt Zertifikate nur fuer eigene MagicDNS-Namen aus"
$r = Invoke-SSH "echo | openssl s_client -connect 127.0.0.1:6333 -servername $Fqdn 2>/dev/null | openssl x509 -noout -subject" $VpsUser $VpsIp $SshKeyPath
When "das Server-Zertifikat auf dem VPS inspiziert wird"
Then-True "Subject enthaelt $Fqdn" ($r.Output -match [regex]::Escape($Fqdn)) $r.Output

# ── Q3: Health-Endpoint /healthz liefert ok (nicht /health → 404) ──
Write-Host "`nScenario: Health-Endpoint /healthz ist ok" -ForegroundColor Yellow
Given "Qdrant-Container laeuft mit production.yaml"
$r = Invoke-SSH "curl -sk https://localhost:6333/healthz" $VpsUser $VpsIp $SshKeyPath
When "GET /healthz lokal abgefragt wird"
Then-True "Antwort enthaelt status ok" ($r.Output -match '"status"\s*:\s*"ok"') $r.Output

# ── Q4: Collection zoocode-3072d existiert (3072d, Cosine) ──
Write-Host "`nScenario: Collection $Collection existiert (3072d, Cosine)" -ForegroundColor Yellow
Given "Rolle legt die Collection idempotent an (RFC 0034b/#195)"
$r = Invoke-SSH "curl -sk https://localhost:6333/collections/$Collection" $VpsUser $VpsIp $SshKeyPath
When "GET /collections/$Collection lokal abgefragt wird"
Then-True "Collection ist vorhanden (HTTP 200)" ($r.ExitCode -eq 0 -and $r.Output -match '"status"\s*:\s*"ok"') $r.Output
Then-True "Vektor-Dimension 3072" ($r.Output -match '3072') $r.Output
Then-True "Distance Cosine" ($r.Output -match 'Cosine') $r.Output
