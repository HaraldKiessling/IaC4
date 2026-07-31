variable "tailscale_api_key" {
  description = "Tailscale API Access Token – NUR Workflow 01 (Terraform-Provider; OAuth-Client-Token kann OAuth-Clients nicht verwalten, Review PR #44)"
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
