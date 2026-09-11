#!/usr/bin/env bash
#
# Vault Setup Script
#
# This script configures HashiCorp Vault with:
# - JWT authentication method
# - Identity groups (readonly, readwrite)
# - Group aliases for JWT auth
# - ACL policies for database access
# - Database roles with MongoDB credentials
#
# Prerequisites:
# - Vault CLI installed and in PATH
# - VAULT_ADDR environment variable set
# - VAULT_TOKEN environment variable set (or logged in)
# - Environment variables configured (see .env.vault.example)
# - MongoDB running and accessible
#
# Environment Variables Required:
# - VAULT_ADDR: Vault server address
# - VAULT_TOKEN: Vault authentication token
# - OIDC_DISCOVERY_URL: IBM Verify OIDC discovery URL
# - BOUND_AUDIENCES: Client ID for JWT validation
# - MONGO_HOST: MongoDB hostname (default: mongodb)
# - MONGO_PORT: MongoDB port (default: 27017)
# - MONGO_USERNAME: MongoDB admin username (default: admin)
# - MONGO_PASSWORD: MongoDB admin password
#

set -euo pipefail

#############################################
# Auto-source environment file
#############################################

# Try to find and source .env file
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VAULT_SCRIPTS_DIR="$(dirname "$SCRIPT_DIR")"

# Look for .env file in the vault scripts directory
if [[ -f "$VAULT_SCRIPTS_DIR/.env" ]]; then
    print_status() { echo -e "\033[0;36m==>\033[0m $1"; }
    print_status "Auto-sourcing environment file: $VAULT_SCRIPTS_DIR/.env"
    # shellcheck disable=SC1090
    source "$VAULT_SCRIPTS_DIR/.env"
    print_status "Environment variables loaded from .env"
elif [[ -f "$VAULT_SCRIPTS_DIR/.env.vault" ]]; then
    print_status() { echo -e "\033[0;36m==>\033[0m $1"; }
    print_status "Auto-sourcing environment file: $VAULT_SCRIPTS_DIR/.env.vault"
    # shellcheck disable=SC1090
    source "$VAULT_SCRIPTS_DIR/.env.vault"
    print_status "Environment variables loaded from .env.vault"
fi

# Color codes for output
readonly GREEN='\033[0;32m'
readonly BLUE='\033[0;34m'
readonly RED='\033[0;31m'
readonly TEAL='\033[0;36m'
readonly YELLOW='\033[1;33m'
readonly NC='\033[0m' # No Color

#############################################
# Print Functions
#############################################

print_status() {
    echo -e "${TEAL}==>${NC} $1"
}

print_success() {
    echo -e "${GREEN}==>${NC} $1"
}

print_error() {
    echo -e "${RED}==>${NC} $1" >&2
}

print_warning() {
    echo -e "${YELLOW}==>${NC} $1"
}

print_section_header() {
    local title=$1
    echo
    echo -e "${BLUE}╔═══════════════════════════════════════════════════════════╗${NC}"
    printf "${BLUE}║${NC}  %-57s${BLUE}║${NC}\n" "$title"
    echo -e "${BLUE}╚═══════════════════════════════════════════════════════════╝${NC}"
}

#############################################
# Validation Functions
#############################################

check_prerequisites() {
    print_section_header "Checking Prerequisites"
    
    # Check if vault CLI is installed
    if ! command -v vault &> /dev/null; then
        print_error "Vault CLI is not installed or not in PATH"
        print_error "Please install Vault CLI: https://www.vaultproject.io/downloads"
        exit 1
    fi
    print_success "Vault CLI found: $(vault version | head -n1)"
    
    # Check if VAULT_ADDR is set
    if [[ -z "${VAULT_ADDR:-}" ]]; then
        print_error "VAULT_ADDR environment variable is not set"
        print_error "Example: export VAULT_ADDR=https://vault.example.com:8200"
        exit 1
    fi
    print_success "VAULT_ADDR: $VAULT_ADDR"
    
    # Check if we can connect to Vault
    if ! vault status &> /dev/null; then
        print_error "Cannot connect to Vault at $VAULT_ADDR"
        print_error "Please check your VAULT_ADDR and network connectivity"
        exit 1
    fi
    print_success "Successfully connected to Vault"
    
    # Check if we're authenticated
    if ! vault token lookup &> /dev/null; then
        print_error "Not authenticated to Vault"
        print_error "Please set VAULT_TOKEN or run 'vault login'"
        exit 1
    fi
    print_success "Vault authentication verified"
    
    echo
}

