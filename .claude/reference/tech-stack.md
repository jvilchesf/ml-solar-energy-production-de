
# Table of Contents

1. [Kind](#start-kind)
2. [Ingress](#install-ingress-nginx)
3. [Risingwave](#install-risingwave)
4. [Minio](#minio-in-risingwave)
5. [Grafana](#grafana)
6. [Kafka](#strimzi-kafka)
7. [Kafka-UI](#kafka-ui)
8. [mlflow](#mlflow)

### Start Kind

```sh
docker network create --subnet 172.100.0.0/16 rwml-34fa-network
```

```sh
KIND_EXPERIMENTAL_DOCKER_NETWORK=rwml-34fa-network kind create cluster --config ./kind-with-portmapping.yaml
```

### Install ingress-nginx

```sh
kubectl apply --recursive -f manifests/ingress-nginx-all-in-one.yaml
```

or 

```sh
kubectl apply --recursive -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/refs/heads/main/deploy/static/provider/kind/deploy.yaml
```

### Install Risingwave


[Chart](https://github.com/risingwavelabs/helm-charts/) [values](https://github.com/risingwavelabs/helm-charts/blob/main/charts/risingwave/values.yaml) are saved and modified in ```manifests/risingwave-values.yaml```

```sh
helm repo add risingwavelabs https://risingwavelabs.github.io/helm-charts/ --force-update
```

```sh
helm repo update
```

```sh
helm upgrade --install --create-namespace --wait risingwave risingwavelabs/risingwave --namespace=risingwave -f manifests/risingwave-values.yaml 
```

Verify with https://docs.risingwave.com/get-started/quickstart#step-2-connect-to-risingwave

From risingwave pod

```sh
psql -h localhost -p 4567 -d dev -U root
```

From outside the pod

```sh
psql -h risingwave.risingwave.svc.cluster.local -p 4567 -d dev -U root 
```

```sql

CREATE TABLE exam_scores (
  score_id int,
  exam_id int,
  student_id int,
  score real,
  exam_date date
);

```

```sql

INSERT INTO exam_scores (score_id, exam_id, student_id, score, exam_date)
VALUES
  (1, 101, 1001, 85.5, '2022-01-10'),
  (2, 101, 1002, 92.0, '2022-01-10'),
  (3, 101, 1003, 78.5, '2022-01-10'),
  (4, 102, 1001, 91.2, '2022-02-15'),
  (5, 102, 1003, 88.9, '2022-02-15');

```

```sql

CREATE MATERIALIZED VIEW average_exam_scores AS
SELECT
    exam_id,
    AVG(score) AS average_score,
    COUNT(score) AS total_scores
FROM
    exam_scores
GROUP BY
    exam_id;

```

```sql
SELECT * FROM average_exam_scores;
```

```sql
INSERT INTO exam_scores (score_id, exam_id, student_id, score, exam_date)
VALUES
  (11, 101, 1004, 89.5, '2022-05-05'),
  (12, 101, 1005, 93.2, '2022-05-05'),
  (13, 102, 1004, 87.1, '2022-06-10'),
  (14, 102, 1005, 91.7, '2022-06-10'),
  (15, 102, 1006, 84.3, '2022-06-10');
```

```sql
SELECT * FROM average_exam_scores;
```


Uninstall with:

```sh
helm uninstall risingwave -n risingwave
```

Port-forward to service:

```sh
kubectl -n risingwave port-forward svc/risingwave 4567:4567
```

### Minio in Risingwave

```sh
kubectl get secrets -n risingwave risingwave-minio -o json | jq -r '.data."root-password"' | base64 -D
```

#### AccessKey for mlflow

In Minio console (http://localhost:9001/login) create at: http://localhost:9001/access-keys a new Access Key / Secret Key pair and save them. Add them in the mlflow secret, see below.


### Grafana

```sh
helm repo add grafana https://grafana.github.io/helm-charts
```

```sh
helm upgrade --install --create-namespace --wait grafana grafana/grafana --namespace=monitoring --values manifests/grafana-values.yaml
```

### Strimzi Kafka

https://strimzi.io/quickstarts/

Kafka broker(s) are exposed via KIND portmapping. 


```sh
kubectl create namespace kafka
```

```sh
kubectl create -f 'https://strimzi.io/install/latest?namespace=kafka' -n kafka
```

```sh
kubectl apply -f manifests/kafka-e11b.yaml
```

see header in ``` manifests/kafka-e11b.yaml ``` for a quick start. 

To check the kafka brokers are accessible from outside the cluster do the following:

1. Create a topic from inside the k8s cluster
    ```sh
    kubectl exec -it kafka-e11b-dual-role-0 -n kafka -c kafka -- bin/kafka-topics.sh --bootstrap-server kafka-e11b-kafka-bootstrap:9092 --topic first_topic --create --partitions 3 --replication-factor 1
    ```

2. Produce a message to the `first_topic` from local with kcat
    ```sh
    echo "{'key': 'value'}" | kcat -b 127.0.0.1:9092 -P -t first_topic
    ```

3. Consume message from the `first_topic` from local with kcat.
    ```sh
    kcat -b 127.0.0.1:9092 -C -t first_topic
    ```

---

### Kafka-UI

```sh
kubectl apply -f manifests/kafka-ui-all-in-one.yaml
```

```sh
kubectl -n kafka port-forward svc/kafka-ui 8182:8080
```

---

### [SKIP] Redpanda

Notes: Redpanda chart values has replicas: 3 which has to match with the number of worker nodes in kind. 

```sh
helm repo add redpanda https://charts.redpanda.com
```

```sh
helm upgrade --install --create-namespace --wait redpanda redpanda/redpanda --namespace=redpanda --values manifests/redpanda-values.yaml
```

See https://docs.redpanda.com/current/manage/kubernetes/networking/k-connect-to-redpanda/

For console:

```sh
kubectl -n redpanda port-forward svc/redpanda-console 8384:8080
```

open http://localhost:8384/


For Kafka API:

```sh
kubectl -n redpanda port-forward svc/redpanda 9093:9093
```

Verify with:

```sh
kcat -b localhost:9093 -L
```

```sh
Metadata for all topics (from broker -1: localhost:9093/bootstrap):
 2 brokers:
  broker 1 at redpanda-1.redpanda.redpanda.svc.cluster.local:9093
  broker 0 at redpanda-0.redpanda.redpanda.svc.cluster.local:9093 (controller)
 1 topics:
  topic "_schemas" with 1 partitions:
    partition 0, leader 1, replicas: 1, isrs: 1
```

Uninstall with:

```sh
helm uninstall redpanda -n redpanda
```

### mlflow

#### Create a secret for mlflow

in ```manifests/mlflow-minio-secret.yaml``` add:

```yaml
---
apiVersion: v1
kind: Secret
metadata:
  name: mlflow-minio-secret
  namespace: mlflow
type: Opaque
stringData:
  AccessKeyID: REDACTED
  SecretKey: REDACTED
```

Apply it ``` kubectl apply --recursive -f manifests/mlflow-minio-secret.yaml```

#### Helm install

```sh
helm upgrade --install --create-namespace --wait mlflow oci://registry-1.docker.io/bitnamicharts/mlflow --namespace=mlflow --values deployments/dev/kind/manifests/mlflow-values.yaml
```

In a shell in the risingwave-postgresql-0 pod

pass: ```postgres``

```sh
psql -U postgres -h risingwave-postgresql.risingwave.svc.cluster.local
```

```sql
CREATE USER mlflow WITH ENCRYPTED password 'mlflow';
CREATE DATABASE mlflow WITH ENCODING='UTF8' OWNER=mlflow;
CREATE DATABASE mlflow_auth WITH ENCODING='UTF8' OWNER=mlflow;
```

```sh
kubectl -n mlflow port-forward svc/mlflow-tracking 8889:80
```

user / passwords are autogenerated, you have to do a 1 liner:

```sh
kubectl get secrets -n mlflow mlflow-tracking -o json | jq -r '.data."admin-password"' | base64 -D
```

```sh
kubectl get secrets -n mlflow mlflow-tracking -o json | jq -r '.data."admin-user"' | base64 -D
```

or

```sh
kubectl get secret --namespace mlflow mlflow-tracking -o jsonpath="{.data.admin-password }"  | base64 -D
```

```sh
kubectl get secret --namespace mlflow mlflow-tracking -o jsonpath="{.data.admin-user }"  | base64 -D
```

Uninstall with:

```sh
helm uninstall mlflow -n mlflow
```

Test with:


```py
import mlflow
from mlflow.models import infer_signature

import pandas as pd
from sklearn import datasets
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

import os

# Load the Iris dataset
X, y = datasets.load_iris(return_X_y=True)

# Split the data into training and test sets
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# Define the model hyperparameters
params = {
    "solver": "lbfgs",
    "max_iter": 1000,
    "multi_class": "auto",
    "random_state": 8888,
}

# Train the model
lr = LogisticRegression(**params)
lr.fit(X_train, y_train)

# Predict on the test set
y_pred = lr.predict(X_test)

# Calculate metrics
accuracy = accuracy_score(y_test, y_pred)

# Set our tracking server uri for logging
os.environ['MLFLOW_TRACKING_USERNAME'] = 'CHANGE-ME'
os.environ['MLFLOW_TRACKING_PASSWORD'] = 'CHANGE-ME'
mlflow.set_tracking_uri("http://localhost:8889")

# Create a new MLflow Experiment
mlflow.set_experiment("MLflow Quickstart")

# Start an MLflow run
with mlflow.start_run():
    # Log the hyperparameters
    mlflow.log_params(params)

    # Log the loss metric
    mlflow.log_metric("accuracy", accuracy)

    # Set a tag that we can use to remind ourselves what this run was for
    mlflow.set_tag("Training Info", "Basic LR model for iris data")

    # Infer the model signature
    signature = infer_signature(X_train, lr.predict(X_train))

    # Log the model
    model_info = mlflow.sklearn.log_model(
        sk_model=lr,
        artifact_path="iris_model",
        signature=signature,
        input_example=X_train,
        registered_model_name="tracking-quickstart",
    )
```

---

### SKIP - Minio is installed by Risingwave - Install Minio

```sh
helm repo add minio https://charts.min.io/
```

```sh
helm upgrade --install --create-namespace --wait minio minio/minio --namespace=minio --values manifests/minio-values.yaml
```

Uninstall with:

```sh
helm uninstall minio -n minio
```

---
