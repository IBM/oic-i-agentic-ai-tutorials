#!/usr/bin/env bash
#
# Vault Audit Log Viewer for OpenShift
# 
# This script provides a beautiful, colored view of Vault audit logs
# with filtering, statistics, and real-time monitoring capabilities.
#
# Usage: ./view-vault-logs.sh [OPTIONS]
#
# Examples:
#   ./view-vault-logs.sh                          # Show last 50 logs
#   ./view-vault-logs.sh --follow                 # Live tail mode
#   ./view-vault-logs.sh --user Alice             # Filter by user
#   ./view-vault-logs.sh --denied                 # Show only denied requests
#   ./view-vault-logs.sh --stats                  # Show statistics
#   ./view-vault-logs.sh --namespace my-project   # Specify namespace
#

set -eo pipefail

# ============================================================================
# Configuration
# ============================================================================

# Default values
NAMESPACE="${VAULT_NAMESPACE:-confused-deputy}"
POD_NAME=""
LINES=50
FOLLOW=false
FILTER_USER=""
FILTER_PATH=""
FILTER_OPERATION=""
SHOW_DENIED_ONLY=false
SHOW_ALLOWED_ONLY=false
SHOW_STATS=false
SHOW_RAW=false
CONTAINER_NAME="vault"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
GRAY='\033[0;90m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# ============================================================================
# Helper Functions
# ============================================================================

print_error() {
    echo -e "${RED}ERROR: $1${NC}" >&2
}

print_warning() {
    echo -e "${YELLOW}WARNING: $1${NC}" >&2
}

print_info() {
    echo -e "${CYAN}INFO: $1${NC}"
}

print_success() {
    echo -e "${GREEN}SUCCESS: $1${NC}"
}

show_help() {
    cat << EOF
${BOLD}Vault Audit Log Viewer for OpenShift${NC}

${BOLD}USAGE:${NC}
    $0 [OPTIONS]

${BOLD}OPTIONS:${NC}
    -h, --help              Show this help message
    -n, --namespace NAME    OpenShift namespace (default: $NAMESPACE)
    -p, --pod NAME          Specific pod name (auto-detected if not provided)
    -l, --lines NUM         Number of log lines to show (default: $LINES)
    -f, --follow            Follow log output (live tail)
    
    ${BOLD}Filtering:${NC}
    -u, --user USER         Filter by user display name (e.g., "Alice")
    --path PATH             Filter by Vault path (e.g., "database/creds")
    --operation OP          Filter by operation (read, update, delete, etc.)
    --denied                Show only denied requests
    --allowed               Show only allowed requests
    
    ${BOLD}Display:${NC}
    -s, --stats             Show statistics summary
    -r, --raw               Show raw JSON (no formatting)
    -c, --container NAME    Container name (default: $CONTAINER_NAME)

${BOLD}EXAMPLES:${NC}
    # Show last 50 logs with nice formatting
    $0

    # Live tail mode
    $0 --follow

    # Filter by user Alice
    $0 --user Alice

    # Show only denied requests
    $0 --denied

    # Show statistics for last 100 logs
    $0 --lines 100 --stats

    # Filter by path and operation
    $0 --path database/creds --operation read

    # Combine filters
    $0 --user Alice --denied --follow

${BOLD}ENVIRONMENT VARIABLES:${NC}
    VAULT_NAMESPACE         Default namespace (overridden by --namespace)

EOF
}

# ============================================================================
# Argument Parsing
# ============================================================================

parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -n|--namespace)
                NAMESPACE="$2"
                shift 2
                ;;
            -p|--pod)
                POD_NAME="$2"
                shift 2
                ;;
            -l|--lines)
                LINES="$2"
                shift 2
                ;;
            -f|--follow)
                FOLLOW=true
                shift
                ;;
            -u|--user)
                FILTER_USER="$2"
                shift 2
                ;;
            --path)
                FILTER_PATH="$2"
                shift 2
                ;;
            --operation)
                FILTER_OPERATION="$2"
                shift 2
                ;;
            --denied)
                SHOW_DENIED_ONLY=true
                shift
                ;;
            --allowed)
                SHOW_ALLOWED_ONLY=true
                shift
                ;;
            -s|--stats)
                SHOW_STATS=true
                shift
                ;;
            -r|--raw)
                SHOW_RAW=true
                shift
                ;;
            -c|--container)
                CONTAINER_NAME="$2"
                shift 2
                ;;
            *)
                print_error "Unknown option: $1"
                echo "Use --help for usage information"
                exit 1
                ;;
        esac
    done
}

