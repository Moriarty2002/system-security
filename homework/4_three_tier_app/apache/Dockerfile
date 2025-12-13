FROM httpd:alpine

# Update base packages and install wget, jq for Vault API calls to pick up security fixes
# Create non-root user for running Apache
# UID/GID 1000 is a common convention for the first non-system user
RUN apk update && apk upgrade --no-cache && apk add --no-cache wget jq && \
    addgroup -g 1000 apache && \
    adduser -D -u 1000 -G apache apache && \
    chown -R apache:apache /usr/local/apache2/logs /usr/local/apache2/conf

# Copy entrypoint script
COPY scripts/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh && \
    chown apache:apache /usr/local/bin/entrypoint.sh

# Switch to non-root user
# Apache can still bind to ports 80/443 thanks to NET_BIND_SERVICE capability
USER apache

# Use custom entrypoint
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
