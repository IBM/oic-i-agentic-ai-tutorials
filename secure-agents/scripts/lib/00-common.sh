#!/usr/bin/env bash
#
# Common Utilities Library
#
# This library provides:
# - Color codes for output formatting
# - Print functions for status, success, error, and warning messages
# - Help documentation
# - Global output collector for deployment information
# - Utility functions
#

# Color codes for pretty output
readonly GREEN='\033[0;32m'
readonly BLUE='\033[0;34m'
readonly RED='\033[0;31m'
readonly TEAL='\033[0;36m'
readonly YELLOW='\033[1;33m'
readonly NC='\033[0m' # No Color

# Global output collector for deployment information (Bash 3 compatible)
DEPLOYMENT_OUTPUT_KEYS=(
    frontend_url
    backend_url
    oauth_proxy_url
    oauth_redirect_url
    frontend_webhook
    backend_webhook
    secret_key_generated
    backend_cors_origins
    domain
    vite_api_url
    github_webhooks_configured
)

for key in "${DEPLOYMENT_OUTPUT_KEYS[@]}"; do
    printf -v "DEPLOYMENT_OUTPUT__${key}" ''
done

#############################################
# Print Functions
#############################################

# Function to print colored status messages with library prefix
# Usage: print_status "message" ["library-name"]
print_status() {
    local message=$1
    local library=${2:-}
    
    if [[ -n "$library" ]]; then
        echo -e "${BLUE}[$library]${NC} ${TEAL}==>${NC} $message"
    else
        echo -e "${TEAL}==>${NC} $message"
    fi
}

print_success() {
    local message=$1
    local library=${2:-}
    
    if [[ -n "$library" ]]; then
        echo -e "${BLUE}[$library]${NC} ${GREEN}==>${NC} $message"
    else
        echo -e "${GREEN}==>${NC} $message"
    fi
}

print_error() {
    local message=$1
    local library=${2:-}
    
    if [[ -n "$library" ]]; then
        echo -e "${BLUE}[$library]${NC} ${RED}==>${NC} $message" >&2
    else
        echo -e "${RED}==>${NC} $message" >&2
    fi
}

print_warning() {
    local message=$1
    local library=${2:-}
    
    if [[ -n "$library" ]]; then
        echo -e "${BLUE}[$library]${NC} ${YELLOW}==>${NC} $message"
    else
        echo -e "${YELLOW}==>${NC} $message"
    fi
}

# Function to print section headers with box-drawing characters
print_section_header() {
    local title=$1
    echo
    echo -e "${BLUE}╔═══════════════════════════════════════════════════════════╗${NC}"
    printf "${BLUE}║${NC}  %-57s${BLUE}║${NC}\n" "$title"
    echo -e "${BLUE}╚═══════════════════════════════════════════════════════════╝${NC}"
}

#############################################
# Output Collection Functions
#############################################

# Functions to manage deployment output
add_deployment_output() {
    local key=$1
    local value=$2

    printf -v "DEPLOYMENT_OUTPUT__${key}" '%s' "$value"
}

get_deployment_output() {
    local key=$1

    local var="DEPLOYMENT_OUTPUT__${key}"
    printf '%s' "${!var-}"
}

# Function to print deployment summary
print_deployment_summary() {
    echo
    print_success "Deployment completed successfully!"
    echo
    echo -e "${TEAL}═══════════════════════════════════════════════════${NC}"
    echo -e "${TEAL}           DEPLOYMENT SUMMARY${NC}"
    echo -e "${TEAL}═══════════════════════════════════════════════════${NC}"
    echo
    
    local oauth_proxy_url oauth_redirect_url frontend_url backend_url frontend_webhook backend_webhook secret_key_generated github_webhooks_configured
    local domain backend_cors_origins vite_api_url

    oauth_proxy_url=$(get_deployment_output "oauth_proxy_url")
    oauth_redirect_url=$(get_deployment_output "oauth_redirect_url")
    frontend_url=$(get_deployment_output "frontend_url")
    backend_url=$(get_deployment_output "backend_url")
    frontend_webhook=$(get_deployment_output "frontend_webhook")
    backend_webhook=$(get_deployment_output "backend_webhook")
    secret_key_generated=$(get_deployment_output "secret_key_generated")
    github_webhooks_configured=$(get_deployment_output "github_webhooks_configured")
    domain=$(get_deployment_output "domain")
    backend_cors_origins=$(get_deployment_output "backend_cors_origins")
    vite_api_url=$(get_deployment_output "vite_api_url")

    # Application URLs
    if [[ -n "$oauth_proxy_url" ]]; then
        echo -e "${GREEN}OAuth2 Proxy URL (Main Entry Point):${NC}"
        echo "  https://$oauth_proxy_url"
        echo

        if [[ -n "$oauth_redirect_url" ]]; then
            echo -e "${YELLOW}⚠️  OAUTH CONFIGURATION REQUIRED:${NC}"
            echo -e "You must add this Redirect URL to your identity provider (e.g., App ID):"
            echo -e "${GREEN}  $oauth_redirect_url${NC}"
            echo
        fi
    fi
    
    if [[ -n "$frontend_url" ]]; then
        echo -e "${GREEN}Frontend URL:${NC}"
        echo "  https://$frontend_url"
        echo
    fi
    
    if [[ -n "$backend_url" ]]; then
        echo -e "${GREEN}Backend URL:${NC}"
        echo "  https://$backend_url"
        echo
    fi
    
    # Webhooks
    if [[ "$github_webhooks_configured" == "true" ]]; then
        print_success "GitHub webhooks have been configured automatically!"
        echo
    else
        if [[ -n "$frontend_webhook" ]]; then
            echo -e "${GREEN}Frontend Webhook URL:${NC}"
            echo "  $frontend_webhook"
            echo
        fi
        
        if [[ -n "$backend_webhook" ]]; then
            echo -e "${GREEN}Backend Webhook URL:${NC}"
            echo "  $backend_webhook"
            echo
        fi
        
        if [[ -n "$frontend_webhook" || -n "$backend_webhook" ]]; then
            print_status "Please add these webhook URLs to your GitHub repository"
            echo
        fi
    fi
    
    # Generated secrets
    if [[ -n "$secret_key_generated" ]]; then
        echo -e "${YELLOW}⚠️  IMPORTANT: Save this SECRET_KEY for future reference:${NC}"
        echo -e "${GREEN}SECRET_KEY=$secret_key_generated${NC}"
        echo
    fi
    
    # Build status note
    if [[ -n "$frontend_url" && -n "$backend_url" ]]; then
        echo -e "${BLUE}Note: Builds may take a few minutes to complete.${NC}"
        echo "Once builds are finished, your application will be accessible at the URLs above."
        echo
    fi
    
    echo -e "${TEAL}═══════════════════════════════════════════════════${NC}"
    echo
}