# ============================================================================
# Validation Functions
# ============================================================================

check_prerequisites() {
    # Check if oc is installed
    if ! command -v oc &> /dev/null; then
        print_error "OpenShift CLI (oc) is not installed"
        echo "Please install it from: https://docs.openshift.com/container-platform/latest/cli_reference/openshift_cli/getting-started-cli.html"
        exit 1
    fi

    # Check if jq is installed
    if ! command -v jq &> /dev/null; then
        print_error "jq is not installed"
        echo "Please install it: brew install jq (macOS) or apt-get install jq (Linux)"
        exit 1
    fi

    # Check if logged in to OpenShift
    if ! oc whoami &> /dev/null; then
        print_error "Not logged in to OpenShift"
        echo "Please login using: oc login"
        exit 1
    fi
}

find_vault_pod() {
    if [[ -n "$POD_NAME" ]]; then
        # Verify the specified pod exists
        if ! oc get pod "$POD_NAME" -n "$NAMESPACE" &> /dev/null; then
            print_error "Pod '$POD_NAME' not found in namespace '$NAMESPACE'"
            exit 1
        fi
        return
    fi

    # Auto-detect Vault pod - try multiple label selectors
    print_info "Auto-detecting Vault pod in namespace '$NAMESPACE'..."
    
    # Try different label selectors
    local selectors=(
        "app.kubernetes.io/component=vault"
        "app.kubernetes.io/name=vault"
        "app=vault"
        "component=vault"
    )
    
    for selector in "${selectors[@]}"; do
        POD_NAME=$(oc get pods -n "$NAMESPACE" -l "$selector" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
        if [[ -n "$POD_NAME" ]]; then
            print_success "Found Vault pod: $POD_NAME (using selector: $selector)"
            return
        fi
    done
    
    # If still not found, try to find any pod with "vault" in the name
    POD_NAME=$(oc get pods -n "$NAMESPACE" -o jsonpath='{.items[?(@.metadata.name contains "vault")].metadata.name}' 2>/dev/null | awk '{print $1}')
    
    if [[ -n "$POD_NAME" ]]; then
        print_success "Found Vault pod: $POD_NAME (by name pattern)"
        return
    fi
    
    # Still not found - show helpful error message
    print_error "No Vault pod found in namespace '$NAMESPACE'"
    echo ""
    echo "Available pods in namespace '$NAMESPACE':"
    oc get pods -n "$NAMESPACE" -o custom-columns=NAME:.metadata.name,STATUS:.status.phase 2>/dev/null || echo "  (unable to list pods)"
    echo ""
    echo "Please specify the pod name manually with: --pod <pod-name>"
    echo "Example: $0 --pod vault-0"
    exit 1
}

# ============================================================================
# Log Processing Functions
# ============================================================================

format_log_entry() {
    local json="$1"
    
    # Extract key fields
    local time=$(echo "$json" | jq -r '.time // "N/A"')
    local type=$(echo "$json" | jq -r '.type // "N/A"')
    local user=$(echo "$json" | jq -r '.auth.display_name // "N/A"')
    local operation=$(echo "$json" | jq -r '.request.operation // "N/A"')
    local path=$(echo "$json" | jq -r '.request.path // "N/A"')
    local allowed=$(echo "$json" | jq -r '.auth.policy_results.allowed // "N/A"')
    local error=$(echo "$json" | jq -r '.error // ""')
    local policies=$(echo "$json" | jq -r '.auth.policies // [] | join(", ")')
    
    # Apply filters
    if [[ -n "$FILTER_USER" ]] && [[ "$user" != *"$FILTER_USER"* ]]; then
        return
    fi
    
    if [[ -n "$FILTER_PATH" ]] && [[ "$path" != *"$FILTER_PATH"* ]]; then
        return
    fi
    
    if [[ -n "$FILTER_OPERATION" ]] && [[ "$operation" != "$FILTER_OPERATION" ]]; then
        return
    fi
    
    if [[ "$SHOW_DENIED_ONLY" == "true" ]] && [[ "$allowed" != "false" ]]; then
        return
    fi
    
    if [[ "$SHOW_ALLOWED_ONLY" == "true" ]] && [[ "$allowed" != "true" ]]; then
        return
    fi
    
    # Format timestamp
    local formatted_time=$(date -j -f "%Y-%m-%dT%H:%M:%S" "${time:0:19}" "+%Y-%m-%d %H:%M:%S" 2>/dev/null || echo "$time")
    
    # Color coding based on status
    local status_color=$GREEN
    local status_icon="✓"
    if [[ "$allowed" == "false" ]] || [[ -n "$error" ]]; then
        status_color=$RED
        status_icon="✗"
    fi
    
    # Type color
    local type_color=$BLUE
    if [[ "$type" == "response" ]]; then
        type_color=$MAGENTA
    fi
    
    # Print formatted entry
    echo -e "${GRAY}${formatted_time}${NC} ${type_color}[${type}]${NC} ${status_color}${status_icon}${NC} ${WHITE}${user}${NC} ${YELLOW}${operation}${NC} ${CYAN}${path}${NC}"
    
    if [[ -n "$policies" ]] && [[ "$policies" != "null" ]]; then
        echo -e "  ${GRAY}├─ Policies: ${policies}${NC}"
    fi
    
    if [[ -n "$error" ]]; then
        echo -e "  ${GRAY}└─ ${RED}Error: ${error}${NC}"
    fi
    
    echo ""
}

show_statistics() {
    local logs="$1"
    
    echo -e "\n${BOLD}${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${CYAN}                    VAULT AUDIT LOG STATISTICS${NC}"
    echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════════${NC}\n"
    
    # Total events
    local total=$(echo "$logs" | wc -l | tr -d ' ')
    echo -e "${WHITE}Total Events:${NC} ${BOLD}$total${NC}"
    
    # Request vs Response
    local requests=$(echo "$logs" | jq -r 'select(.type == "request")' | wc -l | tr -d ' ')
    local responses=$(echo "$logs" | jq -r 'select(.type == "response")' | wc -l | tr -d ' ')
    echo -e "${WHITE}Requests:${NC} ${BOLD}$requests${NC}"
    echo -e "${WHITE}Responses:${NC} ${BOLD}$responses${NC}"
    
    # Success vs Denied
    local allowed=$(echo "$logs" | jq -r 'select(.auth.policy_results.allowed == true)' | wc -l | tr -d ' ')
    local denied=$(echo "$logs" | jq -r 'select(.auth.policy_results.allowed == false)' | wc -l | tr -d ' ')
    echo -e "\n${GREEN}✓ Allowed:${NC} ${BOLD}$allowed${NC}"
    echo -e "${RED}✗ Denied:${NC} ${BOLD}$denied${NC}"
    
    # Top Users
    echo -e "\n${BOLD}${YELLOW}Top Users:${NC}"
    echo "$logs" | jq -r '.auth.display_name // "unknown"' | sort | uniq -c | sort -rn | head -5 | while read count user; do
        echo -e "  ${WHITE}$user:${NC} $count"
    done
    
    # Top Operations
    echo -e "\n${BOLD}${YELLOW}Top Operations:${NC}"
    echo "$logs" | jq -r '.request.operation // "unknown"' | sort | uniq -c | sort -rn | head -5 | while read count op; do
        echo -e "  ${WHITE}$op:${NC} $count"
    done
    
    # Top Paths
    echo -e "\n${BOLD}${YELLOW}Top Paths:${NC}"
    echo "$logs" | jq -r '.request.path // "unknown"' | sort | uniq -c | sort -rn | head -5 | while read count path; do
        echo -e "  ${CYAN}$path:${NC} $count"
    done
    
    # Errors
    local errors=$(echo "$logs" | jq -r 'select(.error != null and .error != "")' | wc -l | tr -d ' ')
    if [[ "$errors" -gt 0 ]]; then
        echo -e "\n${BOLD}${RED}Errors: $errors${NC}"
        echo "$logs" | jq -r 'select(.error != null and .error != "") | .error' | sort | uniq -c | sort -rn | head -5 | while read count error; do
            echo -e "  ${RED}$error:${NC} $count"
        done
    fi
    
    echo -e "\n${BOLD}${CYAN}═══════════════════════════════════════════════════════════${NC}\n"
}

# ============================================================================
# Main Execution
# ============================================================================

main() {
    # Parse arguments
    parse_arguments "$@"
    
    # Check prerequisites
    check_prerequisites
    
    # Find Vault pod
    find_vault_pod
    
    # Build oc logs command
    local oc_cmd="oc logs -n $NAMESPACE $POD_NAME -c $CONTAINER_NAME"
    
    if [[ "$FOLLOW" == "true" ]]; then
        # Follow mode: show last N lines first, then stream new ones
        oc_cmd="$oc_cmd -f --tail=$LINES"
    else
        # Non-follow mode: just show last N lines
        oc_cmd="$oc_cmd --tail=$LINES"
    fi
    
    # Print header
    echo -e "\n${BOLD}${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${CYAN}              VAULT AUDIT LOG VIEWER${NC}"
    echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${WHITE}Namespace:${NC} $NAMESPACE"
    echo -e "${WHITE}Pod:${NC} $POD_NAME"
    echo -e "${WHITE}Container:${NC} $CONTAINER_NAME"
    
    if [[ -n "$FILTER_USER" ]]; then
        echo -e "${WHITE}Filter User:${NC} $FILTER_USER"
    fi
    if [[ -n "$FILTER_PATH" ]]; then
        echo -e "${WHITE}Filter Path:${NC} $FILTER_PATH"
    fi
    if [[ -n "$FILTER_OPERATION" ]]; then
        echo -e "${WHITE}Filter Operation:${NC} $FILTER_OPERATION"
    fi
    if [[ "$SHOW_DENIED_ONLY" == "true" ]]; then
        echo -e "${WHITE}Filter:${NC} ${RED}Denied Only${NC}"
    fi
    if [[ "$SHOW_ALLOWED_ONLY" == "true" ]]; then
        echo -e "${WHITE}Filter:${NC} ${GREEN}Allowed Only${NC}"
    fi
    
    echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════════${NC}\n"
    
    # Get logs
    if [[ "$SHOW_STATS" == "true" ]]; then
        # Collect all logs for statistics
        local logs=$($oc_cmd 2>/dev/null | grep '^{' || true)
        
        if [[ -z "$logs" ]]; then
            print_warning "No audit logs found"
            exit 0
        fi
        
        show_statistics "$logs"
        exit 0
    fi
    
    # Stream and format logs
    if [[ "$SHOW_RAW" == "true" ]]; then
        # Raw JSON output
        if [[ "$FOLLOW" == "true" ]]; then
            print_info "Streaming logs in real-time (press Ctrl+C to stop)..."
            $oc_cmd 2>/dev/null | grep '^{' | jq '.'
        else
            print_info "Fetching last $LINES audit log entries..."
            local json_count=$($oc_cmd 2>/dev/null | grep '^{' | tail -n "$LINES" | tee >(wc -l | xargs echo "Found" >&2) | jq '.')
        fi
    else
        # Formatted output
        if [[ "$FOLLOW" == "true" ]]; then
            # Follow mode - stream all logs
            print_info "Streaming logs in real-time (press Ctrl+C to stop)..."
            echo ""
            $oc_cmd 2>/dev/null | while IFS= read -r line; do
                # Only process JSON lines (audit logs)
                if [[ "$line" =~ ^\{ ]]; then
                    format_log_entry "$line"
                fi
            done
        else
            # Non-follow mode - limit to last N JSON entries
            print_info "Fetching last $LINES audit log entries..."
            local json_lines=$($oc_cmd 2>/dev/null | grep '^{' | tail -n "$LINES")
            
            if [[ -z "$json_lines" ]]; then
                echo ""
                print_warning "No audit logs found in the last $LINES container log lines"
                echo "Try increasing --lines or check if audit logging is enabled in Vault"
                exit 0
            fi
            
            local count=$(echo "$json_lines" | wc -l | tr -d ' ')
            print_success "Found $count audit log entries"
            echo ""
            
            local processed=0
            echo "$json_lines" | while IFS= read -r line; do
                if [[ -n "$line" ]]; then
                    format_log_entry "$line"
                    ((processed++))
                fi
            done
            
            echo ""
            echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════════${NC}"
            echo -e "${GREEN}✓ Finished displaying $count audit log entries${NC}"
            echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════════${NC}"
            echo ""
        fi
    fi
}

# Execute main function
main "$@"

# Made with Bob
