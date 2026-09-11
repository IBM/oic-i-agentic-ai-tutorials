#!/usr/bin/env bash
#
# Environment Management Library
#
# This library provides:
# - Environment variable loading from .env files
# - Flavor-based deployment configuration
# - Required variable validation
# - Password validation
#

#############################################
# Deployment Flavor Definitions
#############################################

# Valid deployment flavors
declare -a VALID_FLAVORS=(
    "local-auth"
    "backend-only"
    "oauth-proxy"
    "backend-only-no-db"
    "local-auth-custom-ui"
    "oauth-proxy-custom-ui"
    "confused-deputy"
)

# Default flavor
DEFAULT_FLAVOR="local-auth"

#############################################
# Flavor-Specific Variable Arrays
#############################################

# Flavor: local-auth (Full stack with local authentication)
declare -a FLAVOR_LOCAL_AUTH_VARS=(
    "APP_NAME"
    "PROJECT_NAME"
    "GIT_SSH_URL"
    "ENVIRONMENT"
    "FIRST_SUPERUSER"
    "FIRST_SUPERUSER_PASSWORD"
    "SIGNUP_ACCESS_PASSWORD"
    "SECRET_KEY"
    "POSTGRES_SERVER"
    "POSTGRES_PORT"
    "POSTGRES_DB"
    "POSTGRES_USER"
    "POSTGRES_PASSWORD"
)

declare -a FLAVOR_LOCAL_AUTH_PASSWORD_VARS=(
    "FIRST_SUPERUSER_PASSWORD"
    "SIGNUP_ACCESS_PASSWORD"
    "SECRET_KEY"
    "POSTGRES_PASSWORD"
)

# Flavor: backend-only (Backend + Database with API key auth)
declare -a FLAVOR_BACKEND_ONLY_VARS=(
    "APP_NAME"
    "PROJECT_NAME"
    "GIT_SSH_URL"
    "ENVIRONMENT"
    "API_KEY"
    "POSTGRES_SERVER"
    "POSTGRES_PORT"
    "POSTGRES_DB"
    "POSTGRES_USER"
    "POSTGRES_PASSWORD"
)

declare -a FLAVOR_BACKEND_ONLY_PASSWORD_VARS=(
    "POSTGRES_PASSWORD"
)

# Flavor: oauth-proxy (Full stack with OAuth2 authentication)
declare -a FLAVOR_OAUTH_PROXY_VARS=(
    "APP_NAME"
    "PROJECT_NAME"
    "GIT_SSH_URL"
    "ENVIRONMENT"
    "OAUTH2_PROXY_COOKIE_SECRET"
    "OAUTH2_PROXY_CLIENT_ID"
    "OAUTH2_PROXY_CLIENT_SECRET"
    "OAUTH2_PROXY_OIDC_ISSUER_URL"
    "POSTGRES_SERVER"
    "POSTGRES_PORT"
    "POSTGRES_DB"
    "POSTGRES_USER"
    "POSTGRES_PASSWORD"
)

declare -a FLAVOR_OAUTH_PROXY_PASSWORD_VARS=(
    "POSTGRES_PASSWORD"
)

# Flavor: backend-only-no-db (Backend only, no database)
declare -a FLAVOR_BACKEND_ONLY_NO_DB_VARS=(
    "APP_NAME"
    "PROJECT_NAME"
    "GIT_SSH_URL"
    "ENVIRONMENT"
    "API_KEY"
)

declare -a FLAVOR_BACKEND_ONLY_NO_DB_PASSWORD_VARS=()

# Flavor: local-auth-custom-ui (Backend + Database with local auth, custom frontend)
declare -a FLAVOR_LOCAL_AUTH_CUSTOM_UI_VARS=(
    "APP_NAME"
    "PROJECT_NAME"
    "GIT_SSH_URL"
    "ENVIRONMENT"
    "FIRST_SUPERUSER"
    "FIRST_SUPERUSER_PASSWORD"
    "SECRET_KEY"
    "POSTGRES_SERVER"
    "POSTGRES_PORT"
    "POSTGRES_DB"
    "POSTGRES_USER"
    "POSTGRES_PASSWORD"
)

