#!/usr/bin/env bash
#
# OAuth2 Proxy Deployment Library
#
# This library provides:
# - OAuth2 Proxy deployment (optional feature)
# - OAuth configuration validation
# - OAuth secret management
# - OAuth service and route creation
#

#############################################
# OAuth Detection Functions
#############################################

# Function to check if OAuth is enabled (for backward compatibility)
is_oauth_enabled() {
    # Check the DEPLOY_OAUTH flag set by flavor configuration
    if [[ "${DEPLOY_OAUTH:-false}" == "true" ]]; then
        return 0
    fi
    return 1
}

#############################################
# OAuth Secret Management
#############################################

# Function to create OAuth2 Proxy secret
create_oauth_proxy_secret() {
    local secret_name="$APP_NAME-oauth-proxy-secret"
    
    # NOTE: We cannot derive the redirect URL or cookie domain from the oauth-proxy route yet
    # because that route hasn't been created. The deployment flow is:
    # 1. Create Secret (needs URLs)
    # 2. Deploy Proxy (uses Secret)
    # 3. Create Service
    # 4. Create Route (generates the URL we needed in step 1)
    #
    # To solve this circular dependency, we'll create the route *first* (or check for it),
    # then update the secret with the correct values.
    
    # Check if route exists, if not create it immediately to get the host
    if ! resource_exists "route" "oauth-proxy"; then
        print_status "Pre-creating OAuth2 Proxy route to reserve hostname..." "oauth"
        create_oauth_proxy_service || return 1
        create_oauth_proxy_route || return 1
    fi

    # Now get the OAuth proxy URL
    local oauth_url
    oauth_url=$(oc get route oauth-proxy -o jsonpath='{.spec.host}' 2>/dev/null || echo "")
    
    if [[ -z "$oauth_url" ]]; then
        print_error "Could not get OAuth proxy URL. Make sure the route is created." "oauth"
        return 1
    fi

    # Derive values strictly from the OAuth proxy route
    local derived_redirect_url="https://$oauth_url/oauth2/callback"
    
    # Store in output collector for summary
    add_deployment_output "oauth_redirect_url" "$derived_redirect_url"
    
    # Derive cookie domain (strip protocol, path, port)
    local derived_cookie_domain="$oauth_url"
    derived_cookie_domain="${derived_cookie_domain#*://}"
    derived_cookie_domain="${derived_cookie_domain%%/*}"
    derived_cookie_domain="${derived_cookie_domain%:*}"

    print_status "Configuring OAuth2 Proxy with derived values from OAuth Route:" "oauth"
    echo "  - Redirect URL: $derived_redirect_url"
    echo "  - Cookie Domain: $derived_cookie_domain"
    
    print_status "Creating OAuth2 Proxy secret..." "oauth"
    
    # Check if secret exists
    if resource_exists "secret" "$secret_name"; then
        print_status "OAuth2 Proxy secret exists, updating..." "oauth"
        oc delete secret "$secret_name"
    fi
    
    # Create secret with OAuth variables
    # Note: redirect-url and cookiedomain are derived from oauth_url
    oc create secret generic "$secret_name" \
        --from-literal=cookiedomain="$derived_cookie_domain" \
        --from-literal=cookiesecret="$OAUTH2_PROXY_COOKIE_SECRET" \
        --from-literal=clientid="$OAUTH2_PROXY_CLIENT_ID" \
        --from-literal=clientsecret="$OAUTH2_PROXY_CLIENT_SECRET" \
        --from-literal=oidc-issuer-url="$OAUTH2_PROXY_OIDC_ISSUER_URL" \
        --from-literal=redirect-url="$derived_redirect_url"
    
    print_success "OAuth2 Proxy secret created: $secret_name" "oauth"
    
    # We need to restart the deployment if it already exists to pick up the secret changes
    if resource_exists "deployment" "oauth-proxy"; then
        print_status "Restarting OAuth2 Proxy to apply new secret configuration..." "oauth"
        oc rollout restart deployment/oauth-proxy
    fi
    
    return 0
}

