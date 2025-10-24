#!/usr/bin/env bash
set -e
BASEDIR=$(dirname "$0")

echo "=== Удаление приложения и Istio IngressGateway ==="
kubectl delete namespace hpa-example --grace-period=0

echo "=========================================="
echo "Удаление завершено!"
echo "=========================================="