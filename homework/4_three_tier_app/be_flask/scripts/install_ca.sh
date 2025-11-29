#!/bin/sh
set -eu

VAULT_ADDR="${VAULT_ADDR:?VAULT_ADDR environment variable is required}"
VAULT_ROLE_ID="${VAULT_ROLE_ID:?VAULT_ROLE_ID environment variable is required}"
VAULT_SECRET_ID="${VAULT_SECRET_ID:?VAULT_SECRET_ID environment variable is required}"
VAULT_AUTH_PATH="${VAULT_AUTH_PATH:?VAULT_AUTH_PATH environment variable is required}"

# Path in KV where app secrets live (KV v2)
KV_PATH="secret/data/mes_local_cloud/app/flask"
CA_PATH="/usr/local/share/ca-certificates/vault_pki_ca.crt"

HTTP_CLIENT=""

echo "[install_ca.sh] Authenticating to Vault and fetching CA_chain (if present)"

if [ -z "$VAULT_ROLE_ID" ] || [ -z "$VAULT_SECRET_ID" ]; then
  echo "[install_ca.sh] VAULT_ROLE_ID or VAULT_SECRET_ID missing; skipping CA install"
  exit 0
fi

# Prefer curl, fall back to wget
if command -v curl >/dev/null 2>&1; then
  HTTP_CLIENT="curl"
elif command -v wget >/dev/null 2>&1; then
  HTTP_CLIENT="wget"
else
  echo "[install_ca.sh] WARN: neither curl nor wget is available; skipping CA install"
  exit 0
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "[install_ca.sh] WARN: jq is not installed; cannot parse Vault response; skipping CA install"
  exit 0
fi

# Support a pre-provisioned CA file to validate Vault (--cacert), or allow
# skipping verification via VAULT_SKIP_VERIFY=true (not recommended).
VAULT_CACERT="${VAULT_CACERT:-}"
VAULT_SKIP_VERIFY="${VAULT_SKIP_VERIFY:-false}"

curl_common_opts() {
  # base curl options
  opts="--fail --silent --show-error --location --max-time 10 --retry 3 --retry-delay 2"
  if [ -n "$VAULT_CACERT" ] && [ -f "$VAULT_CACERT" ]; then
    opts="$opts --cacert $VAULT_CACERT"
  elif [ "$VAULT_SKIP_VERIFY" = "true" ]; then
    opts="$opts --insecure"
  fi
  printf '%s' "$opts"
}

http_post() {
  url="$1"
  body="$2"
  if [ "$HTTP_CLIENT" = "curl" ]; then
    # Use command substitution unquoted so the options are split correctly
    curl $(curl_common_opts) -X POST -H "Content-Type: application/json" -d "$body" "$url"
  else
    # wget fallback: supports --no-check-certificate for skip verify
    if [ -n "$VAULT_CACERT" ] && [ -f "$VAULT_CACERT" ]; then
      # wget doesn't have a simple --cacert flag in busybox; attempt --ca-certificate
      wget --ca-certificate="$VAULT_CACERT" -qO- --method=POST --header="Content-Type: application/json" --body-data="$body" "$url"
    elif [ "$VAULT_SKIP_VERIFY" = "true" ]; then
      wget --no-check-certificate -qO- --method=POST --header="Content-Type: application/json" --body-data="$body" "$url"
    else
      wget -qO- --method=POST --header="Content-Type: application/json" --body-data="$body" "$url"
    fi
  fi
}

http_get() {
  url="$1"
  token="$2"
  if [ "$HTTP_CLIENT" = "curl" ]; then
    curl $(curl_common_opts) -H "X-Vault-Token: ${token}" "$url"
  else
    if [ -n "$VAULT_CACERT" ] && [ -f "$VAULT_CACERT" ]; then
      wget --ca-certificate="$VAULT_CACERT" -qO- --header "X-Vault-Token: ${token}" "$url"
    elif [ "$VAULT_SKIP_VERIFY" = "true" ]; then
      wget --no-check-certificate -qO- --header "X-Vault-Token: ${token}" "$url"
    else
      wget -qO- --header "X-Vault-Token: ${token}" "$url"
    fi
  fi
}

