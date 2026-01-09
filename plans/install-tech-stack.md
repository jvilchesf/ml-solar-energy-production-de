# Plan: Install Tech Stack

## Overview

Install the complete Kubernetes-based tech stack for the ML Solar Energy Production project. This includes setting up a local Kind cluster with all required infrastructure: Kafka for streaming, RisingWave for stream processing, MinIO for object storage, MLflow for ML tracking, and Grafana for monitoring.

### Key Requirements
- Docker must be running
- `kubectl`, `helm`, `kind`, and `kcat` CLI tools must be installed
- Sufficient system resources (recommended: 16GB RAM, 4 CPUs)

### Success Criteria
- Kind cluster running with all nodes ready
- Kafka accessible at `localhost:9092`
- RisingWave accessible at `localhost:4567`
- MLflow UI accessible at `localhost:8889`
- Grafana accessible at `localhost:3000`
- MinIO console accessible at `localhost:9001`

---

## Relevant Files

| File | Action | Description |
|------|--------|-------------|
| `deployments/dev/kind/kind-with-portmapping.yaml` | Create | Kind cluster config with port mappings |
| `deployments/dev/kind/manifests/risingwave-values.yaml` | Create | RisingWave Helm values |
| `deployments/dev/kind/manifests/grafana-values.yaml` | Create | Grafana Helm values |
| `deployments/dev/kind/manifests/kafka-e11b.yaml` | Create | Strimzi Kafka cluster manifest |
| `deployments/dev/kind/manifests/kafka-ui-all-in-one.yaml` | Create | Kafka UI deployment |
| `deployments/dev/kind/manifests/mlflow-values.yaml` | Create | MLflow Helm values |
| `deployments/dev/kind/manifests/mlflow-minio-secret.yaml` | Create | MLflow MinIO credentials secret |
| `deployments/dev/kind/manifests/ingress-nginx-all-in-one.yaml` | Create | Ingress NGINX manifest |
| `deployments/dev/kind/scripts/setup-cluster.sh` | Create | Main setup script |
| `deployments/dev/kind/scripts/teardown-cluster.sh` | Create | Cleanup script |
| `deployments/dev/kind/scripts/port-forward.sh` | Create | Port forwarding helper script |

---

## Dependencies

### CLI Tools Required
- `docker` - Container runtime
- `kind` - Kubernetes in Docker
- `kubectl` - Kubernetes CLI
- `helm` - Kubernetes package manager
- `kcat` - Kafka CLI tool (for testing)
- `jq` - JSON processor
- `psql` - PostgreSQL client (for RisingWave testing)

### Helm Repositories
- `risingwavelabs` - https://risingwavelabs.github.io/helm-charts/
- `grafana` - https://grafana.github.io/helm-charts
- `bitnami/mlflow` - oci://registry-1.docker.io/bitnamicharts/mlflow

---

## Step by Step Tasks

### Task 1: Create Directory Structure

**Action**: Create the deployments directory structure

```bash
mkdir -p deployments/dev/kind/manifests
mkdir -p deployments/dev/kind/scripts
```

---

### Task 2: Create Kind Cluster Configuration

**File**: `deployments/dev/kind/kind-with-portmapping.yaml` (create new)

**Action**: Create Kind cluster config with port mappings for all services

**Details**:
- Configure 1 control-plane node and 3 worker nodes
- Map port 9092 for Kafka
- Map port 80/443 for ingress
- Map port 9001 for MinIO console
- Configure extra mounts if needed

**Content**:
```yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: rwml-34fa
nodes:
  - role: control-plane
    kubeadmConfigPatches:
      - |
        kind: InitConfiguration
        nodeRegistration:
          kubeletExtraArgs:
            node-labels: "ingress-ready=true"
    extraPortMappings:
      - containerPort: 80
        hostPort: 80
        protocol: TCP
      - containerPort: 443
        hostPort: 443
        protocol: TCP
      - containerPort: 9092
        hostPort: 9092
        protocol: TCP
      - containerPort: 9001
        hostPort: 9001
        protocol: TCP
  - role: worker
  - role: worker
  - role: worker
```

---

### Task 3: Create Ingress NGINX Manifest

**File**: `deployments/dev/kind/manifests/ingress-nginx-all-in-one.yaml` (create new)

**Action**: Download and save the Kind-specific ingress-nginx manifest

