#!/usr/bin/env bash
#
# Application Deployment Library
#
# This library provides:
# - Frontend deployment
# - Backend deployment
# - Build configuration
# - Application grouping
#
#############################################
# Application Deployment Functions
#############################################

# Function to configure buildconfig webhook branch filter
configure_buildconfig_branch_filter() {
    local buildconfig_name=$1
    local branch_filter="${DEPLOYMENT_BRANCH_FILTER:-}"
    
    if [[ -n "$branch_filter" ]]; then
        print_status "Configuring $buildconfig_name to build only from branch: $branch_filter" "deployment"
        
        # Update the Git source ref to specify the branch
        if oc patch bc/$buildconfig_name --type=json -p "[
            {
                \"op\": \"add\",
                \"path\": \"/spec/source/git/ref\",
                \"value\": \"$branch_filter\"
            }
        ]" 2>&1; then
            print_success "Branch filter configured for $buildconfig_name (ref: $branch_filter)" "deployment"
        else
            print_warning "Failed to configure branch filter for $buildconfig_name" "deployment"
        fi
        
        # Add branch filter to webhook triggers using allowEnv
        # This ensures webhooks only trigger builds for the specified branch
        local trigger_count
        trigger_count=$(oc get bc/$buildconfig_name -o json | jq '.spec.triggers | length')
        
        for ((i=1; i<trigger_count; i++)); do
            local trigger_type
            trigger_type=$(oc get bc/$buildconfig_name -o json | jq -r ".spec.triggers[$i].type")
            
            if [[ "$trigger_type" == "GitHub" ]] || [[ "$trigger_type" == "Generic" ]]; then
                local trigger_key=$(echo "$trigger_type" | tr '[:upper:]' '[:lower:]')
                
                # Add allowEnv and env filter for the trigger
                oc patch bc/$buildconfig_name --type=json -p "[
                    {
                        \"op\": \"add\",
                        \"path\": \"/spec/triggers/$i/$trigger_key/allowEnv\",
                        \"value\": true
                    },
                    {
                        \"op\": \"add\",
                        \"path\": \"/spec/triggers/$i/$trigger_key/env\",
                        \"value\": [{\"name\": \"GIT_REF\", \"value\": \"refs/heads/$branch_filter\"}]
                    }
                ]" 2>/dev/null || print_warning "Could not add env filter to $trigger_type trigger at index $i" "deployment"
            fi
        done
    fi
}

# Function to deploy frontend
deploy_frontend() {
    print_status "Deploying frontend..." "deployment"
    
    # Check if frontend app already exists
    if resource_exists "buildconfig" "frontend"; then
        print_status "Frontend buildconfig already exists, triggering rollout restart..." "deployment"
        # Just restart the deployment to pick up new environment variables
        # Don't rebuild unless explicitly requested
        if resource_exists "deployment" "frontend"; then
            oc rollout restart deployment/frontend
            oc rollout status deployment/frontend --timeout=300s
        else
            print_warning "Frontend deployment not found, skipping restart" "deployment"
        fi
    else
        print_status "Creating new frontend application..." "deployment"
        oc new-app --name=frontend --strategy=docker --context-dir=frontend --source-secret=git-secret "$GIT_SSH_URL"
    fi
    
    # Configure branch filter if specified
    configure_buildconfig_branch_filter "frontend"
    
    # Check if route exists
    if ! resource_exists "route" "frontend"; then
        if ! is_oauth_enabled; then
            print_status "Exposing frontend service (OAuth disabled)..." "deployment"
            oc create route edge frontend --service=frontend --port=8080
        else
            print_status "Skipping frontend route creation (OAuth enabled)" "deployment"
        fi
    else
        if is_oauth_enabled; then
            print_warning "Frontend route exists but OAuth is enabled. Deleting public route..." "deployment"
            oc delete route frontend
        else
            print_status "Frontend route already exists, skipping creation" "deployment"
        fi
    fi
    
    return 0
}

