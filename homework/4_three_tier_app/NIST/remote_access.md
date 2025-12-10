# Remote Access Policy

## Allowed Remote Access Methods
1. **Web Browser Access** - HTTPS only via port 443 (Apache)
2. **API Access** - RESTful API via /api/* endpoints (authenticated)

## Usage Restrictions
- Keycloak authentication required for all access
- Role-based authorization enforced (user, moderator, admin)
- Session timeout: 30 minutes idle, 10 hours maximum
- Token expiry: 5 minutes (access), 30 minutes (refresh)

## Configuration Requirements
- TLS 1.3 minimum protocol version
- Valid certificate from Vault PKI required
- Client must support modern cipher suites
- HSTS enabled (2-year max-age)

## Authorization Process
1. User authenticates via Keycloak SSO
2. JWT token issued with role claims
3. Token validated on each API request
4. Token refresh required after 5 minutes
5. Re-authentication required after 30 minutes idle