**Details**:
- Use the official Kind ingress-nginx deployment
- This enables ingress routing within the Kind cluster

**Command to fetch**:
```bash
curl -o deployments/dev/kind/manifests/ingress-nginx-all-in-one.yaml \
  https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml
```

---

### Task 4: Create RisingWave Helm Values

**File**: `deployments/dev/kind/manifests/risingwave-values.yaml` (create new)

**Action**: Configure RisingWave with MinIO for object storage

**Details**:
- Enable standalone mode for local development
- Configure MinIO as the state backend
- Set resource limits appropriate for local development
- Enable PostgreSQL for metadata storage

**Content**:
```yaml
standalone:
  enabled: true

compactMode:
  enabled: true

stateStore:
  minio:
    enabled: true

metaStore:
  postgresql:
    enabled: true

minio:
  enabled: true
  auth:
    rootUser: admin
    rootPassword: admin123456
  service:
    type: ClusterIP
    ports:
      api: 9000
      console: 9001

postgresql:
  enabled: true
  auth:
    username: postgres
    password: postgres
    database: risingwave
```

---

### Task 5: Create Strimzi Kafka Cluster Manifest

**File**: `deployments/dev/kind/manifests/kafka-e11b.yaml` (create new)

**Action**: Define Kafka cluster with external access via NodePort

**Details**:
- Single broker for local development
- Configure external listener on port 9092
- Enable auto topic creation
- Set appropriate resource limits

**Content**:
```yaml
apiVersion: kafka.strimzi.io/v1beta2
kind: Kafka
metadata:
  name: kafka-e11b
  namespace: kafka
spec:
  kafka:
    version: 3.7.0
    replicas: 1
    listeners:
      - name: plain
        port: 9092
        type: internal
        tls: false
      - name: external
        port: 9094
        type: nodeport
        tls: false
        configuration:
          bootstrap:
            nodePort: 9092
    config:
      offsets.topic.replication.factor: 1
      transaction.state.log.replication.factor: 1
      transaction.state.log.min.isr: 1
      default.replication.factor: 1
      min.insync.replicas: 1
      auto.create.topics.enable: true
    storage:
      type: jbod
      volumes:
        - id: 0
          type: persistent-claim
          size: 10Gi
          deleteClaim: false
    template:
      pod:
        metadata:
          labels:
            app: kafka
  zookeeper:
    replicas: 1
    storage:
      type: persistent-claim
      size: 5Gi
      deleteClaim: false
  entityOperator:
    topicOperator: {}
    userOperator: {}
```

---

### Task 6: Create Kafka UI Manifest

**File**: `deployments/dev/kind/manifests/kafka-ui-all-in-one.yaml` (create new)

**Action**: Deploy Kafka UI for cluster management

**Details**:
- Connect to the Strimzi Kafka cluster
- Expose via ClusterIP service (use port-forward for access)

**Content**:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: kafka-ui
  namespace: kafka
  labels:
    app: kafka-ui
spec:
  replicas: 1
  selector:
    matchLabels:
      app: kafka-ui
  template:
    metadata:
      labels:
        app: kafka-ui
    spec:
      containers:
        - name: kafka-ui
          image: provectuslabs/kafka-ui:latest
          ports:
            - containerPort: 8080
          env:
            - name: KAFKA_CLUSTERS_0_NAME
              value: kafka-e11b
            - name: KAFKA_CLUSTERS_0_BOOTSTRAPSERVERS
              value: kafka-e11b-kafka-bootstrap:9092
---
apiVersion: v1
kind: Service
metadata:
  name: kafka-ui
  namespace: kafka
spec:
  type: ClusterIP
  ports:
    - port: 8080
      targetPort: 8080
  selector:
    app: kafka-ui
```

---

### Task 7: Create Grafana Helm Values

**File**: `deployments/dev/kind/manifests/grafana-values.yaml` (create new)

**Action**: Configure Grafana with default datasources

**Details**:
- Set admin password
- Pre-configure RisingWave as PostgreSQL datasource
- Enable persistence

**Content**:
```yaml
adminUser: admin
adminPassword: admin123456

persistence:
  enabled: true
  size: 1Gi