#############################################
# Environment Validation
#############################################

validate_environment() {
    print_section_header "Validating Environment Variables"
    
    local required_vars=(
        "VAULT_ADDR:Vault server address"
        "OIDC_DISCOVERY_URL:IBM Verify OIDC discovery URL"
        "BOUND_AUDIENCES:JWT audience claim (client ID)"
        "MONGO_HOST:MongoDB hostname"
        "MONGO_PORT:MongoDB port"
        "MONGO_USERNAME:MongoDB admin username"
        "MONGO_PASSWORD:MongoDB admin password"
    )
    
    local missing=0
    
    for var_desc in "${required_vars[@]}"; do
        IFS=':' read -r var desc <<< "$var_desc"
        if [[ -z "${!var:-}" ]]; then
            print_error "Required variable $var is not set ($desc)"
            ((missing++))
        else
            print_success "$var is set"
        fi
    done
    
    # Set defaults for optional variables
    export MONGO_DATABASE="${MONGO_DATABASE:-test}"
    export VAULT_DB_CONNECTION_NAME="${VAULT_DB_CONNECTION_NAME:-docdb}"
    export VAULT_DB_DEFAULT_TTL="${VAULT_DB_DEFAULT_TTL:-1h}"
    export VAULT_DB_MAX_TTL="${VAULT_DB_MAX_TTL:-24h}"
    export VAULT_AUDIT_LOG_PATH="${VAULT_AUDIT_LOG_PATH:-/var/log/vault_audit.log}"
    export VAULT_VERBOSE_OIDC_LOGGING="${VAULT_VERBOSE_OIDC_LOGGING:-true}"
    
    if [[ $missing -gt 0 ]]; then
        print_error "$missing required variable(s) missing"
        print_error "Please set the required environment variables"
        print_error "See .env.vault.example for reference"
        exit 1
    fi
    
    print_success "All required environment variables are set"
    echo
}

#############################################
# Database Secrets Engine Setup
#############################################

setup_database_secrets_engine() {
    print_section_header "Setting Up Database Secrets Engine"
    
    # Check if database secrets engine is already enabled
    if vault secrets list -format=json | jq -e '.["database/"]' &> /dev/null; then
        print_warning "Database secrets engine already enabled at database/"
    else
        print_status "Enabling database secrets engine..."
        vault secrets enable database
        print_success "Database secrets engine enabled"
    fi
    
    # Configure MongoDB connection
    print_status "Configuring MongoDB connection '$VAULT_DB_CONNECTION_NAME'..."
    
    local connection_url="mongodb://{{username}}:{{password}}@${MONGO_HOST}:${MONGO_PORT}/admin?authSource=admin"
    
    vault write database/config/$VAULT_DB_CONNECTION_NAME \
        plugin_name="mongodb-database-plugin" \
        allowed_roles="readonly,readwrite" \
        connection_url="$connection_url" \
        username="$MONGO_USERNAME" \
        password="$MONGO_PASSWORD" \
        verify_connection=true
    
    print_success "MongoDB connection '$VAULT_DB_CONNECTION_NAME' configured"
    print_success "Connection URL: mongodb://${MONGO_HOST}:${MONGO_PORT}/admin"
    
    echo
}

#############################################
# JWT Authentication Setup
#############################################

