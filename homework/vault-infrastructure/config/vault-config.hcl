# Shared Vault Server Configuration
# This Vault instance can be used by multiple applications for secrets management.
# 
# Features:
# - File-based storage for development (use Raft/Consul in production)
# - HTTP API (enable TLS in production)
# - UI enabled for management
# - Audit logging support

ui = true

# File storage backend - data persists in /vault/file
storage "file" {
  path = "/vault/file"
}

# HTTPS listener on all interfaces
listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = 0
  tls_cert_file = "/vault/certs/vault-cert.pem"
  tls_key_file = "/vault/certs/vault-key.pem"
  tls_min_version = "tls13"

 "default" = {
    "Strict-Transport-Security" = ["max-age=31536000","includeSubDomains"], # enforce HTTPS
  }
}

# API address
api_addr = "https://0.0.0.0:8200"

# Disable mlock for containerized environments
disable_mlock = false

# Log level
log_level = "Info"

# Default lease duration
default_lease_ttl = "168h"
max_lease_ttl = "720h"

# Enable audit logging
# This will log all Vault operations for security auditing
# Note: Audit logging is enabled via CLI after Vault initialization
# Run: vault audit enable file file_path=/vault/logs/audit.log