datasources:
  datasources.yaml:
    apiVersion: 1
    datasources:
      - name: RisingWave
        type: postgres
        url: risingwave.risingwave.svc.cluster.local:4567
        database: dev
        user: root
        secureJsonData:
          password: ""
        jsonData:
          sslmode: disable
          maxOpenConns: 10
          maxIdleConns: 10
          connMaxLifetime: 14400

service:
  type: ClusterIP
  port: 3000
```

---

### Task 8: Create MLflow MinIO Secret Template

**File**: `deployments/dev/kind/manifests/mlflow-minio-secret.yaml` (create new)

**Action**: Create Kubernetes secret for MLflow to access MinIO

**Details**:
- Placeholder values that must be updated after MinIO access key creation
- Used by MLflow for artifact storage

**Content**:
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: mlflow-minio-secret
  namespace: mlflow
type: Opaque
stringData:
  AccessKeyID: REPLACE_WITH_MINIO_ACCESS_KEY
  SecretKey: REPLACE_WITH_MINIO_SECRET_KEY
```

---

### Task 9: Create MLflow Helm Values

**File**: `deployments/dev/kind/manifests/mlflow-values.yaml` (create new)

**Action**: Configure MLflow with RisingWave PostgreSQL and MinIO

**Details**:
- Use RisingWave's PostgreSQL for backend store
- Use MinIO for artifact storage
- Enable tracking server with authentication

**Content**:
```yaml
tracking:
  enabled: true
  auth:
    enabled: true
  service:
    type: ClusterIP
    port: 80

  extraEnvVars:
    - name: MLFLOW_S3_ENDPOINT_URL
      value: "http://risingwave-minio.risingwave.svc.cluster.local:9000"
    - name: AWS_ACCESS_KEY_ID
      valueFrom:
        secretKeyRef:
          name: mlflow-minio-secret
          key: AccessKeyID
    - name: AWS_SECRET_ACCESS_KEY
      valueFrom:
        secretKeyRef:
          name: mlflow-minio-secret
          key: SecretKey

  backendStore:
    postgresql:
      enabled: true
      host: risingwave-postgresql.risingwave.svc.cluster.local
      port: 5432
      database: mlflow
      user: mlflow
      password: mlflow

  artifactRoot: "s3://mlflow-artifacts"

run:
  enabled: false

postgresql:
  enabled: false

minio:
  enabled: false

externalS3:
  host: risingwave-minio.risingwave.svc.cluster.local
  port: 9000
  useCredentialsInSecret: true
  accessKeyIDSecretKey: AccessKeyID
  secretAccessKeySecretKey: SecretKey
  existingSecret: mlflow-minio-secret
  bucket: mlflow-artifacts
  protocol: http
```

---

### Task 10: Create Main Setup Script

**File**: `deployments/dev/kind/scripts/setup-cluster.sh` (create new)

**Action**: Create comprehensive setup script that installs all components

**Details**:
- Check prerequisites
- Create Docker network
- Create Kind cluster
- Install all Helm charts in order
- Wait for components to be ready
- Create MLflow database in PostgreSQL

**Content**:
```bash
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
```

---

### Task 11: Create Port Forward Script

**File**: `deployments/dev/kind/scripts/port-forward.sh` (create new)

**Action**: Create helper script for port forwarding all services

**Content**:
```bash
#!/bin/bash

echo "Starting port forwards..."
echo "Press Ctrl+C to stop all port forwards"
echo ""

# Kill any existing port-forwards
pkill -f "kubectl.*port-forward" 2>/dev/null || true

# Start port forwards in background
kubectl -n risingwave port-forward svc/risingwave 4567:4567 &
kubectl -n risingwave port-forward svc/risingwave-minio 9001:9001 &
kubectl -n kafka port-forward svc/kafka-ui 8182:8080 &
kubectl -n monitoring port-forward svc/grafana 3000:3000 &
kubectl -n mlflow port-forward svc/mlflow-tracking 8889:80 &

echo "Port forwards started:"
echo "  - RisingWave:   http://localhost:4567"
echo "  - MinIO:        http://localhost:9001"
echo "  - Kafka UI:     http://localhost:8182"
echo "  - Grafana:      http://localhost:3000"
echo "  - MLflow:       http://localhost:8889"
echo ""

# Wait for Ctrl+C
wait
```

---

### Task 12: Create Teardown Script

**File**: `deployments/dev/kind/scripts/teardown-cluster.sh` (create new)

