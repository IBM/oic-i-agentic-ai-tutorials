#!/usr/bin/env bash
#
# Webhook Management Library
#
# This library provides:
# - GitHub webhook creation
# - Webhook setup and configuration
# - RoleBinding for webhook access
#
#############################################
# Webhook Management Functions
#############################################

# Function to create GitHub webhook
create_github_webhook() {
    local repo_url=$1
    local webhook_url=$2
    local webhook_type=$3  # "frontend" or "backend"
    local github_host="${GITHUB_HOST:-$DEFAULT_GITHUB_HOST}"
    
    # Extract owner and repo from SSH URL
    if [[ $repo_url =~ git@[^:]+:([^/]+)/(.+)\.git ]]; then
        local owner="${BASH_REMATCH[1]}"
        local repo="${BASH_REMATCH[2]}"
        
        # Check if GITHUB_TOKEN is available
        if [[ -z "${GITHUB_TOKEN:-}" ]]; then
            print_warning "GITHUB_TOKEN not set. Cannot create webhook automatically." "webhooks"
            return 1
        fi
        
        print_status "Creating GitHub webhook for $webhook_type on $github_host..." "webhooks"
        
        # Check if webhook already exists
        local existing_webhooks
        local http_code
        existing_webhooks=$(curl -s -w "\n%{http_code}" -H "Authorization: token $GITHUB_TOKEN" \
            "https://api.$github_host/repos/$owner/$repo/hooks")
        
        http_code=$(echo "$existing_webhooks" | tail -n1)
        existing_webhooks=$(echo "$existing_webhooks" | sed '$d')
        
        if [[ "$http_code" != "200" ]]; then
            print_error "Failed to check existing webhooks (HTTP $http_code)" "webhooks"
            print_error "API Response:" "webhooks"
            echo "$existing_webhooks" | jq '.' 2>/dev/null || echo "$existing_webhooks"
            
            if [[ "$http_code" == "401" ]]; then
                print_error "Authentication failed. Check your GITHUB_TOKEN." "webhooks"
            elif [[ "$http_code" == "404" ]]; then
                print_error "Repository not found. Check GIT_SSH_URL and token permissions." "webhooks"
            fi
            return 1
        fi
        
        if echo "$existing_webhooks" | grep -q "$webhook_url"; then
            print_status "Webhook for $webhook_type already exists" "webhooks"
            return 0
        fi
        
        # Create webhook
        local response
        local json_payload

        json_payload="{\"name\":\"web\",\"active\":true,\"events\":[\"push\"],\"config\":{\"url\":\"$webhook_url\",\"content_type\":\"json\",\"insecure_ssl\":\"0\"}}"

        response=$(curl -s -w "\n%{http_code}" \
            -X POST \
            -H "Authorization: Bearer $GITHUB_TOKEN" \
            -H "Accept: application/vnd.github+json" \
            -H "X-GitHub-Api-Version: 2022-11-28" \
            "https://api.$github_host/repos/$owner/$repo/hooks" \
            -d $json_payload
        )

        http_code=$(echo "$response" | tail -n1)
        response=$(echo "$response" | sed '$d')
        
        if [[ "$http_code" == "201" ]] && echo "$response" | grep -q '"id"'; then
            print_success "GitHub webhook for $webhook_type created successfully!" "webhooks"
            return 0
        else
            print_error "Failed to create GitHub webhook for $webhook_type (HTTP $http_code)" "webhooks"
            print_error "API Response:" "webhooks"
            echo "$response" | jq '.' 2>/dev/null || echo "$response"
            
            # Provide helpful error messages
            if [[ "$http_code" == "422" ]]; then
                if echo "$response" | grep -q "Hook already exists"; then
                    print_warning "Webhook already exists but wasn't detected in the check." "webhooks"
                else
                    print_error "Validation failed. Check webhook URL format." "webhooks"
                fi
            elif [[ "$http_code" == "401" ]]; then
                print_error "Authentication failed. Check your GITHUB_TOKEN permissions." "webhooks"
            elif [[ "$http_code" == "404" ]]; then
                print_error "Repository not found. Check GIT_SSH_URL and token permissions." "webhooks"
            fi
            return 1
        fi
    fi
    
    print_error "Invalid GIT_SSH_URL format. Expected: git@$github_host:owner/repo.git" "webhooks"
    return 1
}