#############################################
# OAuth Deployment Functions
#############################################

# Function to deploy OAuth2 Proxy
deploy_oauth_proxy() {
    print_status "Deploying OAuth2 Proxy..." "oauth"
    
    # Check if deployment already exists
    if resource_exists "deployment" "oauth-proxy"; then
        print_status "OAuth2 Proxy deployment already exists, triggering rollout restart..." "oauth"
        oc rollout restart deployment/oauth-proxy
        oc rollout status deployment/oauth-proxy --timeout=300s
        return 0
    fi
    
    print_status "Creating new OAuth2 Proxy deployment..." "oauth"
    
    # Create deployment
    cat << EOF | oc apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: oauth-proxy
  labels:
    app: oauth-proxy
    app.kubernetes.io/part-of: ${APP_NAME}
spec:
  replicas: 1
  selector:
    matchLabels:
      deployment: oauth-proxy
  template:
    metadata:
      labels:
        deployment: oauth-proxy
        app: oauth-proxy
    spec:
      containers:
        - name: oauth-proxy
          image: quay.io/oauth2-proxy/oauth2-proxy:latest
          env:
            - name: OAUTH2_PROXY_COOKIE_DOMAIN
              valueFrom:
                secretKeyRef:
                  name: ${APP_NAME}-oauth-proxy-secret
                  key: cookiedomain
            - name: OAUTH2_PROXY_COOKIE_SECRET
              valueFrom:
                secretKeyRef:
                  name: ${APP_NAME}-oauth-proxy-secret
                  key: cookiesecret
            - name: OAUTH2_PROXY_CLIENT_ID
              valueFrom:
                secretKeyRef:
                  name: ${APP_NAME}-oauth-proxy-secret
                  key: clientid
            - name: OAUTH2_PROXY_CLIENT_SECRET
              valueFrom:
                secretKeyRef:
                  name: ${APP_NAME}-oauth-proxy-secret
                  key: clientsecret
            - name: OAUTH2_PROXY_OIDC_ISSUER_URL
              valueFrom:
                secretKeyRef:
                  name: ${APP_NAME}-oauth-proxy-secret
                  key: oidc-issuer-url
            - name: OAUTH2_PROXY_REDIRECT_URL
              valueFrom:
                secretKeyRef:
                  name: ${APP_NAME}-oauth-proxy-secret
                  key: redirect-url
          ports:
            - containerPort: 4180
              protocol: TCP
          args:
            - "--provider=oidc"
            - "--pass-authorization-header"
            - "--insecure-oidc-allow-unverified-email"
            - "--upstream=http://backend:8000/api/"
            - "--upstream=http://frontend:8080/"
            - "--email-domain=*"
            - "--http-address=:4180"
            - "--skip-provider-button"
          readinessProbe:
            httpGet:
              path: /ping
              port: 4180
            initialDelaySeconds: 2
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /ping
              port: 4180
            initialDelaySeconds: 2
            periodSeconds: 30
EOF
    
    print_success "OAuth2 Proxy deployment created" "oauth"
    return 0
}

# Function to create OAuth2 Proxy service
create_oauth_proxy_service() {
    print_status "Creating OAuth2 Proxy service..." "oauth"
    
    # Check if service already exists
    if resource_exists "service" "oauth-proxy"; then
        print_status "OAuth2 Proxy service already exists, skipping creation" "oauth"
        return 0
    fi
    
    # Create service
    cat << EOF | oc apply -f -
apiVersion: v1
kind: Service
metadata:
  name: oauth-proxy
  labels:
    app: oauth-proxy
    app.kubernetes.io/part-of: ${APP_NAME}
spec:
  ports:
    - name: external
      port: 4180
      protocol: TCP
      targetPort: 4180
  selector:
    deployment: oauth-proxy
EOF
    
    print_success "OAuth2 Proxy service created" "oauth"
    return 0
}

