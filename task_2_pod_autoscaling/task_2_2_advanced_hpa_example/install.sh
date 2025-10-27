#!/usr/bin/env bash
BASEDIR=$(dirname "$0")

NAMESPACE_FOR_MONITORING="advanced-hpa-example-monitoring"
NAMESPACE="advanced-hpa-example"  # Придётся разделить эти два namespace, чтобы istio injection врубить только для одного из них = )

echo "=========================================="
echo "=== Установка Prometheus Stack ==="
echo "=========================================="

# Создаем namespace для мониторинга
echo "Создание namespace $(NAMESPACE_FOR_MONITORING)..."
kubectl create namespace $NAMESPACE_FOR_MONITORING 2>/dev/null || echo "Namespace $(NAMESPACE_FOR_MONITORING=) уже существует"

# Добавляем Helm репозиторий Prometheus Community
echo "Добавление Helm репозитория prometheus-community..."
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Устанавливаем kube-prometheus-stack (Prometheus + Grafana + Alertmanager)
echo "Установка kube-prometheus-stack..."
helm upgrade --install prometheus prometheus-community/kube-prometheus-stack \
  --namespace $NAMESPACE_FOR_MONITORING \
  --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false \
  --set prometheus.prometheusSpec.podMonitorSelectorNilUsesHelmValues=false \
  --set prometheus.prometheusSpec.retention=2h \
  --set prometheus.prometheusSpec.storageSpec.volumeClaimTemplate.spec.resources.requests.storage=5Gi \
  --wait --timeout=5m

echo ""
echo "=========================================="
echo "=== Установка Prometheus Adapter ==="
echo "=========================================="

# Устанавливаем Prometheus Adapter для custom metrics
echo "Установка Prometheus Adapter..."
helm upgrade --install prometheus-adapter prometheus-community/prometheus-adapter \
  --namespace $NAMESPACE_FOR_MONITORING \
  --values $BASEDIR/prometheus-adapter-values.yaml \
  --wait --timeout=3m

echo ""
echo "=========================================="
echo "=== Установка приложения ==="
echo "=========================================="

# Создаем namespace для приложения
echo "Создание namespace $(NAMESPACE)..."
kubectl create namespace $NAMESPACE 2>/dev/null || echo "Namespace $(NAMESPACE) уже существует"

# Включаем Istio sidecar injection
echo "Включение Istio sidecar injection..."
kubectl label namespace $NAMESPACE istio-injection=enabled --overwrite

# Применяем манифесты приложения
echo "Применение манифестов приложения..."
kubectl apply -f $BASEDIR/dynamic-hpa-example.yaml -n $NAMESPACE

# Применяем ServiceMonitor для сбора метрик
echo "Применение ServiceMonitor для Istio Ingress Gateway..."
kubectl apply -f $BASEDIR/prometheus-servicemonitor.yaml -n $NAMESPACE

echo ""
echo "=========================================="
echo "Установка завершена!"
echo "=========================================="
echo ""
echo "Компоненты установлены:"
echo "  ✓ Prometheus Stack (namespace: $NAMESPACE_FOR_MONITORING)"
echo "  ✓ Prometheus Adapter (namespace: $NAMESPACE_FOR_MONITORING)"
echo "  ✓ ScaleTestApp с HPA (namespace: $NAMESPACE)"
echo "  ✓ Istio Private IngressGateway (namespace: $NAMESPACE)"
echo "  ✓ ServiceMonitor для метрик (namespace: $NAMESPACE)"
echo ""
