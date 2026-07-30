output "new_oauth_client_id" {
  description = "Client ID des neuen OAuth-Clients"
  value       = tailscale_oauth_client.ci_client_ia4.id
}

output "new_oauth_client_secret" {
  description = "Client Secret des neuen OAuth-Clients (sensitive)"
  value       = tailscale_oauth_client.ci_client_ia4.key
  sensitive   = true
}