# Function to create OAuth2 Proxy route
create_oauth_proxy_route() {
    print_status "Creating OAuth2 Proxy route..." "oauth"
    
    # Check if route already exists
    if resource_exists "route" "oauth-proxy"; then
        print_status "OAuth2 Proxy route already exists, skipping creation" "oauth"
    else
        oc create route edge oauth-proxy --service=oauth-proxy --port=4180
        print_success "OAuth2 Proxy route created" "oauth"
    fi
    
    # Get the OAuth proxy URL
    local oauth_url
    oauth_url=$(oc get route oauth-proxy -o jsonpath='{.spec.host}' 2>/dev/null || echo "")
    
    if [[ -n "$oauth_url" ]]; then
        # Store in output collector
        add_deployment_output "oauth_proxy_url" "$oauth_url"
        print_success "OAuth2 Proxy URL: https://$oauth_url" "oauth"
    else
        print_warning "Could not retrieve OAuth2 Proxy URL" "oauth"
    fi
    
    return 0
}

# Function to update backend environment with OAuth proxy URL
update_backend_with_oauth_url() {
    local oauth_url
    oauth_url=$(oc get route oauth-proxy -o jsonpath='{.spec.host}' 2>/dev/null || echo "")
    
    if [[ -z "$oauth_url" ]]; then
        print_error "Could not get OAuth proxy URL. Make sure the route is created." "oauth"
        return 1
    fi
    
    print_status "Updating backend environment with OAuth proxy URL..." "oauth"
    
    # Update FRONTEND_URL to point to OAuth proxy
    export FRONTEND_URL="https://$oauth_url"
    
    # Update BACKEND_CORS_ORIGINS to include OAuth proxy
    if [[ -z "${BACKEND_CORS_ORIGINS:-}" ]]; then
        export BACKEND_CORS_ORIGINS="https://$oauth_url"
    else
        # Add OAuth URL to existing BACKEND_CORS_ORIGINS if not already present
        if [[ ! "$BACKEND_CORS_ORIGINS" =~ "https://$oauth_url" ]]; then
            export BACKEND_CORS_ORIGINS="$BACKEND_CORS_ORIGINS,https://$oauth_url"
            print_status "Added OAuth proxy URL to BACKEND_CORS_ORIGINS" "oauth"
        fi
    fi
    
    # Derive well-known URL if not set (auto-discovery)
    local clean_issuer_url="${OAUTH2_PROXY_OIDC_ISSUER_URL%/}"
    local well_known_url="${OAUTH2_PROXY_WELL_KNOWN_URL:-${clean_issuer_url}/.well-known/openid-configuration}"

    # Export it so build_secret_literals picks it up if the key exists in .env
    export OAUTH2_PROXY_WELL_KNOWN_URL="$well_known_url"
    
    # Recreate the app environment secret with updated values
    local secret_name="$APP_NAME-env"
    print_status "Updating $secret_name secret with OAuth proxy URL..." "oauth"
    
    # Delete the existing secret
    oc delete secret "$secret_name"
    
    # Recreate the secret with all values including OAuth URL
    local secret_literals=$(build_secret_literals)
    local secret_cmd="oc create secret generic $secret_name"
    secret_cmd+="$secret_literals"

    # Add OAUTH2_PROXY_WELL_KNOWN_URL if it was not included by build_secret_literals
    # (build_secret_literals only includes keys that exist in the .env file)
    if [[ "$secret_literals" != *"OAUTH2_PROXY_WELL_KNOWN_URL="* ]]; then
         secret_cmd+=" --from-literal=OAUTH2_PROXY_WELL_KNOWN_URL=\"$well_known_url\""
         print_status "Added derived OAUTH2_PROXY_WELL_KNOWN_URL to backend environment" "oauth"
    fi
    
    # Execute the command
    eval "$secret_cmd"
    
    print_success "Backend environment updated with OAuth proxy URL: https://$oauth_url" "oauth"
    
    # Restart backend to pick up new environment
    if resource_exists "deployment" "backend"; then
        print_status "Restarting backend to apply OAuth configuration..." "oauth"
        oc rollout restart deployment/backend
        oc rollout status deployment/backend --timeout=300s
    fi
    
    return 0
}

# Made with Bob
