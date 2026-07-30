resource "tailscale_oauth_client" "ci_client_ia4" {
  description = "IaC4 CI OAuth Client ${formatdate("YYYY-MM-DD", timestamp())}"
  scopes      = var.oauth_client_scopes
  tags        = ["tag:ci"]
}
