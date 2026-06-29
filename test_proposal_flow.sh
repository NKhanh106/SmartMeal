#!/bin/bash
# Test script for proposal confirm/reject flow
# Usage: ./test_proposal.sh [base_url] [token]
# Default: http://localhost:8000

BASE_URL=${1:-http://localhost:8000}
TOKEN=${2:-""}

set -e

echo "=========================================="
echo "Testing Proposal Confirm/Reject Flow"
echo "=========================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_pass() { echo -e "${GREEN}[PASS]${NC} $1"; }
log_fail() { echo -e "${RED}[FAIL]${NC} $1"; }
log_info() { echo -e "${YELLOW}[INFO]${NC} $1"; }

# Check if token provided
if [ -z "$TOKEN" ]; then
    echo "Usage: $0 <base_url> <token>"
    echo "Example: $0 http://localhost:8000 eyJhbGciOiJIUzI1NiIs..."
    exit 1
fi

AUTH_HEADER="Authorization: Bearer $TOKEN"

# ==========================================
# Test 1: Check Redis connection
# ==========================================
echo ""
echo "--- Test 1: Redis Connection ---"

REDIS_KEYS=$(curl -s -X POST "$BASE_URL/api/v1/debug/redis-keys" \
    -H "$AUTH_HEADER" \
    -H "Content-Type: application/json" 2>/dev/null || echo "[]")

if [ "$REDIS_KEYS" != "[]" ] && [ -n "$REDIS_KEYS" ]; then
    log_pass "Redis accessible, keys found: $REDIS_KEYS"
else
    log_info "No proposal keys in Redis (expected if no active proposals)"
fi

# ==========================================
# Test 2: Create a session
# ==========================================
echo ""
echo "--- Test 2: Create Chat Session ---"

SESSION_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/ai/chat/sessions" \
    -H "$AUTH_HEADER" \
    -H "Content-Type: application/json")

SESSION_ID=$(echo $SESSION_RESPONSE | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)

if [ -n "$SESSION_ID" ]; then
    log_pass "Session created: $SESSION_ID"
else
    log_fail "Failed to create session: $SESSION_RESPONSE"
    exit 1
fi

# ==========================================
# Test 3: Simulate proposal in Redis
# ==========================================
echo ""
echo "--- Test 3: Create Test Proposal in Redis ---"

# Get user ID from token
USER_ID=$(curl -s "$BASE_URL/api/v1/auth/me" \
    -H "$AUTH_HEADER" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)

if [ -z "$USER_ID" ]; then
    log_fail "Could not get user ID"
    exit 1
fi

TEST_PROPOSAL_ID="test-proposal-$(date +%s)"

# Create a test proposal JSON
TEST_PROPOSAL='{
    "proposal_id": "'"$TEST_PROPOSAL_ID"'",
    "session_id": "'"$SESSION_ID"'",
    "target": "meal_log",
    "action": "create",
    "confidence": 0.85,
    "data": {
        "meal_type": "lunch",
        "foods": [{"name": "Test Food", "amount": 100, "unit": "g"}],
        "calories": 200,
        "protein": 10,
        "carbs": 20,
        "fat": 5
    },
    "reasoning": "Test proposal for automated testing",
    "created_at": "'"$(date -u +%Y-%m-%dT%H:%M:%SZ)'"
}'

# Store proposal in Redis using debug endpoint or direct Redis
REDIS_CMD="SET smartmeal:proposal:$USER_ID:$TEST_PROPOSAL_ID '$TEST_PROPOSAL' EX 300"

# Try to store via API debug endpoint
STORE_RESULT=$(curl -s -X POST "$BASE_URL/api/v1/debug/redis-set" \
    -H "$AUTH_HEADER" \
    -H "Content-Type: application/json" \
    -d "{\"key\": \"smartmeal:proposal:$USER_ID:$TEST_PROPOSAL_ID\", \"value\": $TEST_PROPOSAL, \"ttl\": 300}" 2>/dev/null || echo "FAILED")

if echo "$STORE_RESULT" | grep -q "success"; then
    log_pass "Test proposal created in Redis"
else
    log_info "Debug endpoint not available, testing with existing proposals"
    echo "SKIPPING manual proposal creation"