# Function to setup CI/CD webhooks
setup_webhooks() {
    print_status "Setting up webhooks..." "webhooks"
    
    # Create RoleBinding for webhook access if it doesn't exist
    if ! resource_exists "rolebinding" "webhook-access-unauthenticated"; then
        print_status "Creating RoleBinding for webhook access..." "webhooks"
        apply_resource "$(cat << EOF
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  annotations:
    rbac.authorization.kubernetes.io/autoupdate: "true"
  name: webhook-access-unauthenticated
  namespace: $PROJECT_NAME
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: "system:webhook"
subjects:
  - apiGroup: rbac.authorization.k8s.io
    kind: Group
    name: "system:unauthenticated"
EOF
)"
    else
        print_status "RoleBinding webhook-access-unauthenticated already exists, skipping creation" "webhooks"
    fi
    
    # Get webhook URLs
    print_status "Getting webhook URLs..." "webhooks"
    local frontend_base_url
    local frontend_secret
    local frontend_webhook=""
    local backend_base_url
    local backend_secret
    local backend_webhook
    
    if [[ "${DEPLOY_FRONTEND:-true}" == "true" ]]; then
        frontend_base_url=$(oc describe bc/frontend | grep "Webhook Generic" -A 1 | tail -n 1 | sed 's/.*\(https:\/\/[^ ]*\).*/\1/')
        frontend_secret=$(oc get bc frontend -o jsonpath='{.spec.triggers[*].generic.secret}')
        frontend_webhook=${frontend_base_url/<secret>/$frontend_secret}
        
        # Store webhook URLs in output collector
        add_deployment_output "frontend_webhook" "$frontend_webhook"
    else
        print_status "Skipping frontend webhook retrieval (backend-only mode)" "webhooks"
    fi
    
    backend_base_url=$(oc describe bc/backend | grep "Webhook Generic" -A 1 | tail -n 1 | sed 's/.*\(https:\/\/[^ ]*\).*/\1/')
    backend_secret=$(oc get bc backend -o jsonpath='{.spec.triggers[*].generic.secret}')
    backend_webhook=${backend_base_url/<secret>/$backend_secret}
    
    # Store webhook URLs in output collector
    add_deployment_output "backend_webhook" "$backend_webhook"
    
    # Try to create GitHub webhooks automatically
    if [[ -n "${GITHUB_TOKEN:-}" ]]; then
        print_status "Attempting to create GitHub webhooks automatically..." "webhooks"
        local frontend_webhook_created=false
        local backend_webhook_created=false
        
        if [[ "${DEPLOY_FRONTEND:-true}" == "true" ]]; then
            if create_github_webhook "$GIT_SSH_URL" "$frontend_webhook" "frontend"; then
                frontend_webhook_created=true
            fi
        else
            # In backend-only mode, we consider frontend "created" for the success check logic, 
            # or we just skip it. Let's skip calling the create function.
            frontend_webhook_created=true # mock true to satisfy the ALL check if we used the old logic, but better to adjust logic
        fi
        
        if create_github_webhook "$GIT_SSH_URL" "$backend_webhook" "backend"; then
            backend_webhook_created=true
        fi
        
        # Mark as configured if both webhooks were created (or just backend if backend-only)
        if [[ "$frontend_webhook_created" == "true" && "$backend_webhook_created" == "true" ]]; then
            add_deployment_output "github_webhooks_configured" "true"
        fi
    else
        print_warning "GITHUB_TOKEN not set. Webhooks must be added manually to GitHub." "webhooks"
        add_deployment_output "github_webhooks_configured" "false"
    fi
    
    return 0
}

# Made with Bob
