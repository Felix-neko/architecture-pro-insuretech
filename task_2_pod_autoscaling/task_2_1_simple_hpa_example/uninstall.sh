BASEDIR=$(dirname "$0")
NAMESPACE="simple-hpa-example"
MANIFEST="$BASEDIR/nginx-statefulset.yaml"

kubectl delete -f $BASEDIR/simple-hpa-example.yaml -n $NAMESPACE