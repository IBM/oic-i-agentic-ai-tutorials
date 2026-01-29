#!/usr/bin/env bash
set -euo pipefail

#############################################
# INPUTS
#############################################
read -rp "Enter SERVICE_INSTANCE_URL: " SERVICE_INSTANCE_URL
read -rsp "Enter IAM_API_KEY: " IAM_API_KEY
echo

#############################################
# CONSTANTS & DIRECTORIES
#############################################
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KEYS_DIR="${SCRIPT_DIR}/keys"
MULTI_DIR="${KEYS_DIR}/MULTI_LINE"
SINGLE_DIR="${KEYS_DIR}/SINGLE_LINE"

CLIENT_PRIVATE_MULTI="${MULTI_DIR}/client_private_key.pem"
CLIENT_PUBLIC_MULTI="${MULTI_DIR}/client_public_key.pem"
IBM_PUBLIC_MULTI="${MULTI_DIR}/ibm_public_key.pem"

CLIENT_PRIVATE_SINGLE="${SINGLE_DIR}/client_private_key.pem"
CLIENT_PUBLIC_SINGLE="${SINGLE_DIR}/client_public_key.pem"
IBM_PUBLIC_SINGLE="${SINGLE_DIR}/ibm_public_key.pem"

mkdir -p "$MULTI_DIR" "$SINGLE_DIR"

#############################################
# PREREQUISITES
#############################################
require() {
  command -v "$1" >/dev/null || { echo "Missing dependency: $1"; exit 1; }
}

for cmd in curl jq openssl awk; do
  require "$cmd"
done

#############################################
# UTILS
#############################################
assert_json() {
  echo "$1" | jq . >/dev/null 2>&1 || {
    echo "Invalid JSON response"
    echo "$1"
    exit 1
  }
}

to_single_line() {
  awk 'NF { sub(/\r/, ""); printf "%s\\n", $0 }'
}

#############################################
# GENERATE CLIENT KEYS
#############################################
echo "Generating client RSA keys..."

openssl genpkey -algorithm RSA \
  -pkeyopt rsa_keygen_bits:4096 \
  -out "$CLIENT_PRIVATE_MULTI" >/dev/null 2>&1

openssl pkey -in "$CLIENT_PRIVATE_MULTI" \
  -pubout -out "$CLIENT_PUBLIC_MULTI" >/dev/null 2>&1

chmod 600 "$CLIENT_PRIVATE_MULTI"
chmod 644 "$CLIENT_PUBLIC_MULTI"

#############################################
# FETCH IBM KEY + SECURE EMBED STATUS
#############################################
echo "Fetching IBM public key & Secure Embed status..."

GEN_RESPONSE=$(curl -sS -X POST \
  "${SERVICE_INSTANCE_URL}/v1/embed/secure/generate-key-pair" \
  -H "IAM-API_KEY: ${IAM_API_KEY}" \
  -H "Accept: application/json")

assert_json "$GEN_RESPONSE"

ORCHESTRATE_ID=$(jq -r '.orchestrate_id' <<< "$GEN_RESPONSE")
SECURE_ENABLED=$(jq -r '.is_security_enabled // false' <<< "$GEN_RESPONSE")
jq -r '.public_key' <<< "$GEN_RESPONSE" > "$IBM_PUBLIC_MULTI"

chmod 644 "$IBM_PUBLIC_MULTI"

echo "🔎 Secure Embed enabled : $SECURE_ENABLED"

#############################################
# ENABLE SECURE EMBED (IDEMPOTENT)
#############################################
echo "Applying Secure Embed configuration..."

jq -n \
  --arg orchestrate_id "$ORCHESTRATE_ID" \
  --arg client_public_key "$(cat "$CLIENT_PUBLIC_MULTI")" \
  --arg ibm_public_key "$(cat "$IBM_PUBLIC_MULTI")" \
  '{
    orchestrate_id: $orchestrate_id,
    client_public_key: $client_public_key,
    public_key: $ibm_public_key,
    is_security_enabled: true
  }' | curl -sS -X POST \
    "${SERVICE_INSTANCE_URL}/v1/embed/secure/config" \
    -H "Content-Type: application/json" \
    -H "IAM-API_KEY: ${IAM_API_KEY}" \
    -d @- | jq .


#############################################
# CREATE SINGLE-LINE KEYS
#############################################
echo "Creating single-line key versions..."

to_single_line < "$CLIENT_PRIVATE_MULTI" > "$CLIENT_PRIVATE_SINGLE"
to_single_line < "$CLIENT_PUBLIC_MULTI"  > "$CLIENT_PUBLIC_SINGLE"
to_single_line < "$IBM_PUBLIC_MULTI"     > "$IBM_PUBLIC_SINGLE"

chmod 600 "$CLIENT_PRIVATE_SINGLE"
chmod 644 "$CLIENT_PUBLIC_SINGLE" "$IBM_PUBLIC_SINGLE"

#############################################
# DONE
#############################################
echo
echo "Secure Embed setup complete"
echo
echo "📂 MULTI_LINE:"
ls -1 "$MULTI_DIR"
echo
echo "📂 SINGLE_LINE:"
ls -1 "$SINGLE_DIR"
