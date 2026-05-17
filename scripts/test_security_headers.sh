#!/bin/bash
# Smart Meal — Security headers verification script
# Usage: ./scripts/test_security_headers.sh [API_URL] [FRONTEND_URL]
# Requires: curl

API_URL="${1:-http://localhost:8000}"
FRONTEND_URL="${2:-http://localhost:3000}"

echo "🔒 Testing Security Headers..."

# ── API Headers ──────────────────────────────────────────────────────────────
echo -e "\n--- API: $API_URL ---"
API_HEADERS=$(curl -sI "$API_URL/health" 2>/dev/null || echo "")

printf "%s" "$API_HEADERS" | grep -i "X-Frame-Options" > /dev/null && echo "✅ X-Frame-Options: set" || echo "⚠️  X-Frame-Options: missing"
printf "%s" "$API_HEADERS" | grep -i "X-Content-Type-Options" > /dev/null && echo "✅ X-Content-Type-Options: set" || echo "⚠️  X-Content-Type-Options: missing"
printf "%s" "$API_HEADERS" | grep -i "Strict-Transport-Security" > /dev/null && echo "✅ HSTS: set" || echo "⚠️  HSTS: missing (expected if not behind HTTPS proxy)"
printf "%s" "$API_HEADERS" | grep -i "Content-Security-Policy" > /dev/null && echo "✅ CSP: set" || echo "⚠️  CSP: missing"

# ── Frontend Headers ─────────────────────────────────────────────────────────
echo -e "\n--- Frontend: $FRONTEND_URL ---"
FE_HEADERS=$(curl -sI "$FRONTEND_URL" 2>/dev/null || echo "")

if [ -n "$FE_HEADERS" ]; then
    printf "%s" "$FE_HEADERS" | grep -i "X-Frame-Options" > /dev/null && echo "✅ X-Frame-Options: set" || echo "⚠️  X-Frame-Options: missing"
    printf "%s" "$FE_HEADERS" | grep -i "X-Content-Type-Options" > /dev/null && echo "✅ X-Content-Type-Options: set" || echo "⚠️  X-Content-Type-Options: missing"
    printf "%s" "$FE_HEADERS" | grep -i "Strict-Transport-Security" > /dev/null && echo "✅ HSTS: set" || echo "⚠️  HSTS: missing (expected if not behind HTTPS proxy)"
    printf "%s" "$FE_HEADERS" | grep -i "Content-Security-Policy" > /dev/null && echo "✅ CSP: set" || echo "⚠️  CSP: missing"
else
    echo "⚠️  Frontend not reachable at $FRONTEND_URL"
fi

echo -e "\n✅ Security headers test complete"
