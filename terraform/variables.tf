variable "tailscale_oauth_client_id" {
  description = "Tailscale OAuth-Client-ID (tag:ci, IaC3-Verfahren)"
  type        = string
}

variable "tailscale_oauth_client_secret" {
  description = "Tailscale OAuth-Client-Secret (tag:ci, IaC3-Verfahren)"
  type        = string
  sensitive   = true
}

variable "tailscale_tailnet" {
  description = "Tailscale Tailnet ID (z.B. tailcfea8a.ts.net)"
  type        = string
}

variable "oauth_client_scopes" {
  description = "Scopes für den neuen CI-OAuth-Client"
  type        = set(string)
  default     = ["devices:core", "auth_keys"]
}