**Action**: Create cleanup script to remove all resources

**Content**:
```bash
#!/bin/bash
set -euo pipefail

echo "=== Tearing down ML Solar Energy Production cluster ==="

# Delete Kind cluster
echo "Deleting Kind cluster..."
kind delete cluster --name rwml-34fa

# Remove Docker network
echo "Removing Docker network..."
docker network rm rwml-34fa-network 2>/dev/null || echo "Network already removed"

echo ""
echo "=== Teardown Complete ==="
```

---

### Task 13: Make Scripts Executable

**Action**: Set executable permissions on all scripts

```bash
chmod +x deployments/dev/kind/scripts/*.sh
```

---

### Task 14: Download Ingress NGINX Manifest

**Action**: Fetch the ingress-nginx manifest for Kind

```bash
curl -o deployments/dev/kind/manifests/ingress-nginx-all-in-one.yaml \
  https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml
```

---

## Testing Strategy

### Verification Tests

1. **Cluster Health**
   ```bash
   kubectl get nodes
   kubectl get pods -A
   ```

2. **Kafka Connectivity**
   ```bash
   # Create a test topic
   kubectl exec -it kafka-e11b-kafka-0 -n kafka -c kafka -- \
     bin/kafka-topics.sh --bootstrap-server localhost:9092 --topic test-topic --create --partitions 1 --replication-factor 1

   # Produce a message (from local machine)
   echo '{"test": "message"}' | kcat -b localhost:9092 -P -t test-topic

   # Consume the message
   kcat -b localhost:9092 -C -t test-topic -e
   ```

3. **RisingWave Connectivity**
   ```bash
   psql -h localhost -p 4567 -d dev -U root -c "SELECT 1;"
   ```

4. **MLflow Connectivity**
   ```bash
   # Get credentials
   MLFLOW_USER=$(kubectl get secrets -n mlflow mlflow-tracking -o jsonpath='{.data.admin-user}' | base64 -D)
   MLFLOW_PASS=$(kubectl get secrets -n mlflow mlflow-tracking -o jsonpath='{.data.admin-password}' | base64 -D)

   # Test API
   curl -u "$MLFLOW_USER:$MLFLOW_PASS" http://localhost:8889/api/2.0/mlflow/experiments/list
   ```

---

## Validation Commands

```bash
# Check all pods are running
kubectl get pods -A | grep -v Running | grep -v Completed

# Check Kind cluster
kind get clusters

# Check Helm releases
helm list -A

# Verify Kafka
kcat -b localhost:9092 -L

# Verify RisingWave
psql -h localhost -p 4567 -d dev -U root -c "SELECT version();"

# Check service endpoints
kubectl get svc -A
```

---

## Integration Notes

### Post-Installation Steps

1. **MinIO Access Key for MLflow**:
   - Access MinIO console at `http://localhost:9001` (admin/admin123456)
   - Create access key at Identity > Access Keys
   - Update `mlflow-minio-secret.yaml` with actual credentials
   - Reapply the secret and restart MLflow

2. **Create MLflow Bucket**:
   - In MinIO console, create bucket named `mlflow-artifacts`

3. **Grafana Dashboards**:
   - Import dashboards for Kafka and RisingWave monitoring

### Port Reference

| Service | Internal Port | External Port | Access |
|---------|---------------|---------------|--------|
| Kafka | 9092 | 9092 | Direct via NodePort |
| RisingWave | 4567 | 4567 | Port-forward |
| MinIO Console | 9001 | 9001 | Port-forward |
| Grafana | 3000 | 3000 | Port-forward |
| MLflow | 80 | 8889 | Port-forward |
| Kafka UI | 8080 | 8182 | Port-forward |

### Troubleshooting

- **Pods stuck in Pending**: Check node resources with `kubectl describe node`
- **Kafka not accessible**: Verify NodePort mapping in Kind config
- **MLflow can't connect to MinIO**: Ensure MinIO secret has valid credentials
- **RisingWave connection refused**: Wait for all pods to be ready, check logs

---

## Confirmation

- Feature name: `install-tech-stack`
- Plan saved to: `plans/install-tech-stack.md`
- All tasks are explicit with file paths
- Validation commands are exact
- Another agent could execute this without context

**Next step**: Run `/execute plans/install-tech-stack.md` to implement this feature
