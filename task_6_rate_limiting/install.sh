#!/usr/bin/env bash

# Скрипт для установки nginx load balancing примера в Kubernetes

set -e

BASEDIR=$(dirname "$0")
NAMESPACE="rate-limiting-example"
MANIFEST="$BASEDIR/nginx-statefulset.yaml"

echo "========================================="
echo "Installing Nginx Load Balancing Example"
echo "========================================="

# Создаём namespace если его нет
echo "Creating namespace: $NAMESPACE"
kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -

# Применяем манифест
echo "Applying manifest: $MANIFEST"
kubectl apply -f $MANIFEST -n $NAMESPACE

# Ждём готовности StatefulSet
echo "Waiting for StatefulSet nginx-backend to be ready..."
kubectl rollout status statefulset/nginx-backend -n $NAMESPACE --timeout=120s

# Ждём готовности Deployment
echo "Waiting for Deployment nginx-lb to be ready..."
kubectl rollout status deployment/nginx-lb -n $NAMESPACE --timeout=120s

echo ""
echo "========================================="
echo "Installation completed successfully!"
echo "========================================="
echo ""
echo "Resources created:"
kubectl get all -n $NAMESPACE

echo ""
echo "========================================="
echo "Access Information:"
echo "========================================="
echo "NodePort Service: http://localhost:30002"
echo "Load Balancer Status: http://localhost:30002/status"
echo ""
echo "Test with: curl http://localhost:30002"
echo "Multiple requests to see round-robin:"
echo "  for i in {1..6}; do curl http://localhost:30002; done"
echo ""
