#!/usr/bin/env bash
BASEDIR=$(dirname "$0")

kubectl create namespace hpa-example

kubectl apply -f $BASEDIR/static-hpa-example.yaml -n hpa-example