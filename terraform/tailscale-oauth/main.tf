# Tailscale OAuth-Client + ACLs
# Portiert aus IaC3 (RFC 0025, 0033)
# Ermöglicht GH-Runner den Beitritt zum Tailscale-Netzwerk

variable "tailscale_api_key" {
  description = "Tailscale API-Key (GH Actions Secret)"
  type        = string
  sensitive   = true
}

variable "tailscale_tailnet" {
  description = "Tailscale Tailnet-Name"
  type        = string
  default     = "tailcfea8a.ts.net"
}
