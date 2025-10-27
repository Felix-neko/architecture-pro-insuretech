#!/usr/bin/env bash
BASEDIR=$(dirname "$0")
NAMESPACE="advanced-hpa-example"
NAMESPACE_FOR_MONITORING="advanced-hpa-example-monitoring"

echo "=========================================="
echo "=== Удаление приложения ==="
echo "=========================================="

# Удаляем ServiceMonitor
echo "Удаление ServiceMonitor..."
kubectl delete -f $BASEDIR/prometheus-servicemonitor.yaml -n $NAMESPACE 2>/dev/null || echo "ServiceMonitor уже удален"

# Удаляем манифесты приложения
echo "Удаление манифестов приложения..."
kubectl delete -f $BASEDIR/dynamic-hpa-example.yaml -n $NAMESPACE 2>/dev/null || echo "Манифесты приложения уже удалены"

# Отключаем Istio sidecar injection
echo "Отключение Istio sidecar injection..."
kubectl label namespace $NAMESPACE istio-injection- 2>/dev/null || echo "Label istio-injection уже удален"

echo ""
echo "=========================================="
echo "=== Удаление Prometheus Adapter ==="
echo "=========================================="

# Удаляем Prometheus Adapter
echo "Удаление Prometheus Adapter..."
helm uninstall prometheus-adapter --namespace $NAMESPACE_FOR_MONITORING 2>/dev/null || echo "Prometheus Adapter уже удален"

echo ""
echo "=========================================="
echo "=== Удаление Prometheus Stack ==="
echo "=========================================="

# Удаляем kube-prometheus-stack
echo "Удаление kube-prometheus-stack..."
helm uninstall prometheus --namespace $NAMESPACE_FOR_MONITORING 2>/dev/null || echo "Prometheus Stack уже удален"

echo ""
echo "=========================================="
echo "Удаление завершено!"
echo "=========================================="
echo ""
echo "Компоненты удалены:"
echo "  ✓ ServiceMonitor (namespace: $NAMESPACE)"
echo "  ✓ ScaleTestApp с HPA (namespace: $NAMESPACE)"
echo "  ✓ Istio Private IngressGateway (namespace: $NAMESPACE)"
echo "  ✓ Prometheus Adapter (namespace: $NAMESPACE_FOR_MONITORING)"
echo "  ✓ Prometheus Stack (namespace: $NAMESPACE_FOR_MONITORING)"
echo ""
echo "Namespace'ы сохранены:"
echo "  • $NAMESPACE"
echo "  • $NAMESPACE_FOR_MONITORING"
echo ""
