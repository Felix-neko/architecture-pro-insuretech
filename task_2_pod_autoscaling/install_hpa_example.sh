#!/usr/bin/env bash
BASEDIR=$(dirname "$0")

echo "=== Создание namespace hpa-example ==="
kubectl create namespace hpa-example

echo "=== Включение Istio sidecar injection ==="
kubectl label namespace hpa-example istio-injection=enabled --overwrite

echo "=== Применение манифеста ==="
kubectl apply -f $BASEDIR/dynamic-hpa-example.yaml -n hpa-example

echo "=========================================="
echo "Установка завершена!"
echo "=========================================="
echo ""
echo "Проверьте статус:"
echo "  ./test_istio_setup.sh"
echo ""
echo "Доступ к приложению:"
echo "  http://\$(minikube ip):30000/"
echo ""