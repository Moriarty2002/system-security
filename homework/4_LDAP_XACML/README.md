# Security steps to do:
- change token management to use HTTP-Only Cookies:
```
// Server-side (your backend)
// Set cookie on login
res.cookie('access_token', token, {
  httpOnly: true,  // JavaScript can't access
  secure: true,    // HTTPS only
  sameSite: 'strict',
  maxAge: 24 * 60 * 60 * 1000 // 24 hours
});

// Frontend - no token handling needed!
// Browser automatically sends cookie with each request
async function headers(includeJson){
  const h = {};
  if (includeJson) h['Content-Type'] = 'application/json';
  // No Authorization header needed - cookie is automatic
  return h;
}

// Pros: Most secure (immune to XSS), automatic persistence
// Cons: Requires backend changes, CSRF protection needed
```

# LDAP and XACML Integration Preparation

This project has been prepared for LDAP authentication and XACML policy-based access control integration.

## LDAP Configuration

LDAP settings are configured in `be_flask/src/config.py`:
- `LDAP_ENABLED`: Enable/disable LDAP authentication
- `LDAP_SERVER`: LDAP server URL
- `LDAP_BASE_DN`: Base DN for searches
- `LDAP_BIND_USER/PASSWORD`: Service account credentials
- `LDAP_USER_SEARCH_FILTER`: User search filter template
- `LDAP_USER_ATTRIBUTES`: Mapping of LDAP attributes to user properties

LDAP authentication module: `be_flask/src/ldap_auth.py` (placeholder implementation)

## XACML Configuration

XACML settings are configured in `be_flask/src/config.py`:
- `XACML_ENABLED`: Enable/disable XACML policy evaluation
- `XACML_PDP_URL`: Policy Decision Point endpoint
- `XACML_POLICY_FILE`: Local policy file path
- `XACML_REQUEST_TIMEOUT`: Request timeout for PDP calls

XACML policy evaluation module: `be_flask/src/xacml_policy.py` (placeholder implementation)

Sample policy file: `be_flask/policies/default-policy.xml`

## Docker Services

An OpenLDAP service is prepared in `docker-compose.yaml` (commented out):
- Uncomment the `ldap` service to enable LDAP server
- Configure environment variables for domain and admin credentials

## Dependencies

Potential dependencies are listed in `be_flask/requirements.txt` (commented out):
- `python-ldap` or `ldap3` for LDAP integration
- `pyxacml` for XACML policy evaluation
- `requests` for HTTP-based PDP communication

## Next Steps

To implement LDAP and XACML:
1. Uncomment and install required dependencies
2. Implement actual LDAP authentication in `ldap_auth.py`
3. Implement XACML policy evaluation in `xacml_policy.py`
4. Uncomment LDAP service in `docker-compose.yaml`
5. Update authentication flow to support LDAP
6. Integrate XACML checks in access control logic



# Postgres persistence and init scripts

This directory contains the Flask backend and init SQL for the homework project.

Persistence
- PostgreSQL data is bind-mounted to the host at `./postgres_data` (relative to the repo root).
- On first `docker compose up`, if `./postgres_data` is empty, Postgres will initialize the database there.

Init scripts
- SQL files placed in `./be_flask/db_init` are mounted into the container at `/docker-entrypoint-initdb.d` and will be executed by the official Postgres image when the DB directory is empty.

Resetting the database
1. Stop the containers: `docker compose down`
2. Remove the docker volume `docker volume ls` and `docker volume rm <volume_name>`
4. Uncomment the init script binding in the docker compose file
5. The init SQL scripts in `be_flask/db_init` will run on the fresh DB.

Notes
- If you prefer a named docker volume instead of a host bind, change `docker-compose.yaml`'s `db` service to use a named volume (e.g. `pgdata:/var/lib/postgresql/data`).
- Ensure the Docker host user has permission to write to `./postgres_data`.