setup_jwt_auth() {
    print_section_header "Setting Up JWT Authentication"
    
    # Check if JWT auth method is already enabled
    if vault auth list -format=json | jq -e '.["jwt/"]' &> /dev/null; then
        print_warning "JWT auth method already enabled at jwt/"
    else
        print_status "Enabling JWT auth method..."
        vault auth enable jwt
        print_success "JWT auth method enabled"
    fi
    
    echo
}

#############################################
# JWT Configuration
#############################################

configure_jwt_auth() {
    print_section_header "Configuring JWT Authentication"
    
    # Configure JWT auth with OIDC discovery (without client credentials for JWT mode)
    print_status "Configuring JWT auth with OIDC discovery..."
    vault write auth/jwt/config \
        oidc_discovery_url="$OIDC_DISCOVERY_URL"
    print_success "JWT auth configured with OIDC discovery URL: $OIDC_DISCOVERY_URL"
    print_warning "Note: oidc_client_id and oidc_client_secret are NOT set (JWT mode, not OIDC mode)"
    
    # Create JWT role
    print_status "Creating JWT role 'default'..."
    vault write auth/jwt/role/default \
        role_type="jwt" \
        bound_audiences="$BOUND_AUDIENCES" \
        user_claim="preferred_username" \
        groups_claim="groups" \
        verbose_oidc_logging="$VAULT_VERBOSE_OIDC_LOGGING" \
        claim_mappings.name="name" \
        claim_mappings.aud="aud"
    print_success "JWT role 'default' created"
    print_success "Bound audiences: $BOUND_AUDIENCES"
    
    echo
}

#############################################
# Identity Groups Setup
#############################################

setup_identity_groups() {
    print_section_header "Setting Up Identity Groups"
    
    # Create readonly group
    print_status "Creating 'readonly' identity group..."
    if vault read identity/group/name/readonly &> /dev/null; then
        print_warning "Group 'readonly' already exists"
    else
        vault write identity/group \
            name="readonly" \
            type="external" \
            policies="readonly" \
            metadata.description="Readonly access group"
        print_success "Group 'readonly' created with metadata"
    fi
    
    # Create readwrite group
    print_status "Creating 'readwrite' identity group..."
    if vault read identity/group/name/readwrite &> /dev/null; then
        print_warning "Group 'readwrite' already exists"
    else
        vault write identity/group \
            name="readwrite" \
            type="external" \
            policies="readwrite" \
            metadata.description="Readwrite access group"
        print_success "Group 'readwrite' created with metadata"
    fi
    
    echo
}

#############################################
# Group Aliases Setup
#############################################

setup_group_aliases() {
    print_section_header "Setting Up Group Aliases"
    
    # Get JWT accessor ID
    print_status "Retrieving JWT auth accessor ID..."
    export ACCESSOR_ID=$(vault auth list -format=json | jq -r '.["jwt/"].accessor')
    
    if [[ -z "$ACCESSOR_ID" || "$ACCESSOR_ID" == "null" ]]; then
        print_error "Failed to retrieve JWT accessor ID"
        exit 1
    fi
    print_success "JWT accessor ID: $ACCESSOR_ID"
    
    # Get readonly group ID
    print_status "Retrieving readonly group ID..."
    export RO_GROUP_ID=$(vault read identity/group/name/readonly -format=json | jq -r '.data.id')
    
    if [[ -z "$RO_GROUP_ID" || "$RO_GROUP_ID" == "null" ]]; then
        print_error "Failed to retrieve readonly group ID"
        exit 1
    fi
    print_success "Readonly group ID: $RO_GROUP_ID"
    
    # Get readwrite group ID
    print_status "Retrieving readwrite group ID..."
    export RW_GROUP_ID=$(vault read identity/group/name/readwrite -format=json | jq -r '.data.id')
    
    if [[ -z "$RW_GROUP_ID" || "$RW_GROUP_ID" == "null" ]]; then
        print_error "Failed to retrieve readwrite group ID"
        exit 1
    fi
    print_success "Readwrite group ID: $RW_GROUP_ID"
    
    # Create group alias for readonly
    print_status "Creating group alias for 'readonly'..."
    vault write identity/group-alias \
        name="readonly" \
        mount_accessor="$ACCESSOR_ID" \
        canonical_id="$RO_GROUP_ID"
    print_success "Group alias for 'readonly' created"
    
    # Create group alias for readwrite
    print_status "Creating group alias for 'readwrite'..."
    vault write identity/group-alias \
        name="readwrite" \
        mount_accessor="$ACCESSOR_ID" \
        canonical_id="$RW_GROUP_ID"
    print_success "Group alias for 'readwrite' created"
    
    echo
}

