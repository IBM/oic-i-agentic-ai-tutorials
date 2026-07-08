#!/usr/bin/env bash
#
# OpenShift Deployment Script (Refactored)
#
# This script deploys an application to OpenShift with the following features:
# - Modular library structure for maintainability
# - Idempotent operations (can be run multiple times without side effects)
# - Variables loaded dynamically from .env.production file
# - Comprehensive validation for all required variables
# - Best practices for bash scripting
# - Sensitive values are masked in output
# - Dynamic secret creation from environment variables
# - Automatic VITE_ prefix injection for frontend
# - SSH key management with GitHub deploy key verification
# - Database reset functionality
# - GitHub webhook automation
# - Clean summary output at the end
#
# Usage: ./oc-deploy.sh [OPTIONS]
#
# For detailed documentation, see scripts/README.md
#

set -eo pipefail

# Get directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LIB_DIR="$SCRIPT_DIR/lib"

# Source all library files in order
for lib_file in "$LIB_DIR"/*.sh; do
    if [[ -f "$lib_file" ]]; then
        # shellcheck source=/dev/null
        source "$lib_file"
    fi
done

# Default environment file location (project root)
ENV_FILE="$PROJECT_ROOT/.env.production"

# Default GitHub host (can be overridden in .env.production)
# Set to github.ibm.com for IBM GitHub Enterprise
# Set to github.com for public GitHub
DEFAULT_GITHUB_HOST="github.ibm.com"

# Flags
RESET_PROD_DB=false
RESET_MONGODB=false
REGENERATE_SSH_KEY=false
SHOW_HELP=false
SHOW_ENV_VALUES=false
FLAVOR_OVERRIDE=""

#############################################
# Argument Parsing
#############################################

# Parse command line arguments
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                SHOW_HELP=true
                shift
                ;;
            --env-file)
                ENV_FILE="$2"
                shift 2
                ;;
            --flavor)
                FLAVOR_OVERRIDE="$2"
                shift 2
                ;;
            --backend-only)
                print_warning "DEPRECATED: --backend-only flag is deprecated. Use CEN_FLAVOR=backend-only in .env file or --flavor backend-only"
                FLAVOR_OVERRIDE="backend-only"
                shift
                ;;
            --no-db)
                print_warning "DEPRECATED: --no-db flag is deprecated. Use CEN_FLAVOR=backend-only-no-db in .env file or --flavor backend-only-no-db"
                FLAVOR_OVERRIDE="backend-only-no-db"
                shift
                ;;
            --reset-prod-db)
                RESET_PROD_DB=true
                shift
                ;;
            --reset-mongodb)
                RESET_MONGODB=true
                shift
                ;;
            --regenerate-ssh-key)
                REGENERATE_SSH_KEY=true
                shift
                ;;
            --show-env-values)
                SHOW_ENV_VALUES=true
                shift
                ;;
            *)
                print_error "Unknown option: $1"
                echo "Use --help for usage information"
                exit 1
                ;;
        esac
    done
}

#############################################
# Main Execution
#############################################

# Main function
main() {
    # Parse arguments
    parse_arguments "$@"
    
    # Show help if requested
    if [[ "$SHOW_HELP" == "true" ]]; then
        show_help
        exit 0
    fi
    
    echo
    echo -e "${TEAL}Welcome to the OpenShift Deployment Script!${NC}"
    echo
    
    # ============================================================
    # PHASE 1: INITIALIZATION
    # ============================================================
    print_section_header "PHASE 1: INITIALIZATION"
    
    # Load environment variables from file
    load_env_file "$ENV_FILE" "$SHOW_ENV_VALUES" || exit 1
    
    # Apply flavor override from command line if provided
    if [[ -n "$FLAVOR_OVERRIDE" ]]; then
        export CEN_FLAVOR="$FLAVOR_OVERRIDE"
        print_status "Deployment flavor overridden via command line: $FLAVOR_OVERRIDE"
    fi
    
    # Validate all required variables (this also detects flavor and sets deployment flags)
    validate_required_vars || exit 1
    
    # ============================================================
    # PHASE 2: PREREQUISITES CHECK
    # ============================================================
    print_section_header "PHASE 2: PREREQUISITES CHECK"
    
    # Check OpenShift client and login
    check_oc_version || exit 1
    check_oc_login || exit 1
    
    # ============================================================
    # PHASE 3: PROJECT SETUP
    # ============================================================
    print_section_header "PHASE 3: PROJECT SETUP"
    
    # Setup project
    setup_project || exit 1
    
    # Handle SSH key regeneration flag
    if [[ "$REGENERATE_SSH_KEY" == "true" ]]; then
        delete_ssh_keys || exit 1
    fi
    
    # Setup SSH keys
    setup_ssh_keys || exit 1
    
    # Handle database reset flags
    if [[ "$RESET_PROD_DB" == "true" ]]; then
        reset_production_database || exit 1
        print_deployment_summary
        exit 0
    fi
    
    if [[ "$RESET_MONGODB" == "true" ]]; then
        reset_mongodb_database || exit 1
        print_deployment_summary
        exit 0
    fi
    
    # ============================================================
    # PHASE 4: DATABASE DEPLOYMENT
    # ============================================================
    print_section_header "PHASE 4: DATABASE DEPLOYMENT"
    
    # Create the initial app environment secret
    create_initial_app_env_secret || exit 1
    
    # Deploy PostgreSQL database
    if [[ "$DEPLOY_DB" == "true" ]]; then
        deploy_database || exit 1
    else
        print_status "Skipping PostgreSQL deployment (DEPLOY_DB=false)"
    fi
    
    # Deploy MongoDB (if enabled)
    if [[ "${DEPLOY_MONGODB:-false}" == "true" ]]; then
        print_status "MongoDB is enabled, deploying..."
        deploy_mongodb || exit 1
    else
        print_status "Skipping MongoDB deployment (DEPLOY_MONGODB not enabled)"
    fi

    # Pre-configure OAuth to avoid backend restarts
    if [[ "${DEPLOY_OAUTH:-false}" == "true" ]]; then
        print_status "OAuth2 Proxy is enabled. Pre-configuring secrets to avoid backend restarts..."
        # Order matters: we need the route first to get the URL for the secret
        create_oauth_proxy_service || exit 1
        create_oauth_proxy_route || exit 1
        create_oauth_proxy_secret || exit 1
        update_backend_with_oauth_url || exit 1
    fi
    
    # ============================================================
    # PHASE 5: APPLICATION DEPLOYMENT
    # ============================================================
    print_section_header "PHASE 5: APPLICATION DEPLOYMENT"
    
    # Deploy Vault (if enabled by flavor)
    if [[ "${DEPLOY_VAULT:-false}" == "true" ]]; then
        print_status "Vault is enabled, deploying..."
        deploy_vault || exit 1
    fi
    
    # Deploy frontend (if enabled by flavor)
    if [[ "${DEPLOY_FRONTEND:-true}" == "true" ]]; then
        deploy_frontend || exit 1
    else
        print_status "Skipping frontend deployment (flavor: ${CEN_FLAVOR})"
    fi
    
    # Deploy backend (always deployed)
    deploy_backend || exit 1
    
    # Deploy MCP server (if enabled by flavor)
    if [[ "${DEPLOY_MCP:-false}" == "true" ]]; then
        print_status "MCP Server is enabled, deploying..."
        deploy_mcp || exit 1
    fi
    
    # Update the app environment secret with frontend/backend URLs
    update_app_env_secret_with_urls || exit 1
    
    # Deploy OAuth2 Proxy (if enabled by flavor)
    if [[ "${DEPLOY_OAUTH:-false}" == "true" ]]; then
        print_status "OAuth2 Proxy is enabled, deploying..."
        deploy_oauth_proxy || exit 1
    fi
    
    # ============================================================
    # PHASE 6: CONFIGURATION
    # ============================================================
    print_section_header "PHASE 6: CONFIGURATION"
    
    # Configure frontend (if enabled by flavor)
    if [[ "${DEPLOY_FRONTEND:-true}" == "true" ]]; then
        configure_frontend || exit 1
    fi
    
    configure_backend || exit 1
    
    # Configure MCP (if enabled by flavor)
    if [[ "${DEPLOY_MCP:-false}" == "true" ]]; then
        configure_mcp || exit 1
    fi
    
    # Group resources
    group_resources || exit 1
    
    # ============================================================
    # PHASE 7: POST-DEPLOYMENT
    # ============================================================
    print_section_header "PHASE 7: POST-DEPLOYMENT"
    
    # Setup webhooks
    setup_webhooks || exit 1
    
    # Print deployment summary
    print_deployment_summary
    
    return 0
}

# Execute main function with all arguments
main "$@"

# Made with Bob