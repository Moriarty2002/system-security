#!/bin/bash
# Generate TLS certificates for LDAP server
# This script creates a self-signed CA and server certificate for LDAPS

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CERTS_DIR="$SCRIPT_DIR/../certs"

echo "🔐 Generating TLS certificates for LDAP server..."

# Create certs directory
mkdir -p "$CERTS_DIR"
cd "$CERTS_DIR"

# Generate CA private key
if [ ! -f "ca-key.pem" ]; then
    echo "📝 Generating CA private key..."
    openssl genrsa -out ca-key.pem 4096
    chmod 600 ca-key.pem
fi

# Generate CA certificate
if [ ! -f "ca-cert.pem" ]; then
    echo "📝 Generating CA certificate..."
    openssl req -new -x509 -days 3650 -key ca-key.pem -out ca-cert.pem \
        -subj "/C=IT/ST=Italy/L=Milan/O=MES Cloud/OU=Security/CN=MES LDAP CA"
fi

# Generate LDAP server private key
if [ ! -f "ldap-key.pem" ]; then
    echo "📝 Generating LDAP server private key..."
    openssl genrsa -out ldap-key.pem 2048
    chmod 600 ldap-key.pem
fi

# Generate LDAP server certificate signing request
if [ ! -f "ldap-csr.pem" ]; then
    echo "📝 Generating LDAP server CSR..."
    openssl req -new -key ldap-key.pem -out ldap-csr.pem \
        -subj "/C=IT/ST=Italy/L=Milan/O=MES Cloud/OU=LDAP/CN=ldap-server"
fi

# Create OpenSSL config for SAN (Subject Alternative Names)
cat > openssl-san.cnf <<EOF
[req]
distinguished_name = req_distinguished_name
req_extensions = v3_req
prompt = no

[req_distinguished_name]
C = IT
ST = Italy
L = Milan
O = MES Cloud
OU = LDAP
CN = ldap-server

[v3_req]
keyUsage = keyEncipherment, dataEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = ldap-server
DNS.2 = ldap
DNS.3 = localhost
IP.1 = 127.0.0.1
EOF

# Sign the certificate with CA
if [ ! -f "ldap-cert.pem" ]; then
    echo "📝 Signing LDAP server certificate..."
    openssl x509 -req -days 365 -in ldap-csr.pem \
        -CA ca-cert.pem -CAkey ca-key.pem -CAcreateserial \
        -out ldap-cert.pem -extensions v3_req -extfile openssl-san.cnf
fi

# Create DH parameters for enhanced security
if [ ! -f "dhparam.pem" ]; then
    echo "📝 Generating DH parameters (this may take a while)..."
    openssl dhparam -out dhparam.pem 2048
fi

# Set proper permissions
chmod 644 ca-cert.pem ldap-cert.pem
chmod 600 ca-key.pem ldap-key.pem

echo ""
echo "✅ TLS certificates generated successfully!"
echo ""
echo "📁 Certificate files:"
echo "   CA Certificate:     $CERTS_DIR/ca-cert.pem"
echo "   LDAP Certificate:   $CERTS_DIR/ldap-cert.pem"
echo "   LDAP Private Key:   $CERTS_DIR/ldap-key.pem"
echo "   DH Parameters:      $CERTS_DIR/dhparam.pem"
echo ""
echo "🔒 These certificates are self-signed and suitable for development/testing."
echo "   For production, use certificates from a trusted CA."
