resource "tailscale_acl" "main" {
  acl                        = file("${path.module}/acl.json")
  overwrite_existing_content = true
}