#############################################
# ACL Policies Setup
#############################################

setup_acl_policies() {
    print_section_header "Setting Up ACL Policies"
    
    # Create readonly policy
    print_status "Creating 'readonly' ACL policy..."
    vault policy write readonly - <<EOF
# Allow reading database credentials for readonly role
path "database/creds/readonly" {
  capabilities = ["read"]
}

# Allow listing database roles
path "database/roles" {
  capabilities = ["list"]
}
EOF
    print_success "Policy 'readonly' created"
    
    # Create readwrite policy
    print_status "Creating 'readwrite' ACL policy..."
    vault policy write readwrite - <<EOF
# Allow reading database credentials for readwrite role
path "database/creds/readwrite" {
  capabilities = ["read"]
}

# Allow listing database roles
path "database/roles" {
  capabilities = ["list"]
}
EOF
    print_success "Policy 'readwrite' created"
    
    echo
}

#############################################
# Database Roles Setup
#############################################

setup_database_roles() {
    print_section_header "Setting Up Database Roles"
    
    # Check if database connection exists
    print_status "Checking database connection '$VAULT_DB_CONNECTION_NAME'..."
    if ! vault read database/config/$VAULT_DB_CONNECTION_NAME &> /dev/null; then
        print_warning "Database connection '$VAULT_DB_CONNECTION_NAME' not found"
        print_warning "Please run setup_database_secrets_engine first"
        print_warning "Skipping database role creation"
        echo
        return 0
    fi
    print_success "Database connection '$VAULT_DB_CONNECTION_NAME' found"
    
    # Create readonly database role
    print_status "Creating 'readonly' database role..."
    vault write database/roles/readonly \
        db_name="$VAULT_DB_CONNECTION_NAME" \
        creation_statements="{ \"db\": \"admin\", \"roles\": [{ \"db\": \"$MONGO_DATABASE\", \"role\": \"read\" }] }" \
        default_ttl="$VAULT_DB_DEFAULT_TTL" \
        max_ttl="$VAULT_DB_MAX_TTL"
    print_success "Database role 'readonly' created for database '$MONGO_DATABASE'"
    
    # Create readwrite database role
    print_status "Creating 'readwrite' database role..."
    vault write database/roles/readwrite \
        db_name="$VAULT_DB_CONNECTION_NAME" \
        creation_statements="{ \"db\": \"admin\", \"roles\": [{ \"db\": \"$MONGO_DATABASE\", \"role\": \"readWrite\" }] }" \
        default_ttl="$VAULT_DB_DEFAULT_TTL" \
        max_ttl="$VAULT_DB_MAX_TTL"
    print_success "Database role 'readwrite' created for database '$MONGO_DATABASE'"
    
    echo
}

#############################################
# Audit Logging Setup
#############################################

