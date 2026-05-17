#!/bin/bash
# Smart Meal — Health monitoring script
# Runs periodic health checks against API and alerts via webhook
# Usage: ./scripts/health_monitor.sh [API_URL] [SLACK_WEBHOOK]

API_URL="${API_URL:-http://localhost:8000}"
ALERT_WEBHOOK="${SLACK_WEBHOOK:-}"

check_endpoint() {
    local name="$1"
    local url="$2"
    local expected_status="${3:-200}"

    status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$url" 2>/dev/null || echo "000")

    if [ "$status" = "$expected_status" ]; then
        echo "✅ $name: OK ($status)"
        return 0
    else
        echo "❌ $name: FAIL (got $status, expected $expected_status)"
        if [ -n "$ALERT_WEBHOOK" ]; then
            curl -s -X POST "$ALERT_WEBHOOK" \
              -H "Content-type: application/json" \
              -d "{\"text\":\"🚨 Smart Meal Alert: $name is DOWN (status: $status)\"}" \
              > /dev/null 2>&1
        fi
        return 1
    fi
}

echo "=== Smart Meal Health Check $(date) ==="
check_endpoint "API Basic"    "$API_URL/health"
check_endpoint "API Readiness" "$API_URL/health/ready"
check_endpoint "AI Health"     "$API_URL/health/ai"
echo "======================================="
