FROM httpd:alpine

# Update base packages and install wget, jq for Vault API calls to pick up security fixes
# Create non-root user for running Apache
# UID/GID 1000 is a common convention for the first non-system user
RUN apk update && apk upgrade --no-cache && apk add --no-cache wget jq && \
    addgroup -g 1000 apache && \
    adduser -D -u 1000 -G apache apache && \
    mkdir -p /usr/local/apache2/conf/extra/certs /usr/local/apache2/logs && \
    chmod 777 /usr/local/apache2/logs /usr/local/apache2/conf/extra/certs

# Copy entrypoint script
COPY scripts/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Note: Container starts as root for certificate fetching, but Apache httpd will run as 'apache' user
# This is configured via httpd.conf User/Group directives

# Use custom entrypoint
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

# This version is not perfecet due to blfks file system that does not allow chown