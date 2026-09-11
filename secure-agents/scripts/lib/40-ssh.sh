#!/usr/bin/env bash
#
# SSH Key Management Library
#
# This library provides:
# - GitHub deploy key verification
# - GitHub deploy key creation
# - SSH key deletion
# - SSH key setup and configuration
#
#############################################
# SSH Key Management Functions
#############################################

# Function to check if deploy key exists on GitHub
check_github_deploy_key() {
    local repo_url=$1
    local public_key=$2
    local github_host="${GITHUB_HOST:-$DEFAULT_GITHUB_HOST}"
    
    # Extract owner and repo from SSH URL
    # Format: git@github.com:owner/repo.git or git@github.ibm.com:owner/repo.git
    if [[ $repo_url =~ git@[^:]+:([^/]+)/(.+)\.git ]]; then
        local owner="${BASH_REMATCH[1]}"
        local repo="${BASH_REMATCH[2]}"
        
        # Check if GITHUB_TOKEN is available
        if [[ -z "${GITHUB_TOKEN:-}" ]]; then
            print_warning "GITHUB_TOKEN not set. Cannot verify deploy key automatically." "ssh"
            return 1
        fi
        
        # Determine API URL based on GitHub host
        local api_url
        if [[ "$github_host" == "github.com" ]]; then
            api_url="https://api.github.com/repos/$owner/$repo/keys"
        else
            # GitHub Enterprise Server format
            api_url="https://$github_host/api/v3/repos/$owner/$repo/keys"
        fi
        
        # Query GitHub API for deploy keys
        local response
        local http_code
        response=$(curl -s -w "\n%{http_code}" -H "Authorization: token $GITHUB_TOKEN" \
            "$api_url")
        
        http_code=$(echo "$response" | tail -n1)
        response=$(echo "$response" | sed '$d')
        
        # Check for API errors
        if [[ "$http_code" != "200" ]]; then
            print_warning "Failed to check deploy keys (HTTP $http_code). API response:" "ssh"
            echo "$response" | head -n 5
            return 1
        fi
        
        # Check if the public key exists
        if echo "$response" | grep -q "$(echo "$public_key" | awk '{print $2}')"; then
            return 0
        fi
    fi
    
    return 1
}

# Function to add deploy key to GitHub
add_github_deploy_key() {
    local repo_url=$1
    local public_key=$2
    local key_title="OpenShift Deploy Key - $(date +%Y%m%d)"
    local github_host="${GITHUB_HOST:-$DEFAULT_GITHUB_HOST}"
    
    # Extract owner and repo from SSH URL
    if [[ $repo_url =~ git@[^:]+:([^/]+)/(.+)\.git ]]; then
        local owner="${BASH_REMATCH[1]}"
        local repo="${BASH_REMATCH[2]}"
        
        # Check if GITHUB_TOKEN is available
        if [[ -z "${GITHUB_TOKEN:-}" ]]; then
            print_warning "GITHUB_TOKEN not set. Cannot add deploy key automatically." "ssh"
            return 1
        fi
        
        print_status "Adding deploy key to GitHub repository ($github_host)..." "ssh"
        
        # Determine API URL based on GitHub host
        local api_url
        if [[ "$github_host" == "github.com" ]]; then
            api_url="https://api.github.com/repos/$owner/$repo/keys"
        else
            # GitHub Enterprise Server format
            api_url="https://$github_host/api/v3/repos/$owner/$repo/keys"
        fi
        
        # Add deploy key via GitHub API
        local response
        local http_code
        response=$(curl -s -w "\n%{http_code}" -X POST \
            -H "Authorization: Bearer $GITHUB_TOKEN" \
            -H "Accept: application/vnd.github+json" \
            -H "X-GitHub-Api-Version: 2022-11-28" \
            "$api_url" \
            -d "{\"title\":\"$key_title\",\"key\":\"$public_key\",\"read_only\":false}")
        
        http_code=$(echo "$response" | tail -n1)
        response=$(echo "$response" | sed '$d')
        
        if [[ "$http_code" == "201" ]] && echo "$response" | grep -q '"id"'; then
            print_success "Deploy key added to GitHub successfully!" "ssh"
            return 0
        else
            print_error "Failed to add deploy key to GitHub (HTTP $http_code)" "ssh"
            print_error "API Response:" "ssh"
            echo "$response" | jq '.' 2>/dev/null || echo "$response"
            
            # Provide helpful error messages
            if echo "$response" | grep -q "key is already in use"; then
                print_warning "This SSH key is already registered. You may need to use --regenerate-ssh-key" "ssh"
            elif [[ "$http_code" == "401" ]]; then
                print_error "Authentication failed. Check your GITHUB_TOKEN permissions." "ssh"
            elif [[ "$http_code" == "404" ]]; then
                print_error "Repository not found. Check GIT_SSH_URL and token permissions." "ssh"
            fi
            return 1
        fi
    fi

    print_error "Invalid GIT_SSH_URL format. Expected: git@$github_host:owner/repo.git" "ssh"
    
    return 1
}