setup_audit_logging() {
    print_section_header "Setting Up Audit Logging"
    
    # Check if audit logging is already enabled
    if vault audit list -format=json | jq -e '.["file/"]' &> /dev/null; then
        print_warning "File audit device already enabled"
        echo
        return 0
    fi
    
    # Create audit log file if it doesn't exist (if we have permissions)
    print_status "Checking audit log file: $VAULT_AUDIT_LOG_PATH"
    if [[ -w "$(dirname "$VAULT_AUDIT_LOG_PATH")" ]]; then
        if [[ ! -f "$VAULT_AUDIT_LOG_PATH" ]]; then
            print_status "Creating audit log file..."
            touch "$VAULT_AUDIT_LOG_PATH" 2>/dev/null || true
            chmod 640 "$VAULT_AUDIT_LOG_PATH" 2>/dev/null || true
            print_success "Audit log file created"
        else
            print_success "Audit log file already exists"
        fi
    else
        print_warning "Cannot create audit log file (insufficient permissions)"
        print_warning "Please create it manually: sudo touch $VAULT_AUDIT_LOG_PATH"
        print_warning "And set permissions: sudo chmod 640 $VAULT_AUDIT_LOG_PATH"
    fi
    
    # Enable audit logging
    print_status "Enabling file audit device..."
    vault audit enable file file_path="$VAULT_AUDIT_LOG_PATH"
    print_success "Audit logging enabled at $VAULT_AUDIT_LOG_PATH"
    
    echo
}

#############################################
# Verification
#############################################

verify_setup() {
    print_section_header "Verifying Setup"
    
    local errors=0
    
    # Verify database secrets engine
    print_status "Verifying database secrets engine..."
    if vault secrets list -format=json | jq -e '.["database/"]' &> /dev/null; then
        print_success "Database secrets engine: OK"
    else
        print_error "Database secrets engine: FAILED"
        ((errors++))
    fi
    
    # Verify database connection
    print_status "Verifying database connection..."
    if vault read database/config/$VAULT_DB_CONNECTION_NAME &> /dev/null; then
        print_success "Database connection '$VAULT_DB_CONNECTION_NAME': OK"
    else
        print_error "Database connection '$VAULT_DB_CONNECTION_NAME': FAILED"
        ((errors++))
    fi
    
    # Verify JWT auth
    print_status "Verifying JWT auth method..."
    if vault auth list -format=json | jq -e '.["jwt/"]' &> /dev/null; then
        print_success "JWT auth method: OK"
    else
        print_error "JWT auth method: FAILED"
        ((errors++))
    fi
    
    # Verify JWT configuration
    print_status "Verifying JWT configuration..."
    if vault read auth/jwt/config &> /dev/null; then
        print_success "JWT configuration: OK"
    else
        print_error "JWT configuration: FAILED"
        ((errors++))
    fi
    
    # Verify JWT role
    print_status "Verifying JWT role..."
    if vault read auth/jwt/role/default &> /dev/null; then
        print_success "JWT role 'default': OK"
    else
        print_error "JWT role 'default': FAILED"
        ((errors++))
    fi
    
    # Verify groups
    print_status "Verifying identity groups..."
    if vault read identity/group/name/readonly &> /dev/null; then
        print_success "Group 'readonly': OK"
    else
        print_error "Group 'readonly': FAILED"
        ((errors++))
    fi
    
    if vault read identity/group/name/readwrite &> /dev/null; then
        print_success "Group 'readwrite': OK"
    else
        print_error "Group 'readwrite': FAILED"
        ((errors++))
    fi
    
    # Verify policies
    print_status "Verifying ACL policies..."
    if vault policy read readonly &> /dev/null; then
        print_success "Policy 'readonly': OK"
    else
        print_error "Policy 'readonly': FAILED"
        ((errors++))
    fi
    
    if vault policy read readwrite &> /dev/null; then
        print_success "Policy 'readwrite': OK"
    else
        print_error "Policy 'readwrite': FAILED"
        ((errors++))
    fi
    
    # Verify database roles
    print_status "Verifying database roles..."
    if vault read database/roles/readonly &> /dev/null; then
        print_success "Database role 'readonly': OK"
    else
        print_error "Database role 'readonly': FAILED"
        ((errors++))
    fi
    
    if vault read database/roles/readwrite &> /dev/null; then
        print_success "Database role 'readwrite': OK"
    else
        print_error "Database role 'readwrite': FAILED"
        ((errors++))
    fi
    
    # Verify audit logging
    print_status "Verifying audit logging..."
    if vault audit list -format=json | jq -e '.["file/"]' &> /dev/null; then
        print_success "Audit logging: OK"
    else
        print_warning "Audit logging: NOT ENABLED (optional)"
    fi
    
    echo
    
    if [[ $errors -eq 0 ]]; then
        print_success "All verifications passed!"
        return 0
    else
        print_error "$errors verification(s) failed"
        return 1
    fi
}

