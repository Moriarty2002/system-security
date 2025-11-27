FROM osixia/openldap:1.5.0

# Install required tools for Vault integration
USER root

# Update sources.list to use Debian archive (Buster is EOL)
RUN sed -i 's/deb.debian.org/archive.debian.org/g' /etc/apt/sources.list && \
    sed -i 's|security.debian.org/debian-security|archive.debian.org/debian-security|g' /etc/apt/sources.list && \
    sed -i 's|ftp.debian.org/debian|archive.debian.org/debian|g' /etc/apt/sources.list && \
    sed -i '/stretch-updates/d' /etc/apt/sources.list && \
    sed -i '/buster-updates/d' /etc/apt/sources.list && \
    sed -i '/buster-backports/d' /etc/apt/sources.list && \
    echo "Acquire::Check-Valid-Until \"false\";" > /etc/apt/apt.conf.d/99no-check-valid-until

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    wget \
    jq \
    openssl \
    ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Copy custom entrypoint script
COPY scripts/entrypoint.sh /usr/local/bin/ldap-entrypoint.sh
RUN chmod +x /usr/local/bin/ldap-entrypoint.sh

# Create certs directory if it doesn't exist
RUN mkdir -p /container/service/slapd/assets/certs

# Set entrypoint to our custom script
ENTRYPOINT ["/usr/local/bin/ldap-entrypoint.sh"]
