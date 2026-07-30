resource "tailscale_oauth_client" "ci_client_ia4" {
  description = "IaC4 CI OAuth Client Terraform managed"
  scopes      = var.oauth_client_scopes
  tags        = ["tag:ci", "tag:ia4"]
}