#############################################
# Summary
#############################################

print_summary() {
    print_section_header "Setup Summary"
    
    echo -e "${GREEN}Vault Configuration Completed Successfully!${NC}"
    echo
    echo -e "${TEAL}Components Configured:${NC}"
    echo "  ✓ Database Secrets Engine (database/)"
    echo "  ✓ MongoDB Connection ($VAULT_DB_CONNECTION_NAME)"
    echo "  ✓ JWT Authentication Method (jwt/)"
    echo "  ✓ JWT Configuration (OIDC: $OIDC_DISCOVERY_URL)"
    echo "  ✓ JWT Role (default)"
    echo "  ✓ Identity Groups (readonly, readwrite)"
    echo "  ✓ Group Aliases for JWT auth"
    echo "  ✓ ACL Policies (readonly, readwrite)"
    echo "  ✓ Database Roles (readonly, readwrite)"
    
    if vault audit list -format=json | jq -e '.["file/"]' &> /dev/null; then
        echo "  ✓ Audit Logging ($VAULT_AUDIT_LOG_PATH)"
    else
        echo "  ⚠ Audit Logging (not enabled)"
    fi
    
    echo
    echo -e "${TEAL}Configuration Details:${NC}"
    echo "  MongoDB: mongodb://${MONGO_HOST}:${MONGO_PORT}/${MONGO_DATABASE}"
    echo "  OIDC Discovery: $OIDC_DISCOVERY_URL"
    echo "  Bound Audiences: $BOUND_AUDIENCES"
    echo "  Credential TTL: $VAULT_DB_DEFAULT_TTL (max: $VAULT_DB_MAX_TTL)"
    
    echo
    echo -e "${TEAL}Next Steps:${NC}"
    echo "  1. Test JWT authentication with a valid token"
    echo "  2. Verify group membership is correctly mapped"
    echo "  3. Test database credential generation"
    echo "  4. Monitor audit logs for security events"
    echo
    echo -e "${YELLOW}Example Commands:${NC}"
    echo "  # Test JWT authentication"
    echo "  vault write auth/jwt/login role=default jwt=\$JWT_TOKEN"
    echo
    echo "  # Test readonly credentials"
    echo "  vault read database/creds/readonly"
    echo
    echo "  # Test readwrite credentials"
    echo "  vault read database/creds/readwrite"
    echo
    echo "  # View audit logs"
    echo "  tail -f $VAULT_AUDIT_LOG_PATH"
    echo
    echo "  # List JWT role details"
    echo "  vault read auth/jwt/role/default"
    echo
}

#############################################
# Help
#############################################

