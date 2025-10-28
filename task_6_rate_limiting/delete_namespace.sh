#!/usr/bin/env bash

# Скрипт для удаления namespace rate-limiting-example

set -e

BASEDIR=$(dirname "$0")
NAMESPACE="rate-limiting-example"

echo "========================================="
echo "Deleting Namespace: $NAMESPACE"
echo "========================================="

# Проверяем существование namespace
if ! kubectl get namespace $NAMESPACE &> /dev/null; then
    echo "Namespace $NAMESPACE does not exist. Nothing to delete."
    exit 0
fi

# Показываем ресурсы в namespace перед удалением
echo "Resources in namespace $NAMESPACE:"
kubectl get all -n $NAMESPACE 2>/dev/null || echo "No resources found"

echo ""
read -p "Are you sure you want to delete namespace '$NAMESPACE' and all its resources? (yes/no): " confirmation

if [ "$confirmation" != "yes" ]; then
    echo "Deletion cancelled."
    exit 0
fi

echo "Deleting namespace: $NAMESPACE"
kubectl delete namespace $NAMESPACE

echo ""
echo "========================================="
echo "Namespace deleted successfully!"
echo "========================================="
echo ""
