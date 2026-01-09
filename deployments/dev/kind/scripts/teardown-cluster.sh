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
