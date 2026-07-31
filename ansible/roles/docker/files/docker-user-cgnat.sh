#!/bin/bash
# IaC4 – DOCKER-USER-CGNAT-Regeln (Firewall-Konzept R10/R11, Reviewer-Befund 2026-07-31)
# Warum: Docker-published Ports (80/8080/11434) werden in der FORWARD-Kette (DOCKER-USER)
# verarbeitet – UFW-Regeln (INPUT) greifen dort NICHT. Ohne diese Regeln wären die
# Ports öffentlich erreichbar (Worst-Case ADR-021). Persistenz: systemd-Unit
# docker-user-cgnat.service (After=docker.service).
set -euo pipefail

PORTS="80,8080,11434"

# R10: CGNAT-Allow an Position 1 (Tailscale-Mesh, Defense-in-Depth)
if ! iptables -C DOCKER-USER -s 100.64.0.0/10 -p tcp -m multiport --dports "$PORTS" -j ACCEPT 2>/dev/null; then
  iptables -I DOCKER-USER 1 -s 100.64.0.0/10 -p tcp -m multiport --dports "$PORTS" -j ACCEPT
fi

# R11: Alles andere droppen (Position 2)
if ! iptables -C DOCKER-USER -p tcp -m multiport --dports "$PORTS" -j DROP 2>/dev/null; then
  iptables -I DOCKER-USER 2 -p tcp -m multiport --dports "$PORTS" -j DROP
fi
