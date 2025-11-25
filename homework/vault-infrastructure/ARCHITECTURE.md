# Vault Infrastructure Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     Host Machine (localhost)                     │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │         Shared Vault Infrastructure (Port 8200)            │ │
│  │                                                              │ │
│  │  ┌──────────────────────────────────────────────────────┐  │ │
│  │  │  Container: shared_vault_server                      │  │ │
│  │  │  Image: hashicorp/vault:1.15                        │  │ │
│  │  │                                                        │  │ │
│  │  │  ┌──────────────────────────────────────────────┐    │  │ │
│  │  │  │  Vault Server                                │    │  │ │
│  │  │  │  - KV v2 Secrets Engine                     │    │  │ │
│  │  │  │  - AppRole Authentication                    │    │  │ │
│  │  │  │  - Policies                                  │    │  │ │
│  │  │  │  - HTTP API (0.0.0.0:8200)                  │    │  │ │
│  │  │  │                                              │    │  │ │
│  │  │  │  Secrets:                                    │    │  │ │
│  │  │  │  ├─ secret/4_ldap_xacml/app/flask          │    │  │ │
│  │  │  │  ├─ secret/4_ldap_xacml/database/postgres  │    │  │ │
│  │  │  │  └─ secret/[other-apps]/...                │    │  │ │
│  │  │  │                                              │    │  │ │
│  │  │  │  AppRoles:                                   │    │  │ │
│  │  │  │  ├─ 4_ldap_xacml-flask-app                 │    │  │ │
│  │  │  │  └─ [other-app-roles]                      │    │  │ │
│  │  │  └──────────────────────────────────────────────┘    │  │ │
│  │  │                                                        │  │ │
│  │  │  Volume: vault_data → /vault/file                    │  │ │
│  │  └──────────────────────────────────────────────────────┘  │ │
│  │                                                              │ │
│  │  Network: shared_vault_net (172.30.0.0/16)                 │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                 │                                │
│                                 │                                │
│  ┌──────────────────────────────┼─────────────────────────────┐ │
│  │     Application: 4_three_tier_app (Ports 80, 443, 5432)    │ │
│  │                               │                              │ │
│  │  ┌────────────────────────────┼──────────────────────────┐  │ │
│  │  │  Frontend: apache-FE       │  Backend: flask_be       │  │ │
│  │  │  (Apache HTTPS)            │  (Flask API)             │  │ │
│  │  │  Ports: 80, 443           │  Port: 5000              │  │ │
│  │  │                            │                           │  │ │
│  │  │  Serves:                   │  ┌──────────────────┐    │  │ │
│  │  │  - HTML/CSS/JS            │  │  Vault Client    │    │  │ │
│  │  │  - Static files           │  │  - AppRole Auth  │    │  │ │
│  │  │                            │  │  - Secret Cache  │    │  │ │
│  │  │  Proxies to Backend ────► │  └──────────────────┘    │  │ │
│  │  │                            │         │                 │  │ │
│  │  └────────────────────────────┼─────────┼────────────────┘  │ │
│  │                               │         │                    │ │
│  │                               │    Connects to Vault         │ │
│  │                               │    via shared_vault_net      │ │
│  │                               │         │                    │ │
│  │                               │         ▼                    │ │
│  │                               │   VAULT_ADDR=               │ │
│  │                               │   http://shared_vault_server:8200 │
│  │                               │                              │ │
│  │  ┌─────────────────────────────────────────────────────┐    │ │
│  │  │  Database: postgres_db                              │    │ │
│  │  │  Port: 5432                                         │    │ │
│  │  │                                                      │    │ │
│  │  │  ┌────────────────────────────────────────────┐     │    │ │
│  │  │  │  PostgreSQL 14                             │     │    │ │
│  │  │  │  - Database: postgres_db                  │     │    │ │
│  │  │  │  - User: admin (from Vault)              │     │    │ │
│  │  │  │  - Password: (from Vault via Docker Secret) │     │    │ │
│  │  │  │  - Tables: users                          │     │    │ │
│  │  │  └────────────────────────────────────────────┘     │    │ │
│  │  │                                                      │    │ │
│  │  │  Volume: pg_data                                    │    │ │
│  │  │  Init: be_flask/db_init/001_create_users.sql      │    │ │
│  │  │        (Generated from Vault secrets)              │    │ │
│  │  └─────────────────────────────────────────────────────┘    │ │
│  │                                                              │ │
│  │  Networks:                                                   │ │
│  │  - app_net (internal)                                       │ │
│  │  - shared_vault_net (connects to Vault) ───────────────────┘ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## Secret Flow

