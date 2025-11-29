FROM quay.io/keycloak/keycloak:23.0 AS base

# Download required tools
FROM alpine:3 AS downloader
RUN apk add --no-cache curl unzip && \
    curl -L https://github.com/stedolan/jq/releases/download/jq-1.6/jq-linux64 -o /jq && \
    chmod +x /jq && \
    curl -L https://releases.hashicorp.com/vault/1.15.0/vault_1.15.0_linux_amd64.zip -o /vault.zip && \
    unzip /vault.zip && \
    chmod +x /vault

# Final image
FROM base
USER root

# Copy downloaded tools
COPY --from=downloader /jq /usr/local/bin/jq
COPY --from=downloader /vault /usr/local/bin/vault

USER keycloak

# Copy entrypoint script
COPY scripts/keycloak-entrypoint.sh /scripts/keycloak-entrypoint.sh

ENTRYPOINT ["/scripts/keycloak-entrypoint.sh"]
