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

# HTTP listener on all interfaces
listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = 1
  
  # In production, enable TLS:
  # tls_disable = 0
  # tls_cert_file = "/vault/certs/vault.crt"
  # tls_key_file = "/vault/certs/vault.key"
}

# API address
api_addr = "http://0.0.0.0:8200"

# Disable mlock for containerized environments
disable_mlock = true

# Log level
log_level = "Info"

# Default lease duration
default_lease_ttl = "168h"
max_lease_ttl = "720h"

# Enable audit logging (optional, uncomment to enable)
# This will log all Vault operations for security auditing
# audit "file" {
#   path = "/vault/logs/audit.log"
# }
