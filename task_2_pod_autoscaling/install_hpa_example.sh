#!/usr/bin/env bash
BASEDIR=$(dirname "$0")

echo "=========================================="
echo "=== Установка Prometheus Stack ==="
echo "=========================================="

# Создаем namespace для мониторинга
echo "Создание namespace monitoring..."
kubectl create namespace monitoring 2>/dev/null || echo "Namespace monitoring уже существует"

# Добавляем Helm репозиторий Prometheus Community
echo "Добавление Helm репозитория prometheus-community..."
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Устанавливаем kube-prometheus-stack (Prometheus + Grafana + Alertmanager)
echo "Установка kube-prometheus-stack..."
helm upgrade --install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
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
  --namespace monitoring \
  --values $BASEDIR/prometheus-adapter-values.yaml \
  --wait --timeout=3m

echo ""
echo "=========================================="
echo "=== Установка приложения ==="
echo "=========================================="

# Создаем namespace для приложения
echo "Создание namespace hpa-example..."
kubectl create namespace hpa-example 2>/dev/null || echo "Namespace hpa-example уже существует"

# Включаем Istio sidecar injection
echo "Включение Istio sidecar injection..."
kubectl label namespace hpa-example istio-injection=enabled --overwrite

# Применяем манифесты приложения
echo "Применение манифестов приложения..."
kubectl apply -f $BASEDIR/dynamic-hpa-example.yaml -n hpa-example

# Применяем ServiceMonitor для сбора метрик
echo "Применение ServiceMonitor для Istio Ingress Gateway..."
kubectl apply -f $BASEDIR/prometheus-servicemonitor.yaml -n hpa-example

echo ""
echo "=========================================="
echo "Установка завершена!"
echo "=========================================="
echo ""
echo "Компоненты установлены:"
echo "  ✓ Prometheus Stack (namespace: monitoring)"
echo "  ✓ Prometheus Adapter (namespace: monitoring)"
echo "  ✓ ScaleTestApp с HPA (namespace: hpa-example)"
echo "  ✓ Istio Private IngressGateway (namespace: hpa-example)"
echo "  ✓ ServiceMonitor для метрик (namespace: hpa-example)"
echo ""
echo "Проверьте статус:"
echo "  kubectl get pods -n monitoring"
echo "  kubectl get pods -n hpa-example"
echo "  kubectl get hpa -n hpa-example"
echo "  kubectl get --raw /apis/custom.metrics.k8s.io/v1beta1"
echo ""
echo "Проверка кастомной метрики RPS:"
echo "  kubectl get --raw '/apis/custom.metrics.k8s.io/v1beta1/namespaces/hpa-example/metrics/scaletestapp_requests_per_second' | jq ."
echo ""
echo "Доступ к приложению:"
echo "  http://\$(minikube ip):30000/"
echo ""
echo "Доступ к Prometheus:"
echo "  kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090"
echo "  http://localhost:9090"
echo ""
echo "Доступ к Grafana:"
echo "  kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80"
echo "  http://localhost:3000 (admin/prom-operator)"
echo ""