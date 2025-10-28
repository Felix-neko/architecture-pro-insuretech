#!/usr/bin/env bash
set -e
BASEDIR=$(dirname "$0")

echo "=========================================="
echo "=== Удаление приложения ==="
echo "=========================================="
echo "Удаление namespace hpa-example..."
kubectl delete namespace hpa-example --grace-period=0 --ignore-not-found=true

echo ""
echo "=========================================="
echo "=== Удаление Prometheus Adapter ==="
echo "=========================================="
echo "Удаление Prometheus Adapter..."
helm uninstall prometheus-adapter -n monitoring --ignore-not-found 2>/dev/null || echo "Prometheus Adapter не установлен"

echo ""
echo "=========================================="
echo "=== Удаление Prometheus Stack ==="
echo "=========================================="
echo "Удаление kube-prometheus-stack..."
helm uninstall prometheus -n monitoring --ignore-not-found 2>/dev/null || echo "Prometheus Stack не установлен"

echo ""
echo "Удаление namespace monitoring..."
kubectl delete namespace monitoring --grace-period=0 --ignore-not-found=true

echo ""
echo "=========================================="
echo "Удаление завершено!"
echo "=========================================="
echo ""
echo "Удалены компоненты:"
echo "  ✓ ScaleTestApp и Istio IngressGateway"
echo "  ✓ Prometheus Adapter"
echo "  ✓ Prometheus Stack (Prometheus, Grafana, Alertmanager)"
echo "  ✓ Namespaces: hpa-example, monitoring"
echo ""