#############################################
# Utility Functions
#############################################

# Function to determine if a variable is sensitive
is_sensitive_var() {
    local var_name=$1
    local sensitive_vars=("PASSWORD" "SECRET" "KEY" "TOKEN" "SID")
    
    for sensitive in "${sensitive_vars[@]}"; do
        if [[ "$var_name" == *"$sensitive"* ]]; then
            return 0
        fi
    done
    
    return 1
}

# Function to show help
show_help() {
    echo -e "
${TEAL}OpenShift Deployment Script${NC}

${GREEN}DESCRIPTION:${NC}
    Deploys a full-stack application (Frontend, Backend, PostgreSQL) to OpenShift.
    All configuration is loaded from the .env.production file.

${GREEN}USAGE:${NC}
    $0 [OPTIONS]

${GREEN}OPTIONS:${NC}
    -h, --help              Show this help message and exit
    --env-file PATH         Specify custom environment file (default: scripts/.env.production)
    --backend-only          Deploy only the backend application (skips frontend)
    --no-db                 Skip database deployment (assumes external DB or none required)
    --reset-prod-db         Reset production database (deletes and recreates PostgreSQL storage)
    --regenerate-ssh-key    Delete and regenerate SSH keys for GitHub access
    --show-env-values       Display environment variable names and values during loading (default: silent)

${GREEN}REQUIRED ENVIRONMENT VARIABLES:${NC}
    Main Variables:
        APP_NAME                    Application name (lowercase, alphanumeric, hyphens)
        PROJECT_NAME                OpenShift project name (lowercase, alphanumeric, hyphens)
        GIT_SSH_URL                 Git repository SSH URL (e.g., git@github.com:user/repo.git)
        FIRST_SUPERUSER             Admin email address
        FIRST_SUPERUSER_PASSWORD    Admin password (min 8 characters)
        SIGNUP_ACCESS_PASSWORD      Signup password (min 8 characters, can be empty)
        ENVIRONMENT                 Environment name (e.g., production)
        SECRET_KEY                  Backend secret key (min 8 characters)
        
    Database Variables:
        POSTGRES_SERVER             PostgreSQL server hostname
        POSTGRES_PORT               PostgreSQL port
        POSTGRES_DB                 Database name
        POSTGRES_USER               Database user
        POSTGRES_PASSWORD           Database password (min 8 characters)

${GREEN}OPTIONAL ENVIRONMENT VARIABLES:${NC}
    GITHUB_TOKEN                GitHub Personal Access Token (for webhook automation)
    BACKEND_CORS_ORIGINS        CORS origins (auto-generated if not provided)
    VITE_*                      Any variable prefixed with VITE_ is injected into frontend

${GREEN}EXAMPLES:${NC}
    # Normal deployment
    $0

    # Use custom env file
    $0 --env-file /path/to/.env.custom

    # Reset database and deploy
    $0 --reset-prod-db

    # Regenerate SSH keys
    $0 --regenerate-ssh-key

    # Show environment variable values (for debugging)
    $0 --show-env-values

    # Backend-only deployment
    $0 --backend-only

    # Backend-only deployment without database
    $0 --backend-only --no-db

${GREEN}PREREQUISITES:${NC}
    - OpenShift CLI (oc) version 4.14 or higher
    - Logged into OpenShift cluster (oc login)
    - .env.production file with all required variables
    - GitHub deploy key configured (or will be prompted)

${GREEN}DOCUMENTATION:${NC}
    For detailed documentation, see scripts/README.md
"
}

# Made with Bob