declare -a FLAVOR_LOCAL_AUTH_CUSTOM_UI_PASSWORD_VARS=(
    "FIRST_SUPERUSER_PASSWORD"
    "SECRET_KEY"
    "POSTGRES_PASSWORD"
)

# Flavor: oauth-proxy-custom-ui (Backend + Database + OAuth, custom frontend)
declare -a FLAVOR_OAUTH_PROXY_CUSTOM_UI_VARS=(
    "APP_NAME"
    "PROJECT_NAME"
    "GIT_SSH_URL"
    "ENVIRONMENT"
    "OAUTH2_PROXY_COOKIE_SECRET"
    "OAUTH2_PROXY_CLIENT_ID"
    "OAUTH2_PROXY_CLIENT_SECRET"
    "OAUTH2_PROXY_OIDC_ISSUER_URL"
    "POSTGRES_SERVER"
    "POSTGRES_PORT"
    "POSTGRES_DB"
    "POSTGRES_USER"
    "POSTGRES_PASSWORD"
)

declare -a FLAVOR_OAUTH_PROXY_CUSTOM_UI_PASSWORD_VARS=(
    "POSTGRES_PASSWORD"
)

# Flavor: confused-deputy (Backend + MCP Server + Vault, no database)
declare -a FLAVOR_CONFUSED_DEPUTY_VARS=(
    "APP_NAME"
    "PROJECT_NAME"
    "GIT_SSH_URL"
    "ENVIRONMENT"
    "API_KEY"
    "VAULT_ADDR"
    "JWT_AUDIENCE"
)

declare -a FLAVOR_CONFUSED_DEPUTY_PASSWORD_VARS=()

# OAuth2 Proxy variables (for validation)
declare -a OAUTH_VARS=(
    "OAUTH2_PROXY_COOKIE_SECRET"
    "OAUTH2_PROXY_CLIENT_ID"
    "OAUTH2_PROXY_CLIENT_SECRET"
    "OAUTH2_PROXY_OIDC_ISSUER_URL"
)

#############################################
# Flavor Detection and Configuration
#############################################

# Function to validate flavor name
validate_flavor() {
    local flavor=$1
    
    for valid_flavor in "${VALID_FLAVORS[@]}"; do
        if [[ "$flavor" == "$valid_flavor" ]]; then
            return 0
        fi
    done
    
    return 1
}

# Function to detect and set deployment flavor
detect_flavor() {
    local flavor="${CEN_FLAVOR:-$DEFAULT_FLAVOR}"
    
    # Validate flavor
    if ! validate_flavor "$flavor"; then
        print_error "Invalid deployment flavor: '$flavor'" "environment"
        print_error "Valid flavors are: ${VALID_FLAVORS[*]}" "environment"
        return 1
    fi
    
    # Export flavor for use in other scripts
    export CEN_FLAVOR="$flavor"
    
    print_status "Deployment flavor: $flavor" "environment"
    return 0
}

# Function to get required variables for current flavor
get_flavor_vars() {
    local flavor="${CEN_FLAVOR:-$DEFAULT_FLAVOR}"
    local var_array_name="FLAVOR_${flavor//-/_}_VARS[@]"
    # Convert to uppercase using tr for Bash 3.2 compatibility (macOS)
    var_array_name=$(echo "$var_array_name" | tr '[:lower:]' '[:upper:]')
    
    # Return the array name for indirect reference
    echo "$var_array_name"
}

# Function to get password variables for current flavor
get_flavor_password_vars() {
    local flavor="${CEN_FLAVOR:-$DEFAULT_FLAVOR}"
    local var_array_name="FLAVOR_${flavor//-/_}_PASSWORD_VARS[@]"
    # Convert to uppercase using tr for Bash 3.2 compatibility (macOS)
    var_array_name=$(echo "$var_array_name" | tr '[:lower:]' '[:upper:]')
    
    # Return the array name for indirect reference
    echo "$var_array_name"
}

