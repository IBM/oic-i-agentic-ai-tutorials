#!/usr/bin/env bash
#
# Secret Management Library
#
# This library provides:
# - Dynamic secret creation from environment variables
# - VITE_ variable collection
# - Initial application environment secret creation
# - Secret updates with URLs
#
#############################################
# Secret Management Functions
#############################################

# Function to build dynamic secret creation command
build_secret_literals() {
    local secret_literals=""
    
    # Read all variables from env file
    while IFS= read -r line || [[ -n "$line" ]]; do
        # Skip comments and empty lines
        [[ "$line" =~ ^#.*$ || -z "$line" ]] && continue
        
        # Extract variable name and value
        if [[ "$line" =~ ^([A-Za-z0-9_]+)=(.*)$ ]]; then
            local var_name="${BASH_REMATCH[1]}"
            local var_value="${!var_name:-}"
            
            # Skip GitHub credentials, MongoDB credentials (handled separately), and any variable starting with _
            # Variables starting with _ are considered sensitive/local-only or are aliased
            # and should not be effectively duplicated in the secret
            # MongoDB variables are handled by the MongoDB secret, not the app secret
            if [[ "$var_name" == "GITHUB_HOST" || "$var_name" == "GITHUB_TOKEN" || "$var_name" == _* || "$var_name" == MONGO_* ]]; then
                continue
            fi
            
            # Add to secret literals
            secret_literals+=" --from-literal=$var_name=\"$var_value\""
        fi
    done < "$ENV_FILE"
    
    echo "$secret_literals"
}

# Function to get all VITE_ prefixed variables
get_vite_variables() {
    local vite_vars=""
    
    # Get all exported variables
    while IFS='=' read -r name value; do
        if [[ $name == VITE_* ]]; then
            vite_vars+=" --from-literal=$name=\"$value\""
        fi
    done < <(env)
    
    echo "$vite_vars"
}

# Function to create initial application environment secret
create_initial_app_env_secret() {
    local secret_name="$APP_NAME-env"
    local secret_key_generated=false
    
    # Generate a secure random secret key if not provided or too short
    # Only needed for flavors that use SECRET_KEY (local-auth, local-auth-custom-ui)
    local flavor="${CEN_FLAVOR:-local-auth}"
    if [[ "$flavor" == "local-auth" || "$flavor" == "local-auth-custom-ui" ]]; then
        if [[ -z "${SECRET_KEY:-}" ]] || [[ ${#SECRET_KEY} -lt 8 ]]; then
            SECRET_KEY=$(openssl rand -hex 32)
            export SECRET_KEY
            secret_key_generated=true
            print_success "Generated secure secret key for backend" "secrets"
            
            # Store in output collector
            add_deployment_output "secret_key_generated" "$SECRET_KEY"
        fi
    fi
    
    # Create or update application environment secret
    if resource_exists "secret" "$secret_name"; then
        print_status "Updating $secret_name secret..." "secrets"
        oc delete secret "$secret_name"
    fi
    
    print_status "Creating initial application environment secret $secret_name..." "secrets"
    
    # Build dynamic secret creation command
    local secret_cmd="oc create secret generic $secret_name"
    secret_cmd+=$(build_secret_literals)
    
    # Execute the command
    eval "$secret_cmd"
    
    return 0
}

# Function to update application environment secret with frontend/backend URLs
update_app_env_secret_with_urls() {
    local secret_name="$APP_NAME-env"
    local frontend_url=""
    local backend_url
    
    # Get the backend URL
    backend_url=$(oc get route backend -o jsonpath='{.spec.host}' 2>/dev/null || echo "")
    
    # Get the frontend URL only if frontend is deployed
    if [[ "${DEPLOY_FRONTEND:-true}" == "true" ]]; then
        frontend_url=$(oc get route frontend -o jsonpath='{.spec.host}' 2>/dev/null || echo "")
    fi
    
    # If OAuth is enabled, these routes might not exist (which is expected).
    # We will defer the URL updates to the OAuth phase in that case.
    if [[ "${DEPLOY_OAUTH:-false}" == "true" ]]; then
        print_status "OAuth is enabled - skipping standard URL updates (will be handled by OAuth deployment)" "secrets"
        return 0
    fi
    
    if [[ "${DEPLOY_FRONTEND:-true}" == "true" && -z "$frontend_url" ]] || [[ -z "$backend_url" ]]; then
        if [[ "${DEPLOY_FRONTEND:-true}" == "false" && -n "$backend_url" ]]; then
             # Frontend not deployed and we have backend url, that's fine
             :
        else
            print_error "Could not get URLs (Backend: $backend_url, Frontend: $frontend_url). Make sure the routes are created." "secrets"
            return 1
        fi
    fi
    
    print_status "Updating $secret_name secret with URLs..." "secrets"
    
    # Set BACKEND_CORS_ORIGINS if not already set, or append backend URL if it exists
    if [[ "${DEPLOY_FRONTEND:-true}" == "true" ]]; then
        if [[ -z "${BACKEND_CORS_ORIGINS:-}" ]]; then
            export BACKEND_CORS_ORIGINS="https://$frontend_url"
        else
            # Add backend URL to existing BACKEND_CORS_ORIGINS if not already present
            if [[ ! "$BACKEND_CORS_ORIGINS" =~ "https://$frontend_url" ]]; then
                export BACKEND_CORS_ORIGINS="$BACKEND_CORS_ORIGINS,https://$frontend_url"
                print_status "Added frontend URL to existing BACKEND_CORS_ORIGINS" "secrets"
            fi
        fi
        add_deployment_output "frontend_url" "$frontend_url"
    else
        print_status "Backend-only deployment: skipping frontend URL in BACKEND_CORS_ORIGINS" "secrets"
    fi
    
    # Set DOMAIN for backend
    export DOMAIN="$backend_url"
    
    # Store URLs in output collector
    add_deployment_output "backend_url" "$backend_url"
    add_deployment_output "backend_cors_origins" "$BACKEND_CORS_ORIGINS"
    add_deployment_output "domain" "$DOMAIN"
    
    # Delete the existing secret
    oc delete secret "$secret_name"
    
    # Recreate the secret with all values including URLs
    print_status "Recreating application environment secret with URLs..." "secrets"
    local secret_cmd="oc create secret generic $secret_name"
    secret_cmd+=$(build_secret_literals)
    
    # Execute the command
    eval "$secret_cmd"
    
    print_success "Updated environment secret with backend URL: https://$backend_url" "secrets"
    if [[ -n "$frontend_url" ]]; then
        print_success "  and frontend URL: https://$frontend_url" "secrets"
    fi
    return 0
}

# Made with Bob
