#!/usr/bin/env bash
#
# OpenShift Helper Functions Library
#
# This library provides:
# - Resource existence checking
# - Resource creation/update
# - OpenShift client version checking
# - Login status verification
# - Project setup
#
#############################################
# OpenShift Helper Functions
#############################################

# Function to check if a resource exists
resource_exists() {
    local resource_type=$1
    local resource_name=$2
    
    oc get "$resource_type" "$resource_name" &>/dev/null
    return $?
}

# Function to create or update a resource from a heredoc
apply_resource() {
    local resource_content=$1
    local resource_type
    local resource_name
    
    # Extract resource type and name from the content
    resource_type=$(echo "$resource_content" | grep -E "^kind:" | awk '{print $2}' | tr '[:upper:]' '[:lower:]')
    resource_name=$(echo "$resource_content" | grep -E "^  name:" | head -1 | awk '{print $2}')
    
    if [[ -z "$resource_type" || -z "$resource_name" ]]; then
        print_error "Could not determine resource type or name" "openshift"
        return 1
    fi
    
    print_status "Applying $resource_type/$resource_name..." "openshift"
    echo "$resource_content" | oc apply -f -
    return $?
}

# Check OpenShift client version
check_oc_version() {
    print_status "Checking OpenShift client version..." "openshift"
    local oc_version
    oc_version=$(oc version 2>/dev/null | grep "Client Version:" | awk '{print $3}' | cut -d'.' -f2)
    
    if [ -z "$oc_version" ] || [ "$oc_version" -lt "14" ]; then
        print_error "OpenShift client version 4.14 or higher is required" "openshift"
        print_error "Current version: $(oc version 2>/dev/null | grep "Client Version:")" "openshift"
        return 1
    fi
    
    print_success "OpenShift client version is compatible" "openshift"
    return 0
}

# Check OpenShift login status
check_oc_login() {
    print_status "Checking OpenShift instance and login status..." "openshift"
    
    if ! oc whoami --show-server &>/dev/null || ! oc whoami &>/dev/null; then
        print_error "Not logged into OpenShift. Please login first using:" "openshift"
        echo "oc login --token=<token> --server=<server-url>"
        return 1
    fi
    
    OPENSHIFT_SERVER=$(oc whoami --show-server)
    echo -e "${TEAL}You are about to deploy to:${NC}"
    echo -e "${TEAL}$OPENSHIFT_SERVER${NC}"
    read -p "Do you want to continue? (y/n): " CONTINUE
    
    if [[ ! $CONTINUE =~ ^[Yy]$ ]]; then
        print_error "Deployment cancelled" "openshift"
        return 1
    fi
    
    return 0
}

#############################################
# Project Setup Functions
#############################################

# Function to handle project creation or selection
setup_project() {
    # Check if project exists
    if resource_exists "project" "$PROJECT_NAME"; then
        print_status "Project '$PROJECT_NAME' already exists." "openshift"
        read -p "Do you want to switch to this project and continue deployment? (y/n): " USE_EXISTING
        if [[ $USE_EXISTING =~ ^[Yy]$ ]]; then
            oc project "$PROJECT_NAME" || {
                print_error "Failed to switch to project" "openshift"
                return 1
            }
        else
            print_error "Deployment cancelled" "openshift"
            return 1
        fi
    else
        # Create new project
        print_status "Creating new project '$PROJECT_NAME'..." "openshift"
        oc new-project "$PROJECT_NAME" || {
            print_error "Failed to create project" "openshift"
            return 1
        }
    fi
    
    return 0
}

# Made with Bob
