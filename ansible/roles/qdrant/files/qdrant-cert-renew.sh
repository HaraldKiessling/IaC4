#!/usr/bin/env bash
# qdrant-cert-renew.sh – Erneuert das Tailscale-Zertifikat für Qdrant (90-Tage-Gültigkeit)
# Aufruf: monatlich via systemd-Timer (qdrant-cert-renew.timer)
set -euo pipefail

FQDN="$(tailscale status --json | jq -r '.Self.DNSName' | sed 's/\.$//')"
CERT_DIR=/opt/qdrant/certs

tailscale cert --cert-file="$CERT_DIR/tls.crt" --key-file="$CERT_DIR/tls.key" "$FQDN"
docker restart qdrant
