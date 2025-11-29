#!/bin/sh
set -eu

echo "[entrypoint] Installing Vault PKI CA (if available)"
# Run the shell installer (mirrors Apache FE approach)
/usr/local/bin/install_ca.sh || echo "[entrypoint] CA install encountered an error (continuing)"

echo "[entrypoint] Starting Flask"
# Exec the container CMD (default: flask run)
exec "$@"
