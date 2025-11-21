# Architecture Diagram - Vault-Integrated Application

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         INFRASTRUCTURE LAYER 1                       │
│                      Vault Infrastructure (Separate)                 │
└─────────────────────────────────────────────────────────────────────┘

    ┌──────────────────────────────────────────────────────────┐
    │                    Vault Server                          │
    │  ┌────────────────────────────────────────────────────┐  │
    │  │  KV v2 Secrets Engine                             │  │
    │  │  ┌──────────────────┬──────────────────────────┐  │  │
    │  │  │ secret/app/      │ secret/database/         │  │  │
    │  │  │  - jwt_secret    │  - username              │  │  │
    │  │  │  - admin_pwd     │  - password              │  │  │
    │  │  │  - alice_pwd     │  - database              │  │  │
    │  │  │  - mod_pwd       │  - host, port            │  │  │
    │  │  └──────────────────┴──────────────────────────┘  │  │
    │  └────────────────────────────────────────────────────┘  │
    │                                                           │
    │  ┌────────────────────────────────────────────────────┐  │
    │  │  AppRole Authentication                            │  │
    │  │  - Role: flask-app                                 │  │
    │  │  - Policy: app-policy                              │  │
    │  │  - Token TTL: 1 hour                               │  │
    │  └────────────────────────────────────────────────────┘  │
    │                                                           │
    │  Port: 8200                                               │
    │  Network: vault_net (172.20.0.0/16)                      │
    └──────────────────────────────────────────────────────────┘
                            ▲
                            │ AppRole Auth
                            │ (Role ID + Secret ID)
                            │
┌───────────────────────────┴─────────────────────────────────────────┐
│                         INFRASTRUCTURE LAYER 2                       │
│                      Application Stack (Main)                        │
└─────────────────────────────────────────────────────────────────────┘

    ┌──────────────────────────────────────────────────────────┐
    │                  Apache Frontend                          │
    │  - Ports: 80 (HTTP), 443 (HTTPS)                         │
    │  - Reverse proxy to Flask                                 │
    │  - Static file serving                                    │
    │  - SSL termination                                        │
    └───────────────┬──────────────────────────────────────────┘
                    │
                    │ HTTP proxy to backend:5000
                    ▼
    ┌──────────────────────────────────────────────────────────┐
    │                  Flask Backend                            │
    │  ┌────────────────────────────────────────────────────┐  │
    │  │  Vault Client (vault_client.py)                    │  │
    │  │  - AppRole authentication                          │  │
    │  │  - Secret caching (5 min TTL)                      │  │
    │  │  - Auto token renewal                              │  │
    │  │  - Graceful fallback                               │  │
    │  └────────────────────────────────────────────────────┘  │
    │                        ▲                                  │
    │                        │ Fetches secrets                  │
    │                        │                                  │
    │  ┌────────────────────────────────────────────────────┐  │
    │  │  Application Logic                                 │  │
    │  │  - Auth API (JWT tokens)                           │  │
    │  │  - File API (upload/download)                      │  │
    │  │  - Admin API                                       │  │
    │  └────────────────────────────────────────────────────┘  │
    │                        │                                  │
    │  Environment:          │ Database connection              │
    │  - VAULT_ADDR          │                                  │
    │  - VAULT_ROLE_ID       ▼                                  │
    │  - VAULT_SECRET_ID                                        │
    └───────────────────────┬──────────────────────────────────┘
                            │
                            │ PostgreSQL protocol
                            ▼
    ┌──────────────────────────────────────────────────────────┐
    │                  PostgreSQL Database                      │
    │  - Port: 5432                                            │
    │  - Credentials: Docker secrets + Vault                   │
    │  - Volume: pg_data (persistent)                          │
    │                                                           │
    │  Credentials from:                                        │
    │  1. Vault: secret/database/postgres                      │
    │  2. Docker secret: /run/secrets/db_password              │
    └──────────────────────────────────────────────────────────┘

    Network: app_net (internal)


═══════════════════════════════════════════════════════════════════════
                            NETWORK TOPOLOGY
═══════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────┐
│  External (Host Machine)                                             │
│                                                                       │
│  Exposed Ports:                                                      │
│  - 80/tcp   → Apache HTTP                                            │
│  - 443/tcp  → Apache HTTPS                                           │
│  - 8200/tcp → Vault UI/API                                           │
│  - 5432/tcp → PostgreSQL (optional, for debugging)                   │
└─────────────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌──────────────┐   ┌─────────────────┐  ┌─────────────┐
│  vault_net   │   │    app_net      │  │  External   │
│  (external)  │   │   (internal)    │  │   Network   │
│              │   │                 │  │             │
│ - Vault      │   │ - Apache        │  │ - Internet  │
│   server     │   │ - Flask         │  │             │
│              │   │ - PostgreSQL    │  │             │
│              │◄──┤ Backend connects│  │             │
│              │   │   to Vault      │  │             │
└──────────────┘   └─────────────────┘  └─────────────┘