# Function to deploy backend
deploy_backend() {
    print_status "Deploying backend..." "deployment"
    
    # Check if backend app already exists
    if resource_exists "buildconfig" "backend"; then
        print_status "Backend buildconfig already exists, triggering rollout restart..." "deployment"
        # Just restart the deployment to pick up new environment variables
        # Don't rebuild unless explicitly requested
        if resource_exists "deployment" "backend"; then
            oc rollout restart deployment/backend
            oc rollout status deployment/backend --timeout=300s
        else
            print_warning "Backend deployment not found, skipping restart" "deployment"
        fi
    else
        print_status "Creating new backend application..." "deployment"
        oc new-app --name=backend --strategy=docker --context-dir=backend --source-secret=git-secret "$GIT_SSH_URL"
    fi
    
    # Configure branch filter if specified
    configure_buildconfig_branch_filter "backend"
    
    # Check if route exists
    if ! resource_exists "route" "backend"; then
        if ! is_oauth_enabled; then
            print_status "Exposing backend service (OAuth disabled)..." "deployment"
            oc create route edge backend --service=backend --port=8000
        else
            print_status "Skipping backend route creation (OAuth enabled)" "deployment"
        fi
    else
        if is_oauth_enabled; then
            print_warning "Backend route exists but OAuth is enabled. Deleting public route..." "deployment"
            oc delete route backend
        else
            print_status "Backend route already exists, skipping creation" "deployment"
        fi
    fi
    
    return 0
}

