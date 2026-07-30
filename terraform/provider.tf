terraform {
  required_providers {
    tailscale = {
      source = "tailscale/tailscale"
      version = "~> 0.17"
    }
  }
}

provider "tailscale" {
  api_key = var.tailscale_api_key
}
