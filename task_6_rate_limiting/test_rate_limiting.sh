#!/usr/bin/env bash

# Скрипт для тестирования rate limiting

set -e

MINIKUBE_IP=$(minikube ip)
ENDPOINT="http://${MINIKUBE_IP}:30002"
NAMESPACE="rate-limiting-example"
CURL_TIMEOUT=5

echo "========================================="
echo "Testing Nginx Rate Limiting"
echo "========================================="
echo ""

# Проверяем что сервис запущен
echo "1. Checking if service is running..."
echo "   Endpoint: $ENDPOINT"
if ! curl -s -o /dev/null -w "%{http_code}" --max-time $CURL_TIMEOUT "$ENDPOINT/health" 2>/dev/null | grep -q "200"; then
    echo "ERROR: Service is not running on $ENDPOINT"
    echo "Please run ./install.sh first"
    exit 1
fi
echo "✓ Service is running"
echo ""

# Проверяем статус
echo "2. Checking load balancer status..."
curl -s --max-time $CURL_TIMEOUT "$ENDPOINT/status" 2>/dev/null || echo "Failed to get status"
echo ""
echo ""

# Тест 1: Round-robin балансировка
echo "========================================="
echo "Test 1: Round-Robin Load Balancing"
echo "========================================="
echo "Sending 6 requests to see different backend pods..."
echo ""
for i in {1..6}; do
    echo "Request $i:"
    curl -s --max-time $CURL_TIMEOUT "$ENDPOINT" 2>/dev/null | grep -o "Hello from pod: [^<]*" || echo "  Failed to get response"
done
echo ""
echo "✓ You should see requests distributed across 3 pods"
echo ""

# Тест 2: Ожидание восстановления burst
echo "========================================="
echo "Test 2: Waiting for Burst Recovery"
echo "========================================="
echo "Rate: 20 req/min = 1 token every 3 seconds"
echo "Burst: 20 tokens"
echo "Waiting 60 seconds for full burst recovery..."
echo ""
for i in {1..12}; do
    echo -n "."
    sleep 5
done
echo ""
echo "✓ Burst should be fully recovered now"
echo ""

# Тест 3: Rate limiting (быстрые запросы - превышение лимита)
echo "========================================="
echo "Test 3: Rate Limiting (Fast Requests)"
echo "========================================="
echo "Sending 25 requests rapidly (should trigger rate limiting)..."
echo ""
success_count=0
rate_limited_count=0
error_count=0

# Временно отключаем set -e для этого теста
set +e

for i in {1..25}; do
    http_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time $CURL_TIMEOUT "$ENDPOINT" 2>/dev/null)
    curl_exit=$?
    
    if [ $curl_exit -ne 0 ]; then
        # curl завершился с ошибкой
        http_code="000"
    fi
    
    if [ "$http_code" = "200" ]; then
        ((success_count++))
        echo -n "."
    elif [ "$http_code" = "429" ]; then
        ((rate_limited_count++))
        echo -n "X"
    else
        ((error_count++))
        echo -n "?"
    fi
    sleep 0.05
done

# Включаем обратно set -e
set -e

echo ""
echo ""
echo "Results:"
echo "  Success (200): $success_count"
echo "  Rate Limited (429): $rate_limited_count"
if [ $error_count -gt 0 ]; then
    echo "  Errors: $error_count"
fi
echo ""
echo "Expected behavior:"
echo "  - First ~20 requests: HTTP 200 (burst)"
echo "  - Remaining requests: HTTP 429 (rate limited)"
echo ""
if [ $rate_limited_count -gt 0 ]; then
    echo "✓ Rate limiting is working! Got $rate_limited_count 429 responses"
    echo "  Burst size: ~$success_count tokens"
else
    echo "⚠ No rate limiting detected (unexpected)"
fi
echo ""

# Тест 4: Проверка заголовков
echo "========================================="
echo "Test 4: Response Headers"
echo "========================================="
echo "Checking response headers..."
echo ""
curl -I --max-time $CURL_TIMEOUT "$ENDPOINT" 2>/dev/null | grep -E "(HTTP|X-Backend|X-RateLimit)" || echo "Failed to get headers"
echo ""
echo "✓ Headers show backend server and rate limit info"
echo ""

# Тест 5: Логи nginx
echo "========================================="
echo "Test 5: Nginx Logs (Rate Limiting Events)"
echo "========================================="
echo "Checking nginx logs for rate limiting warnings..."
echo ""
kubectl logs -n $NAMESPACE deployment/nginx-lb --tail=20 2>/dev/null | grep -i "limiting" || echo "No rate limiting events in recent logs"
echo ""

echo "========================================="
echo "Testing Complete!"
echo "========================================="
echo ""
echo "Summary:"
echo "  - Rate limit: 20 requests/minute per IP"
echo "  - Burst: 20 additional requests"
echo "  - Algorithm: Leaky Bucket"
echo "  - Status code on limit: 429 Too Many Requests"
echo "  - Burst recovery: 1 token every 3 seconds (60s for full recovery)"
echo ""
echo "Note: Wait 60+ seconds between tests for full burst recovery!"
echo ""