# Function to set deployment flags based on flavor
set_deployment_flags_from_flavor() {
    local flavor="${CEN_FLAVOR:-$DEFAULT_FLAVOR}"
    
    case "$flavor" in
        local-auth)
            export DEPLOY_FRONTEND=true
            export DEPLOY_BACKEND=true
            export DEPLOY_DB=true
            export DEPLOY_OAUTH=false
            ;;
        backend-only)
            export DEPLOY_FRONTEND=false
            export DEPLOY_BACKEND=true
            export DEPLOY_DB=true
            export DEPLOY_OAUTH=false
            ;;
        oauth-proxy)
            export DEPLOY_FRONTEND=true
            export DEPLOY_BACKEND=true
            export DEPLOY_DB=true
            export DEPLOY_OAUTH=true
            ;;
        backend-only-no-db)
            export DEPLOY_FRONTEND=false
            export DEPLOY_BACKEND=true
            export DEPLOY_DB=false
            export DEPLOY_OAUTH=false
            ;;
        local-auth-custom-ui)
            export DEPLOY_FRONTEND=false
            export DEPLOY_BACKEND=true
            export DEPLOY_DB=true
            export DEPLOY_OAUTH=false
            ;;
        oauth-proxy-custom-ui)
            export DEPLOY_FRONTEND=false
            export DEPLOY_BACKEND=true
            export DEPLOY_DB=true
            export DEPLOY_OAUTH=true
            ;;
        confused-deputy)
            export DEPLOY_FRONTEND=true
            export DEPLOY_BACKEND=true
            export DEPLOY_DB=false
            export DEPLOY_OAUTH=false
            export DEPLOY_MCP=true
            export DEPLOY_VAULT=true
            export DEPLOY_MONGODB=true
            ;;
        *)
            print_error "Unknown flavor: $flavor" "environment"
            return 1
            ;;
    esac
    
    # Build status message based on what's being deployed
    local status_msg="Deployment flags set: Frontend=$DEPLOY_FRONTEND, Backend=$DEPLOY_BACKEND, DB=$DEPLOY_DB, OAuth=$DEPLOY_OAUTH"
    if [[ "${DEPLOY_MCP:-false}" == "true" ]]; then
        status_msg="$status_msg, MCP=$DEPLOY_MCP"
    fi
    if [[ "${DEPLOY_VAULT:-false}" == "true" ]]; then
        status_msg="$status_msg, Vault=$DEPLOY_VAULT"
    fi
    if [[ "${DEPLOY_MONGODB:-false}" == "true" ]]; then
        status_msg="$status_msg, MongoDB=$DEPLOY_MONGODB"
    fi
    print_status "$status_msg" "environment"
    return 0
}

#############################################
# Environment Loading Functions
#############################################

