#!/usr/bin/env bash

# Скрипт для удаления nginx load balancing примера из Kubernetes

set -e

BASEDIR=$(dirname "$0")
NAMESPACE="rate-limiting-example"
MANIFEST="$BASEDIR/nginx-statefulset.yaml"

echo "========================================="
echo "Uninstalling Nginx Load Balancing Example"
echo "========================================="

# Проверяем существование namespace
if ! kubectl get namespace $NAMESPACE &> /dev/null; then
    echo "Namespace $NAMESPACE does not exist. Nothing to uninstall."
    exit 0
fi

echo "Deleting resources from manifest: $MANIFEST"
kubectl delete -f $MANIFEST -n $NAMESPACE --ignore-not-found=true

echo ""
echo "========================================="
echo "Uninstallation completed!"
echo "========================================="
echo ""
echo "Note: Namespace '$NAMESPACE' still exists."
echo "To delete the namespace, run: ./delete_namespace.sh"
echo ""