# Function to delete SSH keys
delete_ssh_keys() {
    local key_path="$HOME/.ssh/$PROJECT_NAME/ocp-key"
    local pub_key_path="$HOME/.ssh/$PROJECT_NAME/ocp-key.pub"
    local github_host="${GITHUB_HOST:-$DEFAULT_GITHUB_HOST}"
    
    print_status "Deleting SSH keys..." "ssh"
    
    # Delete local keys
    if [[ -f "$key_path" ]]; then
        rm -f "$key_path"
        print_status "Deleted local private key" "ssh"
    fi
    
    if [[ -f "$pub_key_path" ]]; then
        local public_key
        public_key=$(cat "$pub_key_path")
        rm -f "$pub_key_path"
        print_status "Deleted local public key" "ssh"
        
        # Delete from GitHub if GITHUB_TOKEN is available
        if [[ -n "${GITHUB_TOKEN:-}" && $GIT_SSH_URL =~ git@[^:]+:([^/]+)/(.+)\.git ]]; then
            local owner="${BASH_REMATCH[1]}"
            local repo="${BASH_REMATCH[2]}"
            
            # Determine API URL based on GitHub host
            local api_url
            if [[ "$github_host" == "github.com" ]]; then
                api_url="https://api.github.com/repos/$owner/$repo/keys"
            else
                # GitHub Enterprise Server format
                api_url="https://$github_host/api/v3/repos/$owner/$repo/keys"
            fi
            
            # Get all deploy keys
            local keys_response
            local http_code
            keys_response=$(curl -s -w "\n%{http_code}" -H "Authorization: token $GITHUB_TOKEN" \
                "$api_url")
            
            http_code=$(echo "$keys_response" | tail -n1)
            keys_response=$(echo "$keys_response" | sed '$d')
            
            if [[ "$http_code" != "200" ]]; then
                print_warning "Failed to retrieve deploy keys from GitHub (HTTP $http_code)" "ssh"
            else
                # Find and delete matching key
                local key_id
                key_id=$(echo "$keys_response" | jq -r ".[] | select(.key | contains(\"$(echo "$public_key" | awk '{print $2}')\")) | .id" 2>/dev/null)
                
                if [[ -n "$key_id" ]]; then
                    # Determine delete API URL
                    local delete_url
                    if [[ "$github_host" == "github.com" ]]; then
                        delete_url="https://api.github.com/repos/$owner/$repo/keys/$key_id"
                    else
                        delete_url="https://$github_host/api/v3/repos/$owner/$repo/keys/$key_id"
                    fi
                    
                    local delete_response
                    delete_response=$(curl -s -w "\n%{http_code}" -X DELETE \
                        -H "Authorization: token $GITHUB_TOKEN" \
                        "$delete_url")
                    
                    local delete_code=$(echo "$delete_response" | tail -n1)
                    if [[ "$delete_code" == "204" ]]; then
                        print_status "Deleted deploy key from GitHub" "ssh"
                    else
                        print_warning "Failed to delete deploy key from GitHub (HTTP $delete_code)" "ssh"
                    fi
                else
                    print_status "Deploy key not found on GitHub (may have been already deleted)" "ssh"
                fi
            fi
        fi
    fi
    
    # Delete from OpenShift
    if resource_exists "secret" "git-secret"; then
        oc delete secret git-secret
        print_status "Deleted git-secret from OpenShift" "ssh"
    fi
    
    print_success "SSH keys deleted successfully" "ssh"
    return 0
}

# Function to create SSH keys for Git access
setup_ssh_keys() {
    mkdir -p "$HOME/.ssh/$PROJECT_NAME"
    local key_path="$HOME/.ssh/$PROJECT_NAME/ocp-key"
    local pub_key_path="$HOME/.ssh/$PROJECT_NAME/ocp-key.pub"
    local need_user_input=false
    
    # Check if keys exist and are valid
    if [[ -f "$key_path" && -f "$pub_key_path" ]]; then
        print_status "SSH key pair already exists in ~/.ssh/$PROJECT_NAME/" "ssh"
        
        # Check if deploy key exists on GitHub
        local public_key
        public_key=$(cat "$pub_key_path")
        
        if check_github_deploy_key "$GIT_SSH_URL" "$public_key"; then
            print_success "Deploy key is already configured on GitHub" "ssh"
        else
            print_warning "Deploy key not found on GitHub" "ssh"
            need_user_input=true
        fi
    else
        # Generate new keys
        print_status "Generating new SSH key pair..." "ssh"
        ssh-keygen -N '' -f "$key_path" -C "openshift-deploy-key" -q <<< y > /dev/null
        print_success "SSH key pair generated" "ssh"
        need_user_input=true
    fi
    
    # Display the public key
    local public_key
    public_key=$(cat "$pub_key_path")
    print_status "Public SSH key for repository access:" "ssh"
    echo -e "${TEAL}$public_key${NC}"
    
    # Try to add deploy key automatically
    if [[ "$need_user_input" == "true" ]]; then
        if add_github_deploy_key "$GIT_SSH_URL" "$public_key"; then
            print_success "Deploy key configured automatically" "ssh"
        else
            print_warning "Could not add deploy key automatically" "ssh"
            print_status "${GREEN}Please add this public key to your GitHub repository as a deploy key${NC}" "ssh"
            read -p "Press enter once you've added the deploy key..."
        fi
    fi
    
    # Create or update OpenShift secret
    if resource_exists "secret" "git-secret"; then
        print_status "Updating git-secret..." "ssh"
        oc delete secret git-secret
    fi
    
    print_status "Creating OpenShift secret..." "ssh"
    oc create secret generic git-secret \
        --from-file=ssh-privatekey="$key_path" \
        --type=kubernetes.io/ssh-auth
    
    return 0
}

# Made with Bob
