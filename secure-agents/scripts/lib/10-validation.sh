#!/usr/bin/env bash
#
# Validation Functions Library
#
# This library provides validation functions for:
# - Project and application names
# - Email addresses
# - Git SSH URLs
# - API keys
# - Password lengths
#

#############################################
# Validation Functions
#############################################

# Function to validate project/app name
validate_name() {
    local name=$1
    if [[ ! $name =~ ^[a-z0-9-]+$ ]]; then
        print_error "Invalid name: '$name'. Must contain only lowercase letters, numbers, and hyphens." "validation"
        return 1
    fi
    return 0
}

# Function to validate email
validate_email() {
    local email=$1
    if [[ ! $email =~ ^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$ ]]; then
        print_error "Invalid email: '$email'" "validation"
        return 1
    fi
    return 0
}

# Function to validate git SSH URL
validate_git_url() {
    local url=$1
    # Check if URL starts with git@ or ssh:// and ends with .git
    if [[ ! $url =~ ^(git@|ssh://).+\.git$ ]]; then
        print_error "Invalid Git SSH URL: '$url'. Must start with 'git@' or 'ssh://' and end with '.git'" "validation"
        return 1
    fi
    return 0
}

# Function to validate API key (min length 16, must be power of 2: 16, 32, 64)
validate_api_key() {
    local key=$1
    local length=${#key}
    
    if [[ $length -lt 16 ]]; then
        print_error "API key must be at least 16 characters long (current: $length)" "validation"
        return 1
    fi
    
    # Check if length is a power of 2 (16, 32, 64, 128, etc.)
    if [[ $length -ne 16 && $length -ne 32 && $length -ne 64 && $length -ne 128 && $length -ne 256 ]]; then
        print_error "API key length must be a power of 2 (16, 32, 64, 128, 256). Current length: $length" "validation"
        return 1
    fi
    
    return 0
}

# Function to validate password length (min 8 characters)
validate_password_length() {
    local password=$1
    local var_name=$2
    
    if [[ ${#password} -lt 8 ]]; then
        print_error "$var_name must be at least 8 characters long (current: ${#password})" "validation"
        return 1
    fi
    
    return 0
}

# Function to get validation function for a variable
get_validation_function() {
    local var_name=$1
    case "$var_name" in
        APP_NAME|PROJECT_NAME)
            echo "validate_name"
            ;;
        GIT_SSH_URL)
            echo "validate_git_url"
            ;;
        FIRST_SUPERUSER)
            echo "validate_email"
            ;;
        API_KEY)
            echo "validate_api_key"
            ;;
        *)
            echo ""
            ;;
    esac
}

# Made with Bob
