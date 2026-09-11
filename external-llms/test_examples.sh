#!/bin/bash

# Comprehensive test examples for Granite LLM Server
# Tests various types of questions to validate model responses
# Usage: ./test_examples.sh [local|deployed]

MODE=${1:-local}

if [ "$MODE" = "deployed" ]; then
    SERVER_URL="https://granite-llm-server.206hm5j0cjd0.us-south.codeengine.appdomain.cloud"
    AUTH_HEADER="Authorization: Bearer be7867e08313864deedead6556b2461b472fc0d33ec81ef915163d57c4d85e0e"
    TIMEOUT="--max-time 60"
else
    SERVER_URL="http://localhost:8000"
    AUTH_HEADER=""
    TIMEOUT="--max-time 30"
fi

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}=========================================="
echo "  Granite LLM - Example Test Suite"
echo "  Mode: $MODE"
echo "==========================================${NC}"
echo ""

# Helper function to test
test_chat() {
    local test_num=$1
    local title=$2
    local prompt=$3
    local max_tokens=$4
    local temp=${5:-0.3}

    echo -e "${BLUE}Test $test_num: $title${NC}"
    echo "Prompt: \"$prompt\""
    echo "Max tokens: $max_tokens | Temperature: $temp"
    echo ""

    RESPONSE=$(curl -sS $TIMEOUT -X POST "$SERVER_URL/v1/chat/completions" \
        -H "Content-Type: application/json" \
        ${AUTH_HEADER:+-H "$AUTH_HEADER"} \
        -d "{\"messages\":[{\"role\":\"user\",\"content\":\"$prompt\"}],\"max_tokens\":$max_tokens,\"temperature\":$temp}" 2>&1)

    if echo "$RESPONSE" | grep -q "choices"; then
        echo "Response:"
        echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"

        # Extract just the assistant's message
        CONTENT=$(echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['choices'][0]['message']['content'])" 2>/dev/null)
        if [ -n "$CONTENT" ]; then
            echo ""
            echo -e "${GREEN}Answer: $CONTENT${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️  Response: $RESPONSE${NC}"
    fi

    echo ""
    echo "=========================================="
    echo ""
}

# Test 1: Simple arithmetic
test_chat 1 "Simple Math" \
    "What is 7 + 5?" \
    15 \
    0.1

# Test 2: Multiplication
test_chat 2 "Multiplication" \
    "Calculate 12 times 8. Give only the number." \
    10 \
    0.0

# Test 3: Geography
test_chat 3 "Geography Question" \
    "What is the capital of France?" \
    20 \
    0.2

# Test 4: Science
test_chat 4 "Science Question" \
    "What planet is known as the Red Planet?" \
    20 \
    0.2

# Test 5: Definitions
test_chat 5 "Definition" \
    "Define the word 'algorithm' in one sentence." \
    40 \
    0.3

# Test 6: Logic
test_chat 6 "Logic Puzzle" \
    "If all cats are animals, and Fluffy is a cat, what can we conclude about Fluffy?" \
    30 \
    0.2

# Test 7: Comparison
test_chat 7 "Comparison" \
    "Which is larger: 1000 or 999?" \
    15 \
    0.0

# Test 8: List generation
test_chat 8 "List Creation" \
    "Name three primary colors." \
    20 \
    0.3

# Test 9: Yes/No question
test_chat 9 "Yes/No Question" \
    "Is Python a programming language? Answer yes or no." \
    10 \
    0.0

# Test 10: Completion task
test_chat 10 "Sentence Completion" \
    "Complete this sentence: The sun rises in the..." \
    10 \
    0.1

# Test 11: Translation (if model supports)
test_chat 11 "Simple Translation" \
    "What does 'hello' mean in Spanish?" \
    15 \
    0.2

# Test 12: Code understanding
test_chat 12 "Code Understanding" \
    "What does this Python code do: x = 5 + 3" \
    30 \
    0.3

# Test 13: Reasoning
test_chat 13 "Simple Reasoning" \
    "If I have 10 apples and give away 3, how many do I have left?" \
    20 \
    0.1

# Test 14: Pattern recognition
test_chat 14 "Pattern Recognition" \
    "What comes next in this sequence: 2, 4, 6, 8, ?" \
    15 \
    0.1

# Test 15: Creative (higher temperature)
test_chat 15 "Creative Writing (High Temp)" \
    "Write a short sentence about a robot." \
    30 \
    0.8

echo ""
echo -e "${BLUE}=========================================="
echo "  All Tests Complete!"
echo "==========================================${NC}"
echo ""
echo "Notes:"
echo "  - Temperature 0.0-0.2: More deterministic/accurate answers"
echo "  - Temperature 0.3-0.5: Balanced creativity and accuracy"
echo "  - Temperature 0.6-1.0: More creative/varied responses"
echo ""
if [ "$MODE" = "local" ]; then
    echo "To test deployed server, run:"
    echo "  ./test_examples.sh deployed"
else
    echo "To test local server, run:"
    echo "  ./test_examples.sh local"
fi
echo ""
