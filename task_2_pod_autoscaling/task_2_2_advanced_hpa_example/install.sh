#!/usr/bin/env bash
BASEDIR=$(dirname "$0")

NAMESPACE_FOR_MONITORING="advanced-hpa-example-monitoring"
NAMESPACE="advanced-hpa-example"  # Придётся разделить эти два namespace, чтобы istio injection врубить только для одного из них = )

echo "=========================================="
echo "=== Установка Prometheus Stack ==="
echo "=========================================="

# Создаем namespace для мониторинга
echo "Создание namespace ${NAMESPACE_FOR_MONITORING}..."
kubectl create namespace $NAMESPACE_FOR_MONITORING 2>/dev/null || echo "Namespace ${NAMESPACE_FOR_MONITORING} уже существует"

echo "Создание namespace ${NAMESPACE}..."
kubectl create namespace $NAMESPACE 2>/dev/null || echo "Namespace ${NAMESPACE} уже существует"

echo "Включение Istio sidecar injection..."
kubectl label namespace $NAMESPACE istio-injection=enabled --overwrite

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
  --set grafana.sidecar.dashboards.enabled=true \
  --set grafana.sidecar.dashboards.label=grafana_dashboard \
  --wait --timeout=5m

echo "Применение monitoring-bundle (ConfigMap, NodePort сервисы, ServiceMonitor)..."
kubectl apply -f $BASEDIR/monitoring-bundle.yaml

PROMETHEUS_ADAPTER_VALUES_FILE=$(mktemp)
kubectl get configmap prometheus-adapter-values \
  --namespace $NAMESPACE_FOR_MONITORING \
  -o jsonpath='{.data.values\.yaml}' > "$PROMETHEUS_ADAPTER_VALUES_FILE"

echo ""
echo "=========================================="
echo "=== Установка Prometheus Adapter ==="
echo "=========================================="

# Устанавливаем Prometheus Adapter для custom metrics
echo "Установка Prometheus Adapter..."
helm upgrade --install prometheus-adapter prometheus-community/prometheus-adapter \
  --namespace $NAMESPACE_FOR_MONITORING \
  --values "$PROMETHEUS_ADAPTER_VALUES_FILE" \
  --wait --timeout=3m

rm -f "$PROMETHEUS_ADAPTER_VALUES_FILE"

echo ""
echo "=========================================="
echo "=== Установка приложения ==="
echo "=========================================="

# Применяем манифесты приложения
echo "Применение манифестов приложения..."
kubectl apply -f $BASEDIR/dynamic-hpa-example.yaml -n $NAMESPACE

echo ""
echo "=========================================="
echo "Ожидание загрузки дашборда в Grafana..."
echo "=========================================="
sleep 10

MINIKUBE_IP=$(minikube ip 2>/dev/null || echo "192.168.49.2")

echo ""
echo "=========================================="
echo "NodePort сервисы доступны:"
echo "  • Prometheus Web UI: http://${MINIKUBE_IP}:30003"
echo "  • Grafana Web UI:    http://${MINIKUBE_IP}:30004"
echo ""
echo "Grafana credentials:"
echo "  • Логин: admin"
echo "  • Пароль: prom-operator"
echo ""
echo "Istio Gateway Dashboard:"
echo "  • Dashboards → Browse → Private Istio Gateway - RPS Monitoring"
echo "  • Или прямая ссылка: http://${MINIKUBE_IP}:30004/d/private-istio-gateway-rps"

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
echo "  ✓ ServiceMonitor + NodePort сервисы + Grafana Dashboard"
echo ""
