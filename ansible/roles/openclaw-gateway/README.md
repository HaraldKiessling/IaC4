# Role: openclaw-gateway

Deployt das OpenClaw-Gateway als gepinnten Docker-Container je Instanz (ADR-025 revidiert).
Pro Instanz (`oc`) werden Config/Workspace als Bind-Mounts angelegt, der Gateway-Port nur auf
`127.0.0.1` veroeffentlicht (`127.0.0.1:{{ oc.port }}:{{ oc.port }}`) und per host-seitigem
`tailscale serve --https` terminiert; das Container-Netz ist `traefik-network`
(Ollama/Qdrant via Docker-DNS).

## Upload-Bruecke (Issue #167)

Optional veroeffentlicht die Rolle je Instanz zusaetzlich die Portal-Upload-Bruecke: Der im
Container auf `openclaw_upload_bridge_internal_port` (Default `8099`) lauschende HTTP-Dienst
wird als Loopback-Host-Port `oc.upload_bridge_host_port` freigegeben und per Tailscale Serve
unter `--https={{ oc.upload_bridge_https }}` auf `http://localhost:{{ oc.upload_bridge_host_port }}`
proxied – dadurch kann ein HTTPS-Browser ohne Mixed-Content-Blockade hochladen. Beides ist
generisch parametrisiert und nur bei `oc.upload_bridge_enabled: true` aktiv; die Serve-Task
prueft vor dem Setzen den `tailscale serve status` (idempotent). Bewusst kein Pinning auf eine
Container-IP (Recreate-stabil). DEV: alle drei Instanzen aktiv (Loopback 18099/18100/18101,
HTTPS 8443/8444/8445). PROD: Werte definiert, aber deaktiviert (`enabled: false`) – Aktivierung
erst nach separater Owner-Freigabe.
