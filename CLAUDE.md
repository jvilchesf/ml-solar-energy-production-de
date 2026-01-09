# ML Energy Production Germany - Development Guidelines

## Project Overview

**Goal**: Predict daily solar energy production in Germany using machine learning.

This system ingests historical and real-time data from German energy and weather APIs, engineers features, trains ML models, and serves predictions through a streaming architecture.

### Data Sources
| Source | Data | Update Frequency |
|--------|------|------------------|
| [SMARD API](https://smard.api.bund.dev/) | Solar energy production (MW) | 15 minutes |
| [Open-Meteo API](https://open-meteo.com/) | Weather (temperature, cloud cover, solar radiation) | Hourly |

### Pipeline Architecture
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

### Target Prediction
- **Output**: Solar energy production in megawatts (MW) for Germany
- **Granularity**: Daily predictions
- **Horizon**: Next-day forecast based on weather predictions

---

## 1. Core Principles

- **Type Safety**: Use type hints on all function signatures and class attributes
- **Configuration via Environment**: All config through pydantic-settings, never hardcoded values
- **Immutable Data Models**: Use Pydantic models for all data structures
- **Fail Fast**: Validate inputs at service boundaries, raise exceptions early
- **Idempotent Operations**: All pipeline stages must be safely re-runnable
- **No Magic**: Explicit imports, no wildcard imports, clear dependencies

## 2. Tech Stack

| Layer | Technology | Version |
|-------|------------|---------|
| Language | Python | 3.12 |
| Package Manager | uv | latest |
| Kubernetes | Kind (local) | latest |
| Streaming | Kafka (Strimzi) | latest |
| Database | RisingWave | latest |
| Object Storage | MinIO | via RisingWave |
| ML Tracking | MLflow | latest |
| Monitoring | Grafana | latest |
| Linting/Formatting | Ruff | latest |
| Testing | pytest | latest |

for any reference needed to install the tech stack reference the file in @.claude/reference/tech-stack.md

### Key Libraries
```toml
# Common dependencies across services
dependencies = [
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "confluent-kafka>=2.0",
    "psycopg2-binary>=2.9",  # RisingWave connection
    "httpx>=0.27",           # Async HTTP client
    "structlog>=24.0",       # Structured logging
]
```

### Data APIs
- **Solar Production**: SMARD API (smard.api.bund.dev) - German govt, no auth
- **Weather**: Open-Meteo API (open-meteo.com) - Free, no auth

## 3. Architecture

### Project Structure
```
ml-energy-production-de/
├── services/                    # Pipeline services (each is a uv workspace member)
│   ├── extraction/              # Pipeline 1: Data extraction
│   │   ├── src/
│   │   │   ├── config.py        # Pydantic settings
│   │   │   ├── main.py          # Entry point
│   │   │   ├── smard_client.py  # Solar data API client
│   │   │   ├── weather_client.py # Weather API client
│   │   │   └── producer.py      # Kafka producer
│   │   ├── pyproject.toml
│   │   └── settings.env
│   ├── features/                # Pipeline 2: Feature engineering
│   ├── training/                # Pipeline 3: Model training
│   └── inference/               # Pipeline 4: Inference
├── deployments/
│   └── dev/
│       ├── kind/                # Kind cluster setup
│       │   ├── manifests/       # Helm values, K8s manifests
│       │   └── *.sh             # Setup scripts
│       └── services/            # Kustomize per service
├── dockers/                     # Dockerfiles per service
├── scripts/                     # Build and deploy scripts
├── tests/                       # Integration tests
├── pyproject.toml               # Root workspace config
└── CLAUDE.md
```

### Service Structure Pattern
Each service in `services/` follows:
```
service-name/
├── src/
│   ├── __init__.py
│   ├── config.py       # Settings class
│   ├── main.py         # Entry point with run loop
│   ├── models.py       # Pydantic data models (if needed)
│   └── *.py            # Domain logic
├── pyproject.toml      # Service dependencies
├── settings.env        # Local dev settings (not committed)
└── README.md
```

## 4. Code Style

### Naming Conventions
```python
# Files: snake_case
weather_client.py
kafka_producer.py

# Classes: PascalCase
class SolarProductionRecord(BaseModel): ...
class KafkaProducerService: ...

# Functions/methods: snake_case, verb-first
def fetch_solar_data() -> list[SolarRecord]: ...
def produce_to_kafka(records: list[dict]) -> None: ...

# Constants: SCREAMING_SNAKE_CASE
KAFKA_TOPIC_SOLAR = "solar_production_raw"
DEFAULT_BATCH_SIZE = 1000

# Private: leading underscore
def _parse_response(data: dict) -> SolarRecord: ...
```

### Configuration Pattern
```python
# config.py
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    # Kafka
    kafka_bootstrap_servers: str = Field(default="localhost:9092")
    kafka_topic_solar: str = Field(default="solar_production_raw")
    kafka_topic_weather: str = Field(default="weather_raw")

    # API
    smard_base_url: str = Field(default="https://www.smard.de/app/chart_data")
    openmeteo_base_url: str = Field(default="https://api.open-meteo.com/v1")

    # Service
    poll_interval_seconds: int = Field(default=900)  # 15 minutes
    batch_size: int = Field(default=1000)

    model_config = {"env_file": "settings.env", "env_file_encoding": "utf-8"}

settings = Settings()
```

### Data Models Pattern
```python
# models.py
from datetime import datetime
from pydantic import BaseModel, Field

class SolarProductionRecord(BaseModel):
    timestamp: datetime
    production_mw: float = Field(ge=0)
    region: str = Field(default="DE")

    model_config = {"frozen": True}

class WeatherRecord(BaseModel):
    timestamp: datetime
    temperature_c: float
    cloud_cover_pct: float = Field(ge=0, le=100)
    solar_radiation_wm2: float = Field(ge=0)
    latitude: float
    longitude: float
```

## 5. Logging

Use `structlog` for structured JSON logging:

```python
import structlog

logger = structlog.get_logger()

# Configuration (in main.py)
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ]
)

# Usage
logger.info("fetching_solar_data", start_date="2024-01-01", end_date="2024-01-31")
logger.error("kafka_produce_failed", topic=topic, error=str(e), record_count=len(records))
```

### What to Log
- Service startup/shutdown with configuration summary
- API requests (URL, response status, duration)
- Kafka produce/consume (topic, partition, offset, record count)
- Errors with full context (never just the exception message)
- Pipeline stage transitions

## 6. Testing

### Structure
```
tests/
├── unit/
│   ├── extraction/
│   │   ├── test_smard_client.py
│   │   └── test_weather_client.py
│   └── features/
├── integration/
│   ├── test_kafka_roundtrip.py
│   └── test_risingwave_write.py
└── conftest.py          # Shared fixtures
```

### Naming and Patterns
```python
# test_smard_client.py
import pytest
from unittest.mock import patch, MagicMock
from src.smard_client import SmardClient, SolarProductionRecord

class TestSmardClient:
    def test_fetch_solar_data_returns_records(self):
        """fetch_solar_data should return list of SolarProductionRecord."""
        client = SmardClient()
        records = client.fetch_solar_data(start="2024-01-01", end="2024-01-02")

        assert len(records) > 0
        assert all(isinstance(r, SolarProductionRecord) for r in records)

    def test_fetch_solar_data_with_invalid_date_raises(self):
        """fetch_solar_data should raise ValueError for invalid date range."""
        client = SmardClient()

        with pytest.raises(ValueError, match="start.*after.*end"):
            client.fetch_solar_data(start="2024-01-31", end="2024-01-01")

# Fixtures in conftest.py
@pytest.fixture
def mock_kafka_producer():
    with patch("confluent_kafka.Producer") as mock:
        yield mock
```

### Running Tests
```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src --cov-report=term-missing

# Run specific service tests
uv run pytest tests/unit/extraction/
```

## 7. Kafka Patterns

### Producer Pattern
```python
from confluent_kafka import Producer
from src.config import settings

class KafkaProducerService:
    def __init__(self):
        self._producer = Producer({
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "enable.idempotence": True,
            "acks": "all",
            "retries": 3,
        })

    def produce(self, topic: str, records: list[dict]) -> None:
        for record in records:
            self._producer.produce(
                topic=topic,
                key=record.get("timestamp", "").encode(),
                value=json.dumps(record).encode(),
                callback=self._delivery_callback,
            )
        self._producer.flush()

    def _delivery_callback(self, err, msg):
        if err:
            logger.error("kafka_delivery_failed", error=str(err))
```

### Consumer Pattern
```python
from confluent_kafka import Consumer

class KafkaConsumerService:
    def __init__(self, topics: list[str], group_id: str):
        self._consumer = Consumer({
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "group.id": group_id,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        })
        self._consumer.subscribe(topics)

    def consume(self, timeout: float = 1.0) -> list[dict]:
        messages = self._consumer.consume(num_messages=100, timeout=timeout)
        records = []
        for msg in messages:
            if msg.error():
                logger.error("kafka_consume_error", error=msg.error())
                continue
            records.append(json.loads(msg.value().decode()))
        return records

    def commit(self):
        self._consumer.commit()
```

## 8. RisingWave Patterns

### Connection Pattern
```python
import psycopg2
from contextlib import contextmanager
from src.config import settings

@contextmanager
def get_risingwave_connection():
    conn = psycopg2.connect(
        host=settings.risingwave_host,
        port=settings.risingwave_port,
        database=settings.risingwave_database,
        user=settings.risingwave_user,
    )
    try:
        yield conn
    finally:
        conn.close()

# Usage
with get_risingwave_connection() as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM features_enriched LIMIT 10")
        rows = cur.fetchall()
```

## 9. Development Commands

```bash
# Setup
uv sync                              # Install all dependencies
uv sync --all-packages               # Install all workspace packages

# Development
uv run python -m services.extraction.src.main   # Run a service
uv run pytest                        # Run tests
uv run ruff check .                  # Lint
uv run ruff format .                 # Format

# Docker
docker build -f dockers/extraction.Dockerfile -t extraction:latest .
docker push <registry>/extraction:latest

# Kubernetes (Kind)
./deployments/dev/kind/create_kind_kubernete.sh  # Create cluster
kubectl apply -k deployments/dev/services/extraction/
kubectl logs -f deployment/extraction -n default
```

## 10. AI Assistant Instructions

1. **Read CLAUDE.md first** before making changes to understand conventions
2. **Follow the service structure** - each pipeline is a separate service in `services/`
3. **Use pydantic-settings** for all configuration - never hardcode values
4. **Use Pydantic models** for all data structures with proper validation
5. **Add type hints** to all functions and use `ruff check` before committing
6. **Write tests** for new functionality - at minimum unit tests for business logic
7. **Use structlog** for logging with contextual fields, not print statements
8. **Check Kafka topics exist** before producing/consuming - create if needed
9. **Keep services independent** - shared code goes in a `common/` package
10. **Run `uv run ruff check . && uv run ruff format .`** before completing any task