show_help() {
    echo -e "
${TEAL}Vault Setup Script${NC}

${GREEN}DESCRIPTION:${NC}
    Configures HashiCorp Vault with complete MongoDB integration including:
    - Database secrets engine with MongoDB connection
    - JWT authentication with IBM Verify OIDC
    - Identity groups and policies for access control
    - Audit logging for security compliance

${GREEN}USAGE:${NC}
    # 1. Copy and configure environment variables
    cp .env.vault.example .env.vault
    # Edit .env.vault with your values
    
    # 2. Source the environment file
    source .env.vault
    
    # 3. Run the setup script
    $0 [OPTIONS]

${GREEN}OPTIONS:${NC}
    -h, --help              Show this help message and exit
    --skip-verification     Skip verification step after setup
    --dry-run               Show what would be done without making changes

${GREEN}PREREQUISITES:${NC}
    - Vault CLI installed and in PATH
    - jq installed for JSON parsing
    - MongoDB running and accessible
    - IBM Verify tenant configured
    - Environment variables set (see .env.vault.example)

${GREEN}REQUIRED ENVIRONMENT VARIABLES:${NC}
    VAULT_ADDR              Vault server address
    VAULT_TOKEN             Vault authentication token
    OIDC_DISCOVERY_URL      IBM Verify OIDC discovery URL
    BOUND_AUDIENCES         JWT audience claim (client ID)
    MONGO_HOST              MongoDB hostname
    MONGO_PORT              MongoDB port
    MONGO_USERNAME          MongoDB admin username
    MONGO_PASSWORD          MongoDB admin password

${GREEN}OPTIONAL ENVIRONMENT VARIABLES:${NC}
    MONGO_DATABASE          Database name (default: test)
    VAULT_DB_CONNECTION_NAME    Connection name (default: docdb)
    VAULT_DB_DEFAULT_TTL    Credential TTL (default: 1h)
    VAULT_DB_MAX_TTL        Max credential TTL (default: 24h)
    VAULT_AUDIT_LOG_PATH    Audit log path (default: /var/log/vault_audit.log)

${GREEN}EXAMPLES:${NC}
    # Normal setup with environment file
    source .env.vault
    $0

    # Skip verification
    $0 --skip-verification

    # Dry run (show what would be done)
    $0 --dry-run

${GREEN}COMPONENTS CONFIGURED:${NC}
    1. Database Secrets Engine (database/)
    2. MongoDB Connection Configuration
    3. JWT Authentication Method (jwt/)
    4. JWT OIDC Configuration
    5. JWT Role (default)
    6. Identity Groups (readonly, readwrite)
    7. Group Aliases for JWT auth
    8. ACL Policies (readonly, readwrite)
    9. Database Roles (readonly, readwrite)
    10. Audit Logging (optional)

${GREEN}SECURITY NOTES:${NC}
    - Store .env.vault securely and never commit it to version control
    - Use strong passwords for MongoDB
    - Rotate credentials regularly
    - Monitor audit logs for suspicious activity
    - Use appropriate TTL values for your security requirements
"
}

#############################################
# Main
#############################################

main() {
    local skip_verification=false
    local dry_run=false
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            --skip-verification)
                skip_verification=true
                shift
                ;;
            --dry-run)
                dry_run=true
                shift
                ;;
            *)
                print_error "Unknown option: $1"
                echo "Use --help for usage information"
                exit 1
                ;;
        esac
    done
    
    if [[ "$dry_run" == "true" ]]; then
        print_warning "DRY RUN MODE - No changes will be made"
        echo
    fi
    
    # Run setup steps
    check_prerequisites
    
    if [[ "$dry_run" == "false" ]]; then
        validate_environment
        setup_database_secrets_engine
        setup_jwt_auth
        configure_jwt_auth
        setup_identity_groups
        setup_group_aliases
        setup_acl_policies
        setup_database_roles
        setup_audit_logging
        
        if [[ "$skip_verification" == "false" ]]; then
            verify_setup
        fi
        
        print_summary
    else
        print_status "Would execute the following steps:"
        echo "  1. Validate environment variables"
        echo "  2. Setup database secrets engine"
        echo "  3. Configure MongoDB connection"
        echo "  4. Enable JWT authentication"
        echo "  5. Configure JWT with OIDC"
        echo "  6. Create JWT role"
        echo "  7. Create identity groups (readonly, readwrite)"
        echo "  8. Create group aliases"
        echo "  9. Create ACL policies"
        echo "  10. Create database roles"
        echo "  11. Setup audit logging"
        echo "  12. Verify setup"
        echo
        print_warning "Run without --dry-run to apply changes"
    fi
}

# Run main function
main "$@"

# Made with Bob