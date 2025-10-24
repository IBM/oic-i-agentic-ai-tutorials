#!/usr/bin/env bash
set -euo pipefail

# HR Agent Pure A2A Testing Script
# This script runs 10 comprehensive tests against the deployed A2A agent

AGENT_URL="${1:-https://hr-agent-pure-a2a.20xtogjmfdje.us-south.codeengine.appdomain.cloud}"
PASSED=0
FAILED=0

echo "========================================"
echo "HR Agent Pure A2A Test Suite"
echo "========================================"
echo "Agent URL: $AGENT_URL"
echo ""

# Helper function to run a test
run_test() {
    local test_num="$1"
    local test_name="$2"
    local test_cmd="$3"
    local expected_pattern="$4"

    echo "Test $test_num: $test_name"
    echo "---"

    if result=$(eval "$test_cmd" 2>&1); then
        if echo "$result" | grep -q "$expected_pattern"; then
            echo " PASSED"
            ((PASSED++))
        else
            echo " FAILED - Expected pattern '$expected_pattern' not found"
            echo "Response: $result"
            ((FAILED++))
        fi
    else
        echo " FAILED - Command execution error"
        echo "Error: $result"
        ((FAILED++))
    fi
    echo ""
}

# Test 1: Agent Card Availability
run_test "1" "Agent Card Availability" \
    "curl -sS --max-time 10 '$AGENT_URL/.well-known/agent.json'" \
    "HR Agent"

# Test 2: Agent Card Contains Skills
run_test "2" "Agent Card Contains Skills" \
    "curl -sS --max-time 10 '$AGENT_URL/.well-known/agent.json'" \
    "employee_onboarding"

# Test 3: Onboard Employee - John Doe
run_test "3" "Onboard John Doe as Software Engineer" \
    "curl -sS --max-time 15 -X POST '$AGENT_URL/' -H 'Content-Type: application/json' -d '{\"jsonrpc\":\"2.0\",\"method\":\"message/send\",\"params\":{\"message\":{\"messageId\":\"msg-001\",\"role\":\"user\",\"parts\":[{\"text\":\"Onboard John Doe as Software Engineer\"}]}},\"id\":1}'" \
    "John Doe"

# Test 4: Onboard Employee - Sarah Williams
run_test "4" "Onboard Sarah Williams as Data Analyst" \
    "curl -sS --max-time 15 -X POST '$AGENT_URL/' -H 'Content-Type: application/json' -d '{\"jsonrpc\":\"2.0\",\"method\":\"message/send\",\"params\":{\"message\":{\"messageId\":\"msg-002\",\"role\":\"user\",\"parts\":[{\"text\":\"Onboard Sarah Williams as Data Analyst\"}]}},\"id\":2}'" \
    "Sarah Williams"

# Test 5: Onboard Employee - Maria Garcia
run_test "5" "Onboard Maria Garcia as Product Manager" \
    "curl -sS --max-time 15 -X POST '$AGENT_URL/' -H 'Content-Type: application/json' -d '{\"jsonrpc\":\"2.0\",\"method\":\"message/send\",\"params\":{\"message\":{\"messageId\":\"msg-003\",\"role\":\"user\",\"parts\":[{\"text\":\"Onboard Maria Garcia as Product Manager\"}]}},\"id\":3}'" \
    "Maria Garcia"

# Test 6: Onboard Employee - James Chen
run_test "6" "Onboard James Chen as DevOps Engineer" \
    "curl -sS --max-time 15 -X POST '$AGENT_URL/' -H 'Content-Type: application/json' -d '{\"jsonrpc\":\"2.0\",\"method\":\"message/send\",\"params\":{\"message\":{\"messageId\":\"msg-004\",\"role\":\"user\",\"parts\":[{\"text\":\"Onboard James Chen as DevOps Engineer\"}]}},\"id\":4}'" \
    "James Chen"

# Test 7: Onboard Employee - Emily Rodriguez
run_test "7" "Onboard Emily Rodriguez as UX Designer" \
    "curl -sS --max-time 15 -X POST '$AGENT_URL/' -H 'Content-Type: application/json' -d '{\"jsonrpc\":\"2.0\",\"method\":\"message/send\",\"params\":{\"message\":{\"messageId\":\"msg-005\",\"role\":\"user\",\"parts\":[{\"text\":\"Onboard Emily Rodriguez as UX Designer\"}]}},\"id\":5}'" \
    "Emily Rodriguez"

# Test 8: Verify Employee ID Generation
run_test "8" "Verify Employee ID is Generated" \
    "curl -sS --max-time 15 -X POST '$AGENT_URL/' -H 'Content-Type: application/json' -d '{\"jsonrpc\":\"2.0\",\"method\":\"message/send\",\"params\":{\"message\":{\"messageId\":\"msg-006\",\"role\":\"user\",\"parts\":[{\"text\":\"Onboard Test User as Quality Engineer\"}]}},\"id\":6}'" \
    "E-"

# Test 9: Verify Email Generation
run_test "9" "Verify Email is Generated" \
    "curl -sS --max-time 15 -X POST '$AGENT_URL/' -H 'Content-Type: application/json' -d '{\"jsonrpc\":\"2.0\",\"method\":\"message/send\",\"params\":{\"message\":{\"messageId\":\"msg-007\",\"role\":\"user\",\"parts\":[{\"text\":\"Onboard Alice Johnson as Senior Engineer\"}]}},\"id\":7}'" \
    "@example.com"

# Test 10: Verify JSON Response Format
run_test "10" "Verify JSON Response Contains Required Fields" \
    "curl -sS --max-time 15 -X POST '$AGENT_URL/' -H 'Content-Type: application/json' -d '{\"jsonrpc\":\"2.0\",\"method\":\"message/send\",\"params\":{\"message\":{\"messageId\":\"msg-008\",\"role\":\"user\",\"parts\":[{\"text\":\"Onboard Bob Smith as Backend Developer\"}]}},\"id\":8}'" \
    "employeeId"

echo "========================================"
echo "Test Results Summary"
echo "========================================"
echo "Total Tests: $((PASSED + FAILED))"
echo "Passed: $PASSED"
echo "Failed: $FAILED"
echo ""

if [ $FAILED -eq 0 ]; then
    echo "🎉 All tests passed!"
    exit 0
else
    echo "⚠️  Some tests failed"
    exit 1
fi
