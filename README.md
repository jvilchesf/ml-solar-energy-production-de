# ML Solar Energy Production Germany

Predict daily solar energy production in Germany using machine learning. This system ingests historical and real-time data from German energy and weather APIs, engineers features, trains ML models, and serves predictions through a streaming architecture.

## Data Sources

| Source | Data | Update Frequency |
|--------|------|------------------|
| [SMARD API](https://smard.api.bund.dev/) | Solar energy production (MW) | 15 minutes |
| [Open-Meteo API](https://open-meteo.com/) | Weather (temperature, cloud cover, solar radiation) | Hourly |

## Architecture

```
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│   PIPELINE 1     │    │   PIPELINE 2     │    │   PIPELINE 3     │    │   PIPELINE 4     │
│   Extraction     │───▶│   Features       │───▶│   Training       │───▶│   Inference      │
│                  │    │                  │    │                  │    │                  │
│ SMARD + Weather  │    │ Kafka ──▶        │    │ LazyPredict      │    │ Load model       │
│ APIs ──▶ Kafka   │    │ Feature Eng ──▶  │    │ Top 3 models     │    │ Predict on live  │
│                  │    │ RisingWave       │    │ Register >80%    │    │ data             │
└──────────────────┘    └──────────────────┘    └──────────────────┘    └──────────────────┘
        │                       │                       │                       │
        ▼                       ▼                       ▼                       ▼
     Kafka               RisingWave                 MLflow                  Grafana
   (raw data)         (features table)           (model registry)        (dashboards)
```

### Pipeline Status

| Pipeline | Status | Description |
|----------|--------|-------------|
| Extraction | Complete | Fetches solar/weather data, publishes to Kafka |
| Features | Complete | Consumes Kafka, engineers features, writes to RisingWave |
| Training | Planned | Train models with LazyPredict, register in MLflow |
| Inference | Planned | Serve predictions from trained models |

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.12 |
| Package Manager | uv |
| Kubernetes | Kind (local) |
| Streaming | Kafka (Strimzi) |
| Database | RisingWave |
| Object Storage | MinIO |
| ML Tracking | MLflow |
| Monitoring | Grafana |

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Docker
- kubectl
- Helm

## Quick Start

### 1. Install Dependencies

```bash
uv sync --all-packages
```

### 2. Set Up Infrastructure

Create the Kind cluster with all required services:

```bash
cd deployments/dev/kind
./scripts/setup-cluster.sh
```

This will set up:
- Kind Kubernetes cluster
- Strimzi Kafka
- RisingWave
- MinIO
- Grafana
- MLflow

### 3. Configure Services

Copy and configure environment files for each service:

```bash
# Extraction service
cp services/extraction/settings.env.example services/extraction/settings.env

# Features service
cp services/features/settings.env.example services/features/settings.env
```

### 4. Run Pipelines

**Historical backfill** (fetch all data since 2025-01-01, then exit):

```bash
# Run extraction pipeline (historical mode)
uv run python -m services.extraction.src.main --mode historical

# Run features pipeline (historical mode)
uv run python -m services.features.src.main --mode historical
```

**Streaming mode** (continuous polling):

```bash
# Run extraction pipeline (stream mode)
uv run python -m services.extraction.src.main --mode stream

# Run features pipeline (stream mode)
uv run python -m services.features.src.main --mode stream
```

## Project Structure

```
ml-solar-energy-production-de/
├── services/                    # Pipeline services (uv workspace)
│   ├── extraction/              # Pipeline 1: Data extraction
│   └── features/                # Pipeline 2: Feature engineering
├── deployments/
│   └── dev/
│       └── kind/                # Kind cluster setup
│           ├── manifests/       # Helm values, K8s manifests
│           └── scripts/         # Setup scripts
├── tests/                       # Unit and integration tests
├── pyproject.toml               # Root workspace config
├── CLAUDE.md                    # Development guidelines
└── README.md
```

## Services

### Extraction Service (Pipeline 1)

Fetches solar production and weather data from external APIs and publishes to Kafka.

**Components:**
- `SmardClient` - Fetches solar production data from SMARD API
- `WeatherClient` - Fetches weather data from Open-Meteo API
- `KafkaProducerService` - Publishes records to Kafka topics

**Kafka Topics:**
- `solar_production_raw` - Solar production records
- `weather_raw` - Weather records

### Features Service (Pipeline 2)

Consumes raw data from Kafka, engineers features, and writes to RisingWave.

**Components:**
- `KafkaConsumerService` - Consumes from Kafka topics
- `FeatureEngineer` - Computes engineered features
- `RisingWaveClient` - Writes features to RisingWave

**Engineered Features:**
- Moving averages (24h): `production_ma_24h`, `temperature_ma_24h`, `cloud_cover_ma_24h`
- Lagged values: `production_lag_1h`, `production_lag_24h`
- Temporal: `hour_of_day`, `day_of_week`, `is_weekend`

**RisingWave Table:** `features_enriched`

## Development

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src --cov-report=term-missing

# Run specific service tests
uv run pytest tests/unit/extraction/
uv run pytest tests/unit/features/
```

### Linting and Formatting

```bash
# Lint
uv run ruff check .

# Format
uv run ruff format .
```

### Port Forwarding (for local access)

```bash
# RisingWave
kubectl -n risingwave port-forward svc/risingwave 4567:4567

# Kafka UI
kubectl -n kafka port-forward svc/kafka-ui 8182:8080

# MLflow
kubectl -n mlflow port-forward svc/mlflow-tracking 8889:80

# MinIO Console
kubectl -n risingwave port-forward svc/risingwave-minio 9001:9001
```

## Configuration

All services use Pydantic settings with environment variables. Key configuration options:

| Variable | Description | Default |
|----------|-------------|---------|
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka broker address | `localhost:9092` |
| `KAFKA_TOPIC_SOLAR` | Solar data topic | `solar_production_raw` |
| `KAFKA_TOPIC_WEATHER` | Weather data topic | `weather_raw` |
| `RISINGWAVE_HOST` | RisingWave host | `localhost` |
| `RISINGWAVE_PORT` | RisingWave port | `4567` |
| `POLL_INTERVAL_SECONDS` | Polling interval (stream mode) | `900` (15 min) |

## License

MIT
