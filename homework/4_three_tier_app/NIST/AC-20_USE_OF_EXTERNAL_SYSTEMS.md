# AC-20: Use of External Systems

## Purpose
This document describes the organization's requirements and procedures for using external systems and services with the Secure File Storage Service, satisfying NIST SP 800-53 AC-20 (Use of External Systems).

## Scope
Applies to any external systems, third-party services, cloud providers, or remote storage (examples: HashiCorp Vault, AWS S3 via Roles Anywhere, MinIO, external identity providers) that are used by the application or its administrators.

## Definitions
- **External System**: Any system outside the administrative control of the application host (cloud storage, third-party APIs, external identity providers).
- **Trusted External Service**: An external system that has been authorized and documented for use with this application.

## Allowed External Systems
- HashiCorp Vault (shared Vault infrastructure) — secrets management
- Keycloak (external identity provider) — authentication/authorization
- AWS S3 (via Roles Anywhere) — object storage
- MinIO (S3-compatible) — local or managed object storage (as configured)

> NOTE: Any additional external system must be approved via the Approval Process below before provisioning or integration.

## Authorization & Approval Process
1. Submit a request including: service name, provider, purpose, data classification, data flows, and required permissions.
2. Security review: owner documents risks, required controls, and mitigation (encryption, IAM, logging).
3. Approval: application owner and system owner must sign off before any credentials or integration are enabled.
4. Record the approved external system in `docs/EXTERNAL_SYSTEMS_REGISTER.md`.

## Data Handling & Protection
- Classify data before sending to external systems (Public / Internal / Confidential / Restricted).
- Encrypt data in transit using TLS 1.2+ (TLS 1.3 preferred).
- Encrypt sensitive data at rest when supported by the external system (server-side or client-side encryption).
- Minimize data shared: use tokens, references, or limited-scope credentials where possible.

## Access Controls & Credentials
- Use short-lived credentials where possible (e.g., AWS Roles Anywhere, Vault AppRole, temporary tokens).
- Store all long- or short-lived secrets in Vault; never hardcode credentials in source code or repo.
- Apply least privilege for external-system roles (limit S3 bucket access to required prefixes).
- Require MFA for administrative accounts that manage external systems.

## Network & Transport Requirements
- All connections to external systems must use authenticated TLS endpoints.
- If external systems are publicly reachable, use IP allowlists, VPC endpoints, or private networking where available.

## Logging, Monitoring & Audit
- Enable audit logging on external systems (Vault audit, Keycloak events, S3 access logs).
- Forward or aggregate external-system logs into the centralized logging/monitoring stack (if available).
- Periodically review external-system access logs for suspicious activity.

## Data Transfer & Export Controls
- Export of Restricted or Confidential data to external systems requires explicit approval and additional controls (encryption at rest, contract terms).
- Use safe transfer mechanisms (signed URLs with expiry, encrypted archives).

## Portable Storage & External Devices
- Prohibit copying sensitive data to portable storage without approval.
- If portable storage is required, encrypt and track devices per the organization's data-handling policy.

## Exceptions & Revocation
- Temporary exceptions must be documented with an owner, justification, and expiration date.
- The security owner may revoke external-system access immediately upon suspected compromise.

## Contacts
- Application Owner: `app-owner@example.local`
- Security Owner: `security@example.local`
- Operations: `ops@example.local`

## Recordkeeping
- Maintain `docs/EXTERNAL_SYSTEMS_REGISTER.md` with: service name, provider, purpose, owner, approval date, controls applied, and expiration/rotation schedule.

## Last Updated
- 10 December 2025