```
1. Application Startup
   ─────────────────►
   
   Flask Backend                  Shared Vault Server
   ┌──────────────┐              ┌──────────────────┐
   │              │              │                  │
   │  Load env:   │              │                  │
   │  ROLE_ID     │──────────────│  AppRole Auth    │
   │  SECRET_ID   │   Login      │                  │
   │              │──────────────│  Validate        │
   │              │              │                  │
   │  Receive     │◄─────────────│  Return Token    │
   │  Token       │              │  (1 hour TTL)    │
   │              │              │                  │
   └──────────────┘              └──────────────────┘

2. Fetch Secrets
   ─────────────────►
   
   Flask Backend                  Shared Vault Server
   ┌──────────────┐              ┌──────────────────┐
   │              │              │                  │
   │  Request     │──────────────│  Check Policy    │
   │  JWT Secret  │   + Token    │  (4_ldap_xacml-app)│
   │              │              │                  │
   │              │              │  Read from:      │
   │              │              │  secret/4_ldap_xacml/│
   │              │              │  app/flask       │
   │              │              │                  │
   │  Receive     │◄─────────────│  Return:         │
   │  Secrets     │              │  - jwt_secret    │
   │  (Cached 5m) │              │  - passwords     │
   │              │              │                  │
   └──────────────┘              └──────────────────┘

3. Database Connection
   ─────────────────►
   
   Flask Backend                  Shared Vault Server
   ┌──────────────┐              ┌──────────────────┐
   │              │              │                  │
   │  Request DB  │──────────────│  Check Policy    │
   │  Credentials │   + Token    │                  │
   │              │              │  Read from:      │
   │              │              │  secret/4_ldap_xacml/│
   │              │              │  database/postgres│
   │              │              │                  │
   │  Receive     │◄─────────────│  Return:         │
   │  Config      │              │  - username      │
   │              │              │  - password      │
   │              │              │  - host, port    │
   │              │              │                  │
   │  Connect to  │──────────────────────┐          │
   │  PostgreSQL  │                      │          │
   │              │                      ▼          │
   └──────────────┘            ┌──────────────┐    │
                               │ PostgreSQL   │    │
                               │ Container    │    │
                               └──────────────┘    │
                                                    │
                               └──────────────────┘
```

## Network Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Docker Networks                      │
│                                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │  shared_vault_net (172.30.0.0/16)                  │ │
│  │  External network - Shared infrastructure          │ │
│  │                                                      │ │
│  │  Connected:                                         │ │
│  │  ├─ shared_vault_server (Vault)                    │ │
│  │  ├─ flask_be (4_three_tier_app backend)               │ │
│  │  └─ [other apps can connect here]                  │ │
│  │                                                      │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │  app_net (4_three_tier_app internal network)          │ │
│  │  Bridge - Application-specific                     │ │
│  │                                                      │ │
│  │  Connected:                                         │ │
│  │  ├─ apache_fe (Frontend)                           │ │
│  │  ├─ flask_be (Backend)                             │ │
│  │  └─ postgres_db (Database)                         │ │
│  │                                                      │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
└─────────────────────────────────────────────────────────┘

