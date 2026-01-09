#!/bin/bash

echo "Starting port forwards..."
echo "Press Ctrl+C to stop all port forwards"
echo ""

# Kill any existing port-forwards
pkill -f "kubectl.*port-forward" 2>/dev/null || true

# Start port forwards in background
# Use pod for RisingWave due to named port mismatch
kubectl -n risingwave port-forward pod/risingwave-standalone-0 4567:4567 &
kubectl -n risingwave port-forward svc/risingwave-minio 9001:9001 &
kubectl -n kafka port-forward svc/kafka-e11b-kafka-bootstrap 9092:9092 &
kubectl -n kafka port-forward svc/kafka-ui 8182:8080 &
kubectl -n monitoring port-forward svc/grafana 3000:3000 &
kubectl -n mlflow port-forward svc/mlflow-tracking 8889:80 2>/dev/null &

echo "Port forwards started:"
echo "  - RisingWave:   http://localhost:4567"
echo "  - MinIO:        http://localhost:9001"
echo "  - Kafka:        localhost:9092"
echo "  - Kafka UI:     http://localhost:8182"
echo "  - Grafana:      http://localhost:3000"
echo "  - MLflow:       http://localhost:8889 (if installed)"
echo ""

# Wait for Ctrl+C
wait
