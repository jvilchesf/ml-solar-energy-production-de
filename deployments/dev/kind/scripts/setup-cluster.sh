#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFESTS_DIR="$SCRIPT_DIR/../manifests"
KIND_CONFIG="$SCRIPT_DIR/../kind-with-portmapping.yaml"

echo "=== ML Solar Energy Production - Tech Stack Setup ==="

# Check prerequisites
echo "Checking prerequisites..."
for cmd in docker kubectl helm kind; do
    if ! command -v $cmd &> /dev/null; then
        echo "ERROR: $cmd is not installed"
        exit 1
    fi
done

# Create Docker network
echo "Creating Docker network..."
docker network create --subnet 172.100.0.0/16 rwml-34fa-network 2>/dev/null || echo "Network already exists"

# Create Kind cluster
echo "Creating Kind cluster..."
KIND_EXPERIMENTAL_DOCKER_NETWORK=rwml-34fa-network kind create cluster --config "$KIND_CONFIG" || echo "Cluster may already exist"

# Wait for cluster to be ready
echo "Waiting for cluster to be ready..."
kubectl wait --for=condition=Ready nodes --all --timeout=300s

# Install ingress-nginx
echo "Installing ingress-nginx..."
kubectl apply -f "$MANIFESTS_DIR/ingress-nginx-all-in-one.yaml"
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=300s || true

# Add Helm repos
echo "Adding Helm repositories..."
helm repo add risingwavelabs https://risingwavelabs.github.io/helm-charts/ --force-update
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

# Install RisingWave
echo "Installing RisingWave..."
helm upgrade --install --create-namespace --wait \
  risingwave risingwavelabs/risingwave \
  --namespace=risingwave \
  -f "$MANIFESTS_DIR/risingwave-values.yaml" \
  --timeout=600s

# Install Strimzi Kafka
echo "Installing Strimzi Kafka operator..."
kubectl create namespace kafka 2>/dev/null || true
kubectl create -f 'https://strimzi.io/install/latest?namespace=kafka' -n kafka 2>/dev/null || true

echo "Waiting for Strimzi operator..."
kubectl wait --for=condition=Ready pods -l name=strimzi-cluster-operator -n kafka --timeout=300s || true

echo "Creating Kafka cluster..."
kubectl apply -f "$MANIFESTS_DIR/kafka-e11b.yaml"

# Install Kafka UI
echo "Installing Kafka UI..."
kubectl apply -f "$MANIFESTS_DIR/kafka-ui-all-in-one.yaml"

# Install Grafana
echo "Installing Grafana..."
helm upgrade --install --create-namespace --wait \
  grafana grafana/grafana \
  --namespace=monitoring \
  -f "$MANIFESTS_DIR/grafana-values.yaml" \
  --timeout=300s

# Create MLflow database
echo "Creating MLflow database..."
kubectl exec -it risingwave-postgresql-0 -n risingwave -- \
  psql -U postgres -c "CREATE USER mlflow WITH ENCRYPTED PASSWORD 'mlflow';" 2>/dev/null || true
kubectl exec -it risingwave-postgresql-0 -n risingwave -- \
  psql -U postgres -c "CREATE DATABASE mlflow WITH ENCODING='UTF8' OWNER=mlflow;" 2>/dev/null || true
kubectl exec -it risingwave-postgresql-0 -n risingwave -- \
  psql -U postgres -c "CREATE DATABASE mlflow_auth WITH ENCODING='UTF8' OWNER=mlflow;" 2>/dev/null || true

# Create MLflow namespace and secret
echo "Setting up MLflow..."
kubectl create namespace mlflow 2>/dev/null || true
kubectl apply -f "$MANIFESTS_DIR/mlflow-minio-secret.yaml"

# Install MLflow
echo "Installing MLflow..."
helm upgrade --install --create-namespace --wait \
  mlflow oci://registry-1.docker.io/bitnamicharts/mlflow \
  --namespace=mlflow \
  -f "$MANIFESTS_DIR/mlflow-values.yaml" \
  --timeout=600s

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Waiting for Kafka cluster to be ready (this may take a few minutes)..."
kubectl wait kafka/kafka-e11b --for=condition=Ready --timeout=600s -n kafka || echo "Kafka still initializing..."

echo ""
echo "=== Access Information ==="
echo "Run: ./scripts/port-forward.sh to start port forwarding"
echo ""
echo "Services will be available at:"
echo "  - Kafka:        localhost:9092"
echo "  - Kafka UI:     localhost:8182"
echo "  - RisingWave:   localhost:4567"
echo "  - MinIO:        localhost:9001"
echo "  - Grafana:      localhost:3000 (admin/admin123456)"
echo "  - MLflow:       localhost:8889 (check secret for credentials)"
echo ""
echo "Get MLflow credentials:"
echo "  kubectl get secrets -n mlflow mlflow-tracking -o json | jq -r '.data.\"admin-password\"' | base64 -D"
echo "  kubectl get secrets -n mlflow mlflow-tracking -o json | jq -r '.data.\"admin-user\"' | base64 -D"
