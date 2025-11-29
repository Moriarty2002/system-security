# Keycloak Infrastructure - Centralized Authentication

This is a **standalone Keycloak infrastructure** similar to `vault-infrastructure`. It provides centralized identity and access management for all applications on the server.

## Architecture

```
┌─────────────────────────────────────────┐
│   Keycloak Infrastructure (Standalone)  │
│                                         │
│  ┌──────────────┐    ┌──────────────┐  │
│  │  Keycloak    │───▶│ PostgreSQL   │  │
│  │   Server     │    │   Database   │  │
│  │  Port 8080   │    │              │  │
│  └──────────────┘    └──────────────┘  │
│         ▲                               │
│         │ shared_keycloak_network       │
└─────────┼───────────────────────────────┘
          │
          │ Applications connect here
          │ for token validation
          ▼
┌─────────────────────────────────────────┐
│        Application 1 (4_three_tier_app) │
│        Application 2 (future)           │
│        Application 3 (future)           │
└─────────────────────────────────────────┘
```

## Features

- **Centralized SSO** - Single sign-on across all applications
- **Isolated Infrastructure** - Separate Docker network and containers
- **Persistent Storage** - Database stored in named volume
- **Health Checks** - Automatic restart on failure
- **Secrets Management** - Credentials stored in files, not environment variables
- **Production Ready** - Can be configured for HTTPS and clustering

## Quick Start

### 1. Initialize Keycloak

```bash
cd keycloak-infrastructure/scripts
./init-keycloak.sh
```

This will:
- Generate secure random passwords
- Store credentials in `secrets/` directory
- Create initialization files

### 2. Start Keycloak Infrastructure

```bash
cd keycloak-infrastructure
docker compose up -d
```

### 3. Wait for Startup

```bash
# Monitor logs
docker compose logs -f keycloak

# Wait for: "Keycloak 23.0 started"
```

### 4. Access Admin Console

- **URL**: http://localhost:8080
- **Username**: Check `secrets/admin_username.txt`
- **Password**: Check `secrets/admin_password.txt`

### 5. Configure Realms and Clients

See `scripts/configure-realm.sh` for automated realm setup.

## Configuration

### Secrets

All sensitive data is stored in `secrets/` directory:

```
secrets/
  ├── db_password.txt       # PostgreSQL password
  ├── admin_username.txt    # Keycloak admin username
  └── admin_password.txt    # Keycloak admin password
```

**Important**: Add `secrets/` to `.gitignore`!

### Network

Keycloak uses a dedicated bridge network: `shared_keycloak_network`

Applications connect to this network to validate tokens:

```yaml
# In application's docker-compose.yaml
networks:
  keycloak_net:
    name: shared_keycloak_network
    external: true
```

### Ports

- **8080**: HTTP port (exposed to localhost)
- For production, configure HTTPS with a reverse proxy

## Application Integration

### 1. Connect Application to Keycloak Network

```yaml
# In 4_three_tier_app/docker-compose.yaml
services:
  backend:
    networks:
      - app_net           # Internal app network
      - keycloak_net      # Keycloak network (external)

networks:
  keycloak_net:
    name: shared_keycloak_network
    external: true
```

### 2. Configure Backend to Use External Keycloak

```python
# Backend uses: http://shared-keycloak-server:8080
KEYCLOAK_SERVER_URL = "http://shared-keycloak-server:8080"
```

### 3. Frontend Still Uses localhost:8080

```javascript
// Frontend (browser) uses public URL
const keycloak = new Keycloak({
    url: 'http://localhost:8080',
    realm: 'mes-local-cloud',
    clientId: 'mes-local-cloud-api'
});
```

## Management Commands

### View Status
```bash
docker compose ps
```

### View Logs
```bash
docker compose logs -f keycloak
```

### Restart Keycloak
```bash
docker compose restart keycloak
```

### Stop Infrastructure
```bash
docker compose down
```

### Complete Reset (Delete Data)
```bash
docker compose down -v
rm -rf secrets/*
```

## Security Best Practices

✅ **Isolated Network** - Keycloak in separate Docker network  
✅ **Secrets in Files** - Not in environment variables or .env  
✅ **Health Checks** - Automatic container restart  
✅ **Resource Limits** - Prevent resource exhaustion (TODO)  
✅ **Read-Only Volumes** - Config mounted read-only (TODO)  
✅ **No Root User** - Keycloak runs as non-root user  
✅ **Persistent Data** - Database in named volume (survives restart)  

## Production Considerations

For production deployment:

1. **Enable HTTPS** - Use reverse proxy (nginx) with SSL certificates
2. **Use Vault for Secrets** - Integrate with vault-infrastructure
3. **Configure Clustering** - Multiple Keycloak instances for HA
4. **Set Resource Limits** - Memory and CPU limits in docker-compose
5. **Enable Audit Logging** - Log all authentication events
6. **Regular Backups** - Backup `keycloak_db_data` volume
7. **Update KC_HOSTNAME** - Set to your domain name
8. **Disable Development Mode** - Use `start` command, not `start-dev`

## Troubleshooting

### Keycloak Won't Start

Check database connection:
```bash
docker compose logs keycloak_db
docker compose logs keycloak
```

### Can't Access Admin Console

1. Check if Keycloak is healthy:
   ```bash
   docker compose ps
   ```

2. Check admin credentials:
   ```bash
   cat secrets/admin_username.txt
   cat secrets/admin_password.txt
   ```

### Application Can't Connect

1. Verify application is on Keycloak network:
   ```bash
   docker network inspect shared_keycloak_network
   ```

2. Test connectivity from application:
   ```bash
   docker compose exec backend curl http://shared-keycloak-server:8080/health
   ```

## Comparison with vault-infrastructure

| Feature | Vault Infrastructure | Keycloak Infrastructure |
|---------|---------------------|------------------------|
| Purpose | Secrets Management | Identity & Access Management |
| Network | `shared_vault_network` | `shared_keycloak_network` |
| Container | `shared_vault_server` | `shared-keycloak-server` |
| Port | 8200 | 8080 |
| Database | File-based | PostgreSQL |
| Used By | All apps (secrets) | All apps (authentication) |

Both are **shared infrastructure services** that run independently and can be used by multiple applications.

## Files

```
keycloak-infrastructure/
├── docker-compose.yaml          # Main infrastructure definition
├── README.md                    # This file
├── scripts/
│   ├── init-keycloak.sh        # Initialize secrets and configuration
│   ├── configure-realm.sh      # Automated realm setup
│   └── backup.sh               # Backup database
├── config/
│   └── realm-export.json       # Realm configuration (optional)
├── secrets/                    # Generated by init script
│   ├── db_password.txt
│   ├── admin_username.txt
│   └── admin_password.txt
└── logs/                       # Keycloak logs
    └── keycloak.log
```

## Next Steps

1. Run `scripts/init-keycloak.sh` to generate secrets
2. Start infrastructure with `docker compose up -d`
3. Configure realms and clients in Admin Console
4. Update applications to use external Keycloak
5. Test SSO across multiple applications

---

**Note**: This setup is similar to how enterprise SSO works - one centralized identity provider (like Okta, Auth0, or Azure AD) serving multiple applications.
