FROM httpd:alpine

# Update base packages and install wget, jq for Vault API calls to pick up security fixes
RUN apk update && apk upgrade --no-cache && apk add --no-cache wget jq

# Copy entrypoint script
COPY scripts/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Use custom entrypoint
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