Note: flask_be is on BOTH networks:
- app_net: To communicate with frontend and database
- shared_vault_net: To fetch secrets from Vault
```

## Security Boundaries

```
┌─────────────────────────────────────────────────────────────┐
│                  Security Architecture                       │
│                                                              │
│  Public Network (Internet)                                  │
│       │                                                      │
│       │ HTTPS (Port 443)                                   │
│       │ HTTP (Port 80)                                     │
│       ▼                                                      │
│  ┌──────────────┐                                          │
│  │  Apache FE   │  ← TLS Termination                       │
│  └──────────────┘                                          │
│       │                                                      │
│       │ Internal (app_net)                                 │
│       ▼                                                      │
│  ┌──────────────┐         ┌────────────────┐              │
│  │  Flask BE    │◄────────┤  PostgreSQL DB │              │
│  │              │ app_net │                │              │
│  └──────┬───────┘         └────────────────┘              │
│         │                                                   │
│         │ shared_vault_net                                 │
│         │ (Isolated from app_net)                         │
│         │                                                   │
│         ▼                                                   │
│  ┌──────────────┐                                          │
│  │  Vault       │  ← Secrets Management                    │
│  │  Server      │    - AppRole Authentication             │
│  │              │    - Policy-based Access                │
│  │              │    - Encrypted Storage                  │
│  └──────────────┘                                          │
│       │                                                      │
│       │ Admin Access (localhost:8200)                      │
│       ▼                                                      │
│  Administrator                                              │
│                                                              │
└─────────────────────────────────────────────────────────────┘

Security Features:
- Network isolation between Vault and application
- No direct public access to Vault
- Secrets never in environment variables (except AppRole creds)
- TLS encryption for frontend traffic
- Database on internal network only
- Policy-based access control
```

## Scaling for Multiple Applications

```
┌──────────────────────────────────────────────────────────────┐
│              Future: Multiple Applications                    │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  Shared Vault Infrastructure                         │    │
│  │                                                        │    │
│  │  Secrets:                                             │    │
│  │  ├─ secret/4_ldap_xacml/                            │    │
│  │  │  ├─ app/flask                                     │    │
│  │  │  └─ database/postgres                             │    │
│  │  │                                                    │    │
│  │  ├─ secret/3_web_server/                            │    │
│  │  │  ├─ apache/certificates                           │    │
│  │  │  └─ tomcat/config                                 │    │
│  │  │                                                    │    │
│  │  └─ secret/other_app/                               │    │
│  │     └─ ...                                            │    │
│  │                                                        │    │
│  │  AppRoles:                                            │    │
│  │  ├─ 4_ldap_xacml-flask-app                          │    │
│  │  ├─ 3_web_server-apache                             │    │
│  │  └─ other_app-service                               │    │
│  │                                                        │    │
│  └────────────────┬───────────────┬─────────────────────┘    │
│                   │               │                           │
│                   │               │                           │
│         ┌─────────┘               └────────┐                 │
│         │                                  │                 │
│         ▼                                  ▼                 │
│  ┌─────────────────┐              ┌─────────────────┐       │
│  │ 4_three_tier_app│              │  3_Web_Server   │       │
│  │  Application    │              │  Application    │       │
│  │                 │              │                 │       │
│  │  AppRole:       │              │  AppRole:       │       │
│  │  4_ldap_xacml-  │              │  3_web_server-  │       │
│  │  flask-app      │              │  apache         │       │
│  │                 │              │                 │       │
│  │  Access:        │              │  Access:        │       │
│  │  secret/        │              │  secret/        │       │
│  │  4_ldap_xacml/* │              │  3_web_server/* │       │
│  └─────────────────┘              └─────────────────┘       │
│                                                               │
│  Benefits:                                                    │
│  ✓ Single Vault instance                                    │
│  ✓ Centralized management                                   │
│  ✓ Namespace isolation                                      │
│  ✓ Independent AppRoles                                     │
│  ✓ Policy-based access control                             │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```