# Function to configure frontend build with environment variables
configure_frontend() {
    # Build VITE_ build arguments JSON array
    # Note: Vite embeds these at BUILD time, so they must be build args, not runtime env vars
    local vite_buildargs_json="["
    local first=true
    local has_args=false
    
    # Add all VITE_ prefixed variables from .env.production file
    if [[ -f "$ENV_FILE" ]]; then
        while IFS= read -r line || [[ -n "$line" ]]; do
            # Skip comments and empty lines
            [[ "$line" =~ ^#.*$ || -z "$line" ]] && continue
            
            # Extract variable name and value
            if [[ "$line" =~ ^(VITE_[A-Za-z0-9_]+)=(.*)$ ]]; then
                local var_name="${BASH_REMATCH[1]}"
                local var_value="${BASH_REMATCH[2]}"
                
                # Remove quotes if present
                var_value="${var_value#\"}"
                var_value="${var_value%\"}"
                var_value="${var_value#\'}"
                var_value="${var_value%\'}"
                
                # Do not automatically set VITE_API_URL
                # nginx.conf handles the /api proxy, so relative paths work by default
                
                if [[ "$first" == "false" ]]; then
                    vite_buildargs_json+=","
                fi
                vite_buildargs_json+="{\"name\":\"$var_name\",\"value\":\"$var_value\"}"
                first=false
                has_args=true
                print_status "Found $var_name in .env.production" "deployment"
            fi
        done < "$ENV_FILE"
    fi
    
    vite_buildargs_json+="]"
    
    # Only patch and rebuild if we actually have VITE arguments
    if [[ "$has_args" == "true" ]]; then
        # Configure frontend build with all VITE_ variables as BUILD ARGS
        print_status "Configuring frontend build with VITE_ build arguments..." "deployment"
        oc patch bc/frontend --type=merge -p "{\"spec\":{\"strategy\":{\"dockerStrategy\":{\"buildArgs\":$vite_buildargs_json}}}}"
        
        print_status "Restarting frontend build to apply build args..." "deployment"
        oc cancel-build bc/frontend --state=new --state=pending --state=running 2>/dev/null || true
        oc start-build bc/frontend
    else
        print_status "No VITE_ variables found in .env.production. Skipping frontend rebuild." "deployment"
    fi
    
    return 0
}

# Function to configure backend environment
configure_backend() {
    local secret_name="$APP_NAME-env"
    
    print_status "Applying backend environment from $secret_name secret..." "deployment"
    oc patch deployment backend --patch "{\"spec\":{\"template\":{\"spec\":{\"containers\":[{\"name\":\"backend\",\"envFrom\":[{\"secretRef\":{\"name\":\"$secret_name\"}}]}]}}}}"
    
    return 0
}

# Function to group resources as one application
group_resources() {
    print_status "Grouping resources as one application..." "deployment"
    
    # Label core deployments
    local resources_to_label=("deployment/backend")
    
    if resource_exists "deployment" "postgresql"; then
        resources_to_label+=("deployment/postgresql")
    fi
    
    if resource_exists "deployment" "frontend"; then
        resources_to_label+=("deployment/frontend")
    fi
    
    oc label "${resources_to_label[@]}" app.kubernetes.io/part-of="$APP_NAME" --overwrite
    
    # Label MongoDB if it exists
    local mongo_deployment="${MONGO_DEPLOYMENT_NAME:-mongodb}"
    if resource_exists "deployment" "$mongo_deployment"; then
        oc label deployment/$mongo_deployment app.kubernetes.io/part-of="$APP_NAME" --overwrite
        print_status "MongoDB included in application group" "deployment"
    fi
    
    # Label OAuth proxy if it exists
    if resource_exists "deployment" "oauth-proxy"; then
        oc label deployment/oauth-proxy app.kubernetes.io/part-of="$APP_NAME" --overwrite
        print_status "OAuth2 Proxy included in application group" "deployment"
    fi
    
    # Label MCP server if it exists
    if resource_exists "deployment" "mcp"; then
        oc label deployment/mcp app.kubernetes.io/part-of="$APP_NAME" --overwrite
        print_status "MCP Server included in application group" "deployment"
    fi
    
    # Label Vault if it exists
    if resource_exists "deployment" "vault"; then
        oc label deployment/vault app.kubernetes.io/part-of="$APP_NAME" --overwrite
        print_status "Vault included in application group" "deployment"
    fi
    
    return 0
}

# Function to deploy Vault
deploy_vault() {
    print_status "Deploying Vault in production mode..." "deployment"
    
    # Check if Vault deployment already exists
    if resource_exists "deployment" "vault"; then
        print_status "Vault deployment already exists, triggering rollout restart..." "deployment"
        oc rollout restart deployment/vault
        oc rollout status deployment/vault --timeout=300s
    else
        print_status "Creating new Vault deployment..." "deployment"
        
        # Create PersistentVolumeClaim for Vault data FIRST
        if ! resource_exists "pvc" "vault-data"; then
            print_status "Creating PersistentVolumeClaim for Vault data..." "deployment"
            cat <<EOF | oc apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: vault-data
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
EOF
        fi
        
        # Create ConfigMap for Vault configuration FIRST
        if ! resource_exists "configmap" "vault-config"; then
            print_status "Creating Vault configuration..." "deployment"
            cat <<EOF | oc apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: vault-config
data:
  vault.hcl: |
    storage "file" {
      path = "/vault/data"
    }
    
    listener "tcp" {
      address = "0.0.0.0:8200"
      tls_disable = 1
    }
    
    ui = true
    
    # Disable mlock for OpenShift compatibility
    disable_mlock = true
EOF
        fi
        
        # Create the complete Vault deployment with all configurations
        print_status "Creating Vault deployment with production configuration..." "deployment"
        cat <<EOF | oc apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vault
  labels:
    app: vault
spec:
  replicas: 1
  selector:
    matchLabels:
      app: vault
  template:
    metadata:
      labels:
        app: vault
    spec:
      containers:
      - name: vault
        image: registry.connect.redhat.com/hashicorp/vault:1.15
        command: ["vault", "server", "-config=/vault/config/vault.hcl"]
        env:
        - name: SKIP_CHOWN
          value: "true"
        - name: SKIP_SETCAP
          value: "true"
        - name: VAULT_DISABLE_MLOCK
          value: "true"
        - name: VAULT_ADDR
          value: "http://127.0.0.1:8200"
        ports:
        - containerPort: 8200
          name: http
          protocol: TCP
        - containerPort: 8201
          name: https-internal
          protocol: TCP
        volumeMounts:
        - name: vault-config
          mountPath: /vault/config
        - name: vault-data
          mountPath: /vault/data
        readinessProbe:
          httpGet:
            path: /v1/sys/health?standbyok=true&sealedcode=204&uninitcode=204
            port: 8200
            scheme: HTTP
          initialDelaySeconds: 10
          periodSeconds: 10
        livenessProbe:
          httpGet:
            path: /v1/sys/health?standbyok=true
            port: 8200
            scheme: HTTP
          initialDelaySeconds: 60
          periodSeconds: 10
      volumes:
      - name: vault-config
        configMap:
          name: vault-config
      - name: vault-data
        persistentVolumeClaim:
          claimName: vault-data
EOF
        
        # Create service if it doesn't exist
        if ! resource_exists "service" "vault"; then
            print_status "Creating Vault service..." "deployment"
            cat <<EOF | oc apply -f -
apiVersion: v1
kind: Service
metadata:
  name: vault
  labels:
    app: vault
spec:
  ports:
  - name: http
    port: 8200
    targetPort: 8200
    protocol: TCP
  - name: https-internal
    port: 8201
    targetPort: 8201
    protocol: TCP
  selector:
    app: vault
EOF
        fi
        
        # Wait for deployment to be ready
        print_status "Waiting for Vault to be ready..." "deployment"
        oc rollout status deployment/vault --timeout=300s
        
        # Print initialization instructions
        print_warning "==================================================================" "deployment"
        print_warning "VAULT INITIALIZATION REQUIRED" "deployment"
        print_warning "==================================================================" "deployment"
        print_warning "Vault is running in production mode and needs to be initialized." "deployment"
        print_warning "" "deployment"
        print_warning "To initialize Vault, run the following commands:" "deployment"
        print_warning "" "deployment"
        print_warning "1. Get a shell in the Vault pod:" "deployment"
        print_warning "   oc rsh deployment/vault" "deployment"
        print_warning "" "deployment"
        print_warning "2. Initialize Vault (save the unseal keys and root token!):" "deployment"
        print_warning "   vault operator init" "deployment"
        print_warning "" "deployment"
        print_warning "3. Unseal Vault (use 3 of the 5 unseal keys):" "deployment"
        print_warning "   vault operator unseal <key1>" "deployment"
        print_warning "   vault operator unseal <key2>" "deployment"
        print_warning "   vault operator unseal <key3>" "deployment"
        print_warning "" "deployment"
        print_warning "4. Login with the root token:" "deployment"
        print_warning "   vault login <root-token>" "deployment"
        print_warning "" "deployment"
        print_warning "IMPORTANT: Store the unseal keys and root token securely!" "deployment"
        print_warning "==================================================================" "deployment"
    fi
    
    # Check if route exists
    if ! resource_exists "route" "vault"; then
        print_status "Exposing Vault service..." "deployment"
        oc create route edge vault --service=vault --port=8200
    else
        print_status "Vault route already exists, skipping creation" "deployment"
    fi
    
    return 0
}

# Function to deploy MCP server
deploy_mcp() {
    print_status "Deploying MCP server..." "deployment"
    
    # Check if MCP app already exists
    if resource_exists "buildconfig" "mcp"; then
        print_status "MCP buildconfig already exists, triggering rollout restart..." "deployment"
        if resource_exists "deployment" "mcp"; then
            oc rollout restart deployment/mcp
            oc rollout status deployment/mcp --timeout=300s
        else
            print_warning "MCP deployment not found, skipping restart" "deployment"
        fi
    else
        print_status "Creating new MCP application..." "deployment"
        oc new-app --name=mcp --strategy=docker --context-dir=mcp --source-secret=git-secret "$GIT_SSH_URL"
    fi
    
    # Configure branch filter if specified
    configure_buildconfig_branch_filter "mcp"
    
    # Check if route exists
    if ! resource_exists "route" "mcp"; then
        print_status "Exposing MCP service..." "deployment"
        oc create route edge mcp --service=mcp --port=8080
    else
        print_status "MCP route already exists, skipping creation" "deployment"
    fi
    
    return 0
}

# Function to configure MCP environment
configure_mcp() {
    local secret_name="$APP_NAME-env"
    
    print_status "Applying MCP environment from $secret_name secret..." "deployment"
    oc patch deployment mcp --patch "{\"spec\":{\"template\":{\"spec\":{\"containers\":[{\"name\":\"mcp\",\"envFrom\":[{\"secretRef\":{\"name\":\"$secret_name\"}}]}]}}}}"
    
    # Get Vault URL and add it to MCP environment
    if resource_exists "route" "vault"; then
        local vault_url="https://$(oc get route vault -o jsonpath='{.spec.host}')"
        print_status "Setting VAULT_ADDR=$vault_url for MCP" "deployment"
        oc set env deployment/mcp VAULT_ADDR="$vault_url"
    fi
    
    return 0
}

# Made with Bob