═══════════════════════════════════════════════════════════════════════
                         SECRET FLOW DIAGRAM
═══════════════════════════════════════════════════════════════════════

1. Application Startup
   ┌──────────┐
   │ Backend  │
   └─────┬────┘
         │ 1. Read VAULT_ROLE_ID, VAULT_SECRET_ID from .env
         │
         ▼
   ┌──────────────┐
   │    Vault     │
   └──────┬───────┘
          │ 2. Authenticate via AppRole
          │
          ▼
   ┌──────────────┐
   │  Token       │  (1 hour validity)
   └──────┬───────┘
          │ 3. Use token to read secrets
          │
          ▼
   ┌──────────────────────────────┐
   │  Cached Secrets (5 min TTL)  │
   │  - JWT signing key           │
   │  - Database credentials      │
   │  - User passwords            │
   └──────────────────────────────┘

2. Request Processing
   ┌──────────┐
   │  Client  │
   └─────┬────┘
         │ HTTP Request
         ▼
   ┌──────────┐
   │  Apache  │
   └─────┬────┘
         │ Proxy to Flask
         ▼
   ┌──────────┐
   │  Flask   │ ──► Check cache for secrets
   └─────┬────┘     (no Vault call if cached)
         │
         │ Use JWT key to verify token
         │ Use DB credentials to query
         │
         ▼
   ┌──────────┐
   │ Database │
   └──────────┘


═══════════════════════════════════════════════════════════════════════
                    SECURITY BOUNDARIES
═══════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────┐
│ Security Zone 1: Vault Infrastructure                               │
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │ - Separate docker-compose file                                  │ │
│ │ - Independent network (vault_net)                               │ │
│ │ - Sealed by default (requires manual unseal)                    │ │
│ │ - File-based backend (can use Consul/Raft in prod)             │ │
│ │ - Policy-based access control                                   │ │
│ │ - Audit logging enabled                                         │ │
│ └─────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ Security Zone 2: Application Layer                                  │
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │ Frontend (Apache)                                               │ │
│ │ - Minimal capabilities (NET_BIND_SERVICE, SETUID, SETGID)      │ │
│ │ - Read-only config mounts                                       │ │
│ │ - SSL termination                                               │ │
│ └─────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │ Backend (Flask)                                                 │ │
│ │ - AppRole credentials from .env (protected by .gitignore)       │ │
│ │ - No secrets in environment variables                           │ │
│ │ - Vault client with automatic token renewal                     │ │
│ │ - Secret caching to reduce Vault load                           │ │
│ └─────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ Security Zone 3: Data Layer                                         │
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │ Database (PostgreSQL)                                           │ │
│ │ - Password via Docker secrets (/run/secrets/db_password.txt)    │ │
│ │ - Credentials managed by Vault                                  │ │
│ │ - Persistent volume for data                                    │ │
│ │ - Internal network only (app_net)                               │ │
│ └─────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════════
                      CREDENTIAL ROTATION FLOW
═══════════════════════════════════════════════════════════════════════

Regular Rotation (Every 30-90 days):

1. Generate New Secret ID
   ┌───────────────────────────────┐
   │ ./rotate-secret-id.sh         │
   │                                │
   │ Creates new Secret ID          │
   │ Old Secret ID remains valid    │
   └───────────────────────────────┘

2. Update Configuration
   ┌───────────────────────────────┐
   │ Update .env file               │
   │ VAULT_SECRET_ID=<new-id>      │
   └───────────────────────────────┘

3. Restart Application
   ┌───────────────────────────────┐
   │ docker compose restart backend │
   │                                │
   │ New Secret ID takes effect     │
   │ Old tokens invalidated         │
   └───────────────────────────────┘

4. Verify
   ┌───────────────────────────────┐
   │ Check logs for successful      │
   │ Vault authentication           │
   └───────────────────────────────┘


═══════════════════════════════════════════════════════════════════════
                    FILE SYSTEM SECURITY
═══════════════════════════════════════════════════════════════════════

Protected Files (.gitignore):
├── .env                          (Vault credentials)
├── secrets/                      (Docker secrets)
│   └── db_password.txt           (Database password)
├── vault/scripts/
│   ├── vault-keys.json           (Unseal keys + root token)
│   └── approle-credentials.txt   (AppRole credentials)
└── vault/file/                   (Vault data directory)

Permissions:
- .env:                    600 (rw-------)
- secrets/*:               600 (rw-------)
- vault/scripts/*.json:    600 (rw-------)
- vault/scripts/*.sh:      700 (rwx------)

Public Files (safe to commit):
├── docker-compose.yaml           (No secrets)
├── docker-compose.vault.yaml     (No secrets)
├── vault/config/*.hcl            (Policies, no secrets)
├── vault/policies/*.hcl          (Access policies)
└── Documentation (*.md)          (No secrets)