fi

# ==========================================
# Test 4: Try to confirm non-existent proposal
# ==========================================
echo ""
echo "--- Test 4: Confirm Non-existent Proposal ---"

CONFIRM_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
    "$BASE_URL/api/v1/ai/chat/sessions/$SESSION_ID/proposals/nonexistent-123/confirm" \
    -H "$AUTH_HEADER" \
    -H "Content-Type: application/json")

HTTP_CODE=$(echo "$CONFIRM_RESPONSE" | tail -1)
RESPONSE_BODY=$(echo "$CONFIRM_RESPONSE" | head -n -1)

if [ "$HTTP_CODE" = "404" ]; then
    log_pass "Correctly returns 404 for non-existent proposal"
else
    log_fail "Expected 404, got $HTTP_CODE: $RESPONSE_BODY"
fi

# ==========================================
# Test 5: Try to confirm with wrong session
# ==========================================
echo ""
echo "--- Test 5: Confirm with Wrong Session ID ---"

# Create another session
SESSION2_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/ai/chat/sessions" \
    -H "$AUTH_HEADER" \
    -H "Content-Type: application/json")
SESSION2_ID=$(echo $SESSION2_RESPONSE | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)

if [ -n "$SESSION2_ID" ]; then
    log_pass "Second session created: $SESSION2_ID"

    # Try to confirm proposal with wrong session
    WRONG_SESSION_CONFIRM=$(curl -s -w "\n%{http_code}" -X POST \
        "$BASE_URL/api/v1/ai/chat/sessions/$SESSION2_ID/proposals/$TEST_PROPOSAL_ID/confirm" \
        -H "$AUTH_HEADER" \
        -H "Content-Type: application/json")

    HTTP_CODE=$(echo "$WRONG_SESSION_CONFIRM" | tail -1)

    if [ "$HTTP_CODE" = "403" ]; then
        log_pass "Correctly returns 403 for session mismatch"
    else
        log_fail "Expected 403, got $HTTP_CODE"
    fi
fi

# ==========================================
# Test 6: Reject proposal
# ==========================================
echo ""
echo "--- Test 6: Reject Proposal ---"

REJECT_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
    "$BASE_URL/api/v1/ai/chat/sessions/$SESSION_ID/proposals/$TEST_PROPOSAL_ID/reject" \
    -H "$AUTH_HEADER" \
    -H "Content-Type: application/json")

HTTP_CODE=$(echo "$REJECT_RESPONSE" | tail -1)

if [ "$HTTP_CODE" = "200" ]; then
    log_pass "Proposal rejected successfully"
else
    log_fail "Reject failed with $HTTP_CODE: $(echo $REJECT_RESPONSE | head -n -1)"
fi

# ==========================================
# Test 7: Try to confirm rejected proposal
# ==========================================
echo ""
echo "--- Test 7: Confirm Rejected Proposal (should fail) ---"

CONFIRM_AFTER_REJECT=$(curl -s -w "\n%{http_code}" -X POST \
    "$BASE_URL/api/v1/ai/chat/sessions/$SESSION_ID/proposals/$TEST_PROPOSAL_ID/confirm" \
    -H "$AUTH_HEADER" \
    -H "Content-Type: application/json")

HTTP_CODE=$(echo "$CONFIRM_AFTER_REJECT" | tail -1)

if [ "$HTTP_CODE" = "404" ]; then
    log_pass "Correctly returns 404 after reject (proposal already deleted)"
else
    log_fail "Expected 404 after reject, got $HTTP_CODE"
fi

# ==========================================
# Summary
# ==========================================
echo ""
echo "=========================================="
echo "Test Complete"
echo "=========================================="
echo ""
echo "To manually test the full flow:"
echo "1. Open browser to $BASE_URL"
echo "2. Login with your account"
echo "3. Send a chat message about food"
echo "4. Wait for proposal card to appear"
echo "5. Click 'Lưu lại' or 'Bỏ qua'"
echo "6. Check browser console for any errors"
echo ""
echo "Debug: Check Redis keys with:"
echo "  docker compose exec redis redis-cli KEYS 'smartmeal:proposal:*'"