AUTH_BODY="{\"role_id\":\"${VAULT_ROLE_ID}\",\"secret_id\":\"${VAULT_SECRET_ID}\"}"

AUTH_URL="${VAULT_ADDR%/}/v1/auth/${VAULT_AUTH_PATH}/login"

AUTH_RESPONSE=""
if ! AUTH_RESPONSE=$(http_post "$AUTH_URL" "$AUTH_BODY" 2>&1); then
  echo "[install_ca.sh] WARN: Vault AppRole login failed; continuing without CA"
  echo "[install_ca.sh] Response: $AUTH_RESPONSE"
  exit 0
fi

VAULT_TOKEN="$(printf '%s' "$AUTH_RESPONSE" | jq -r '.auth.client_token // empty')" || true
if [ -z "$VAULT_TOKEN" ]; then
  echo "[install_ca.sh] WARN: No Vault token obtained; skipping CA install"
  exit 0
fi

echo "[install_ca.sh] Obtained Vault token"

# Read KV v2 secret
KV_URL="${VAULT_ADDR%/}/v1/${KV_PATH}"
RESPONSE=""
# For downloading the CA_chain we allow skipping TLS verification explicitly
# because the Vault server may present a cert signed by the same private CA
# we're trying to fetch. This forces curl/wget to use insecure mode for this
# single request. To override, set VAULT_CACERT to a local CA file.
if [ "$HTTP_CLIENT" = "curl" ]; then
  if [ -n "$VAULT_CACERT" ] && [ -f "$VAULT_CACERT" ]; then
    if ! RESPONSE=$(curl $(curl_common_opts) -H "X-Vault-Token: ${VAULT_TOKEN}" "$KV_URL" 2>&1); then
      echo "[install_ca.sh] WARN: Failed to read KV path ${KV_PATH}; continuing"
      echo "[install_ca.sh] Response: $RESPONSE"
      exit 0
    fi
  else
    # Force --insecure for the CA download step
    if ! RESPONSE=$(curl --insecure --fail --silent --show-error --location --max-time 10 -H "X-Vault-Token: ${VAULT_TOKEN}" "$KV_URL" 2>&1); then
      echo "[install_ca.sh] WARN: Failed to read KV path ${KV_PATH}; continuing"
      echo "[install_ca.sh] Response: $RESPONSE"
      exit 0
    fi
  fi
else
  # wget fallback
  if [ -n "$VAULT_CACERT" ] && [ -f "$VAULT_CACERT" ]; then
    if ! RESPONSE=$(wget --ca-certificate="$VAULT_CACERT" -qO- --header "X-Vault-Token: ${VAULT_TOKEN}" "$KV_URL" 2>&1); then
      echo "[install_ca.sh] WARN: Failed to read KV path ${KV_PATH}; continuing"
      echo "[install_ca.sh] Response: $RESPONSE"
      exit 0
    fi
  else
    # Force --no-check-certificate for wget
    if ! RESPONSE=$(wget --no-check-certificate -qO- --header "X-Vault-Token: ${VAULT_TOKEN}" "$KV_URL" 2>&1); then
      echo "[install_ca.sh] WARN: Failed to read KV path ${KV_PATH}; continuing"
      echo "[install_ca.sh] Response: $RESPONSE"
      exit 0
    fi
  fi
fi

# Extract CA_chain (stored under data.data.CA_chain for KV v2)
CA_CHAIN="$(printf '%s' "$RESPONSE" | jq -r '.data.data.CA_chain // .data.data.ca_chain // empty')" || true

if [ -z "$CA_CHAIN" ]; then
  echo "[install_ca.sh] No CA_chain found in Vault at ${KV_PATH}; nothing to install"
  exit 0
fi

echo "[install_ca.sh] Writing CA to ${CA_PATH}"
printf '%s
' "$CA_CHAIN" > "$CA_PATH"

if command -v update-ca-certificates >/dev/null 2>&1; then
  echo "[install_ca.sh] Updating system CA bundle"
  if ! update-ca-certificates; then
    echo "[install_ca.sh] update-ca-certificates returned non-zero"
  fi
else
  echo "[install_ca.sh] update-ca-certificates not available in image"
fi

echo "[install_ca.sh] Done"
exit 0