# Function to load environment variables from file
load_env_file() {
    local env_file=$1
    local show_values=${2:-false}
    
    if [[ ! -f "$env_file" ]]; then
        print_error "Environment file $env_file not found!" "environment"
        print_error "Please create $env_file with all required variables." "environment"
        print_error "See scripts/.env.production.example for reference." "environment"
        return 1
    fi
    
    print_status "Loading environment variables from $env_file" "environment"
    
    # Load variables from env file without executing any code
    while IFS= read -r line || [[ -n "$line" ]]; do
        # Skip comments and empty lines
        [[ "$line" =~ ^#.*$ || -z "$line" ]] && continue
        
        # Extract variable name and value
        if [[ "$line" =~ ^([A-Za-z0-9_]+)=(.*)$ ]]; then
            var_name="${BASH_REMATCH[1]}"
            var_value="${BASH_REMATCH[2]}"
            
            # Remove quotes if present
            var_value="${var_value#\"}"
            var_value="${var_value%\"}"
            var_value="${var_value#\'}"
            var_value="${var_value%\'}"
            
            # Export the variable
            export "$var_name"="$var_value"

            # If variable starts with _, also export it without the _ prefix
            # This allows usage like _GITHUB_TOKEN in .env but script sees GITHUB_TOKEN
            if [[ "$var_name" == _* ]]; then
                clean_name="${var_name#_}"
                if [[ -n "$clean_name" ]]; then
                    export "$clean_name"="$var_value"
                    if [[ "$show_values" == "true" ]]; then
                        print_status "Aliased $var_name -> $clean_name" "environment"
                    fi
                fi
            fi
            
            # Display variable only if show_values flag is true
            if [[ "$show_values" == "true" ]]; then
                print_status "Loaded $var_name=$var_value" "environment"
            fi
        fi
    done < "$env_file"
    
    return 0
}

# Function to validate OAuth variables for OAuth flavors
validate_oauth_vars() {
    local flavor="${CEN_FLAVOR:-$DEFAULT_FLAVOR}"
    
    # Only validate OAuth for OAuth-enabled flavors
    if [[ "$flavor" != "oauth-proxy" && "$flavor" != "oauth-proxy-custom-ui" ]]; then
        return 0
    fi
    
    # For OAuth flavors, all OAuth vars must be set (already checked in validate_required_vars)
    # Just validate COOKIE_SECRET length (min 16 chars)
    if [[ ${#OAUTH2_PROXY_COOKIE_SECRET} -lt 16 ]]; then
        print_error "OAUTH2_PROXY_COOKIE_SECRET must be at least 16 characters (current: ${#OAUTH2_PROXY_COOKIE_SECRET})" "environment"
        return 1
    fi
    
    print_success "OAuth2 Proxy configuration is valid!" "environment"
    return 0
}

# Function to validate all required variables based on flavor
validate_required_vars() {
    local missing_vars=()
    local invalid_vars=()
    
    # Detect and validate flavor
    if ! detect_flavor; then
        return 1
    fi
    
    # Set deployment flags based on flavor
    if ! set_deployment_flags_from_flavor; then
        return 1
    fi
    
    # Get flavor-specific variable arrays
    local flavor="${CEN_FLAVOR:-$DEFAULT_FLAVOR}"
    local vars_array_name=$(get_flavor_vars)
    local password_vars_array_name=$(get_flavor_password_vars)
    
    # Use indirect reference to get array contents
    local vars_to_check=("${!vars_array_name}")
    local password_vars_to_check=("${!password_vars_array_name}")
    
    print_status "Validating required variables for flavor: $flavor" "environment"
    
    # Check if all required variables are set
    for var_name in "${vars_to_check[@]}"; do
        if [[ -z "${!var_name:-}" ]]; then
            missing_vars+=("$var_name")
        fi
    done
    
    # Report missing variables
    if [[ ${#missing_vars[@]} -gt 0 ]]; then
        print_error "The following required environment variables are missing for flavor '$flavor':" "environment"
        for var_name in "${missing_vars[@]}"; do
            echo "  - $var_name"
        done
        print_error "Please add these variables to your environment file: $ENV_FILE" "environment"
        print_error "See .env.production.example for flavor-specific requirements" "environment"
        return 1
    fi
    
    # Validate specific variables
    local vars_to_validate=("APP_NAME" "PROJECT_NAME" "GIT_SSH_URL" "FIRST_SUPERUSER" "API_KEY")
    for var_name in "${vars_to_validate[@]}"; do
        # Skip validation if variable is not in our checked list
        local is_in_check_list=false
        for v in "${vars_to_check[@]}"; do
            if [[ "$v" == "$var_name" ]]; then
                is_in_check_list=true
                break
            fi
        done
        
        if [[ "$is_in_check_list" == "false" ]]; then
            continue
        fi
        
        local validation_func=$(get_validation_function "$var_name")
        local var_value="${!var_name:-}"
        
        if [[ -n "$validation_func" && -n "$var_value" ]]; then
            if ! $validation_func "$var_value"; then
                invalid_vars+=("$var_name")
            fi
        fi
    done
    
    # Validate password lengths
    for var_name in "${password_vars_to_check[@]}"; do
        local var_value="${!var_name:-}"
        
        # Skip empty optional passwords
        if [[ "$var_name" == "SIGNUP_ACCESS_PASSWORD" && -z "$var_value" ]]; then
            continue
        fi
        
        if [[ -n "$var_value" ]] && ! validate_password_length "$var_value" "$var_name"; then
            invalid_vars+=("$var_name")
        fi
    done
    
    # Report invalid variables
    if [[ ${#invalid_vars[@]} -gt 0 ]]; then
        print_error "The following environment variables have invalid values:" "environment"
        for var_name in "${invalid_vars[@]}"; do
            echo "  - $var_name"
        done
        return 1
    fi
    
    # Validate OAuth variables for OAuth flavors
    if ! validate_oauth_vars; then
        return 1
    fi
    
    print_success "All required environment variables are valid for flavor '$flavor'!" "environment"
    return 0
}

# Made with Bob
