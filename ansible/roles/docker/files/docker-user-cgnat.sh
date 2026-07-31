#!/bin/bash
# IaC4 – DOCKER-USER-CGNAT-Regeln (Firewall-Konzept R10/R11, Harald-Review K1-1/K2-1 2026-07-31)
# Warum: Docker-published Ports werden in FORWARD/DOCKER-USER verarbeitet – UFW (INPUT)
# greift dort NICHT. 
# Design (K1-1-Fix): Der DROP ist INTERFACE-GEBUNDEN an das public Interface (eth0),
# nicht global – sonst würden Host-Loopback (docker-proxy) und Container-zu-Container
# Zugriffe auf 80/8080/11434/6333/6334 mit gedroppt (Playbook-Wait-Steps/BDD würden brechen).
# Persistenz (K2-3-Fix): systemd-Drop-in docker.service.d/docker-user-cgnat.conf
# (ExecStartPost) setzt die Regeln bei JEDEM Docker-Daemon-Start neu.
set -euo pipefail

# Docker-published Ports (R10/R11): Traefik 80/8080, Ollama 11434, Qdrant 6333/6334
PORTS="80,8080,11434,6333,6334"

# Public-Interface via Default-Route ermitteln (eth0 auf dem VPS; fail-closed wenn unbekannt)
PUB_IF=$(ip -4 route show default | awk '{print $5; exit}')
if [ -z "$PUB_IF" ]; then
  echo "FEHLER: kein Default-Route-Interface ermittelt – DOCKER-USER-Regeln nicht gesetzt" >&2
  exit 1
fi

# R10: CGNAT-Allow an Position 1 (Defense-in-Depth; Tailscale-Pfad kommt auf tailscale0 an)
if ! iptables -C DOCKER-USER -s 100.64.0.0/10 -p tcp -m multiport --dports "$PORTS" -j ACCEPT 2>/dev/null; then
  iptables -I DOCKER-USER 1 -s 100.64.0.0/10 -p tcp -m multiport --dports "$PORTS" -j ACCEPT
fi

# R11: Alles andere vom PUBLIC-Interface droppen (Position 2)
#     -i $PUB_IF: nur Internet-Ingress; localhost/docker-proxy/Container bleiben unberührt
if ! iptables -C DOCKER-USER -i "$PUB_IF" -p tcp -m multiport --dports "$PORTS" -j DROP 2>/dev/null; then
  iptables -I DOCKER-USER 2 -i "$PUB_IF" -p tcp -m multiport --dports "$PORTS" -j DROP
fi
