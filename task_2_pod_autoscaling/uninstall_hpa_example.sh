#!/usr/bin/env bash
set -e
BASEDIR=$(dirname "$0")

echo "=== Удаление namespace ingress-nginx ==="
kubectl delete namespace ingress-nginx --grace-period=0

echo "=== Удаление приложения ==="
kubectl delete namespace hpa-example --grace-period=0

echo "=========================================="
echo "Удаление завершено!"
echo "=========================================="