# Feature Pipeline Implementation Plan

## Overview

**Pipeline 2: Feature Engineering** consumes raw solar production and weather data from Kafka topics, performs feature engineering (combining, windowing, aggregations), and writes enriched features to RisingWave for use by the training pipeline.

### Key Requirements
- Consume from Kafka topics: `solar_production_raw` and `weather_raw`
- Combine solar + weather data by timestamp alignment
- Engineer features: rolling averages, lagged values, temporal encodings
- Write to RisingWave table: `features_enriched`
- Support both historical (backfill) and stream (continuous) modes

### Success Criteria
- Service consumes all messages from both Kafka topics
- Features are correctly calculated and written to RisingWave
- All tests pass
- Follows project conventions from CLAUDE.md

---

## Relevant Files

### Files to Create

| Path | Description |
|------|-------------|
| `services/features/pyproject.toml` | Service dependencies and build config |
| `services/features/src/__init__.py` | Package init |
| `services/features/src/config.py` | Pydantic settings for Kafka, RisingWave, and service config |
| `services/features/src/models.py` | Data models for feature records |
| `services/features/src/consumer.py` | Kafka consumer service |
| `services/features/src/feature_engineer.py` | Feature calculation logic |
| `services/features/src/risingwave_client.py` | RisingWave connection and writer |
| `services/features/src/main.py` | Entry point with CLI and run loop |
| `services/features/settings.env.example` | Example environment configuration |
| `tests/unit/features/__init__.py` | Test package init |
| `tests/unit/features/test_feature_engineer.py` | Unit tests for feature calculations |
| `tests/unit/features/test_consumer.py` | Unit tests for Kafka consumer |
| `tests/unit/features/test_risingwave_client.py` | Unit tests for RisingWave client |

### Files to Modify

| Path | Description |
|------|-------------|
| `pyproject.toml` (root) | Add `services/features` to workspace members |

### Reference Files (read-only)

| Path | Purpose |
|------|---------|
| `services/extraction/src/config.py` | Configuration pattern to follow |
| `services/extraction/src/models.py` | Data model pattern to follow |
| `services/extraction/src/producer.py` | Kafka operations pattern (reverse for consumer) |
| `services/extraction/src/main.py` | Main loop and signal handling pattern |
| `CLAUDE.md` | Project conventions and guidelines |

---

## Dependencies

### New Libraries Required

```toml
dependencies = [
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "confluent-kafka>=2.0",
    "psycopg2-binary>=2.9",  # RisingWave uses PostgreSQL protocol
    "structlog>=24.0",
]
```

### Existing Utilities to Use
- structlog for logging (same pattern as extraction)
- Pydantic BaseModel for data validation
- Pydantic BaseSettings for configuration

### Configuration Changes
- RisingWave must be running and accessible
- Kafka topics must exist with data from Pipeline 1

---

## Step by Step Tasks

### Task 1: Create Service Directory Structure

**Files**:
- `services/features/pyproject.toml` (create new)
- `services/features/src/__init__.py` (create new)

**Action**: Set up the basic service structure

**Details**:
```toml
# pyproject.toml
[project]
name = "features"
version = "0.1.0"
description = "Pipeline 2: Feature engineering from raw Kafka streams to RisingWave"
requires-python = ">=3.12"
dependencies = [
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "confluent-kafka>=2.0",
    "psycopg2-binary>=2.9",
    "structlog>=24.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src"]
```

Create empty `src/__init__.py` file.

---

### Task 2: Create Configuration Module

**File**: `services/features/src/config.py` (create new)

**Action**: Define Pydantic settings for the service

**Details**:
- Kafka consumer settings (bootstrap servers, topics, consumer group)
- RisingWave connection settings (host, port, database, user, password)
- Service settings (poll interval, batch size)
- Use `Field(default=...)` pattern from extraction service
- Load from `settings.env` file

**Key settings**:
```python
kafka_bootstrap_servers: str = Field(default="localhost:30092")
kafka_topic_solar: str = Field(default="solar_production_raw")
kafka_topic_weather: str = Field(default="weather_raw")
kafka_consumer_group: str = Field(default="features-service")
risingwave_host: str = Field(default="localhost")
risingwave_port: int = Field(default=4567)
risingwave_database: str = Field(default="dev")
risingwave_user: str = Field(default="root")
```

---

### Task 3: Create Data Models

**File**: `services/features/src/models.py` (create new)

**Action**: Define Pydantic models for input and output data

**Details**:

1. Import models from extraction service or redefine:
   - `SolarProductionRecord` (timestamp, production_mw, region)
   - `WeatherRecord` (timestamp, temperature_c, cloud_cover_pct, solar_radiation_wm2, latitude, longitude)

2. Create `FeatureMode` enum:
   - `HISTORICAL` - process all available data then exit
   - `STREAM` - continuous processing

3. Create `EnrichedFeatureRecord` model:
   - All base fields from solar + weather
   - Engineered features: `production_ma_24h`, `temperature_ma_24h`, `cloud_cover_ma_24h`
   - Lagged features: `production_lag_1h`, `production_lag_24h`
   - Temporal features: `hour_of_day`, `day_of_week`, `is_weekend`

4. Use `model_config = {"frozen": True}` for immutability

---

### Task 4: Create Kafka Consumer Service

**File**: `services/features/src/consumer.py` (create new)

**Action**: Implement Kafka consumer for both topics

**Details**:

1. Create `KafkaConsumerService` class:
   - Initialize with `Consumer` from confluent_kafka
   - Subscribe to both `solar_production_raw` and `weather_raw` topics
   - Use `auto.offset.reset = "earliest"` for historical mode
   - Use `enable.auto.commit = False` for manual offset management

2. Consumer configuration:
   ```python
   Consumer({
       "bootstrap.servers": settings.kafka_bootstrap_servers,
       "group.id": settings.kafka_consumer_group,
       "auto.offset.reset": "earliest",
       "enable.auto.commit": False,
   })
   ```

3. Methods to implement:
   - `consume_batch(timeout: float = 1.0) -> tuple[list[SolarProductionRecord], list[WeatherRecord]]`
   - `commit() -> None`
   - `close() -> None`

4. Parse JSON messages back to Pydantic models
5. Log consumption metrics (messages received, topic, partition, offset)

---

### Task 5: Create Feature Engineer Module

**File**: `services/features/src/feature_engineer.py` (create new)

**Action**: Implement feature calculation logic

**Details**:

1. Create `FeatureEngineer` class that:
   - Maintains internal state for rolling windows (use a deque or list)
   - Aligns solar and weather records by timestamp (nearest hour)
   - Calculates moving averages over configurable windows

2. Methods to implement:
   - `add_solar_records(records: list[SolarProductionRecord]) -> None`
   - `add_weather_records(records: list[WeatherRecord]) -> None`
   - `compute_features() -> list[EnrichedFeatureRecord]`
   - `_calculate_moving_average(values: list[float], window: int) -> float`
   - `_align_records() -> list[tuple[SolarProductionRecord, WeatherRecord]]`

3. Feature calculations:
   - `production_ma_24h`: 24-hour moving average of production_mw
   - `temperature_ma_24h`: 24-hour moving average of temperature
   - `cloud_cover_ma_24h`: 24-hour moving average of cloud cover
   - `production_lag_1h`: production value from 1 hour ago
   - `production_lag_24h`: production value from 24 hours ago
   - `hour_of_day`: extract hour (0-23) from timestamp
   - `day_of_week`: extract day (0-6, Monday=0) from timestamp
   - `is_weekend`: True if Saturday or Sunday

4. Handle missing data gracefully (use None or interpolation)

---

### Task 6: Create RisingWave Client

**File**: `services/features/src/risingwave_client.py` (create new)

**Action**: Implement RisingWave connection and data writer

**Details**:

1. Create `RisingWaveClient` class with:
   - Connection pool or context manager pattern
   - Table creation (idempotent - IF NOT EXISTS)
   - Batch insert method

2. Connection pattern (from CLAUDE.md):
   ```python
   @contextmanager
   def get_connection(self):
       conn = psycopg2.connect(
           host=self._host,
           port=self._port,
           database=self._database,
           user=self._user,
           password=self._password,
       )
       try:
           yield conn
       finally:
           conn.close()
   ```

3. Methods to implement:
   - `ensure_table_exists() -> None` - create table if not exists
   - `write_features(records: list[EnrichedFeatureRecord]) -> int` - batch insert
   - `close() -> None`

4. Table schema:
   ```sql
   CREATE TABLE IF NOT EXISTS features_enriched (
       timestamp TIMESTAMPTZ PRIMARY KEY,
       region VARCHAR(10),
       production_mw DOUBLE PRECISION,
       temperature_c DOUBLE PRECISION,
       cloud_cover_pct DOUBLE PRECISION,
       solar_radiation_wm2 DOUBLE PRECISION,
       latitude DOUBLE PRECISION,
       longitude DOUBLE PRECISION,
       production_ma_24h DOUBLE PRECISION,
       temperature_ma_24h DOUBLE PRECISION,
       cloud_cover_ma_24h DOUBLE PRECISION,
       production_lag_1h DOUBLE PRECISION,
       production_lag_24h DOUBLE PRECISION,
       hour_of_day INTEGER,
       day_of_week INTEGER,
       is_weekend BOOLEAN
   );
   ```

5. Use upsert pattern (ON CONFLICT DO UPDATE) for idempotency

---

### Task 7: Create Main Entry Point

**File**: `services/features/src/main.py` (create new)

**Action**: Implement CLI entry point and run loop

**Details**:

1. Configure structlog (same as extraction):
   ```python
   structlog.configure(
       processors=[
           structlog.processors.TimeStamper(fmt="iso"),
           structlog.processors.add_log_level,
           structlog.processors.JSONRenderer(),
       ],
   )
   ```

2. Implement signal handlers for graceful shutdown (SIGINT, SIGTERM)

3. Create CLI with argparse:
   - `--mode historical|stream` (default: stream)

4. Implement `run_historical_mode()`:
   - Consume all messages from beginning
   - Process in batches
   - Compute features
   - Write to RisingWave
   - Exit when caught up

5. Implement `run_stream_mode()`:
   - Continuous polling loop
   - Process new messages as they arrive
   - Periodic commit of offsets
   - Run until shutdown signal

6. Main function pattern:
   - Parse arguments
   - Register signal handlers
   - Initialize consumer, feature engineer, risingwave client
   - Run appropriate mode
   - Cleanup on exit

---

### Task 8: Create Settings Example File

**File**: `services/features/settings.env.example` (create new)

**Action**: Create example environment configuration

**Details**:
```env
# Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS=localhost:30092
KAFKA_TOPIC_SOLAR=solar_production_raw
KAFKA_TOPIC_WEATHER=weather_raw
KAFKA_CONSUMER_GROUP=features-service

# RisingWave Configuration
RISINGWAVE_HOST=localhost
RISINGWAVE_PORT=4567
RISINGWAVE_DATABASE=dev
RISINGWAVE_USER=root
RISINGWAVE_PASSWORD=

# Service Configuration
POLL_INTERVAL_SECONDS=30
BATCH_SIZE=1000
FEATURE_WINDOW_HOURS=24
```

---

### Task 9: Update Root Workspace Configuration

**File**: `pyproject.toml` (modify existing)

**Action**: Add features service to uv workspace

**Details**:

Find the workspace members section and add the features service:
```toml
[tool.uv.workspace]
members = ["services/extraction", "services/features"]
```

If no workspace section exists, create it.

---

### Task 10: Create Unit Tests for Feature Engineer

**Files**:
- `tests/unit/features/__init__.py` (create new)
- `tests/unit/features/test_feature_engineer.py` (create new)

**Action**: Write unit tests for feature calculation logic

**Details**:

1. Test cases:
   - `test_calculate_moving_average_with_full_window`
   - `test_calculate_moving_average_with_partial_window`
   - `test_align_records_matching_timestamps`
   - `test_align_records_missing_weather`
   - `test_compute_features_returns_enriched_records`
   - `test_hour_of_day_extraction`
   - `test_day_of_week_extraction`
   - `test_is_weekend_calculation`
   - `test_lagged_features_calculation`

2. Use pytest fixtures for sample data:
   ```python
   @pytest.fixture
   def sample_solar_records():
       return [
           SolarProductionRecord(
               timestamp=datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc),
               production_mw=1500.0,
               region="DE",
           ),
           # ... more records
       ]
   ```

---

### Task 11: Create Unit Tests for Consumer

**File**: `tests/unit/features/test_consumer.py` (create new)

**Action**: Write unit tests for Kafka consumer

**Details**:

1. Mock `confluent_kafka.Consumer` using the pattern from extraction tests:
   ```python
   @pytest.fixture(autouse=True)
   def mock_confluent_kafka(self):
       with patch.dict(sys.modules, {"confluent_kafka": MagicMock()}):
           # Setup mock consumer
           ...
   ```

2. Test cases:
   - `test_consume_batch_returns_parsed_records`
   - `test_consume_batch_handles_empty_response`
   - `test_commit_calls_consumer_commit`
   - `test_close_calls_consumer_close`
   - `test_handles_malformed_json_gracefully`

---

### Task 12: Create Unit Tests for RisingWave Client

**File**: `tests/unit/features/test_risingwave_client.py` (create new)

**Action**: Write unit tests for RisingWave client

**Details**:

1. Mock `psycopg2.connect` for database operations

2. Test cases:
   - `test_ensure_table_exists_creates_table`
   - `test_write_features_inserts_records`
   - `test_write_features_returns_count`
   - `test_write_features_handles_duplicates`
   - `test_connection_error_is_logged`

---

## Testing Strategy

### Unit Tests
- **Location**: `tests/unit/features/`
- **Coverage**: Feature engineer logic, consumer parsing, RisingWave writes
- **Mocking**: Mock Kafka and database connections

### Integration Tests (optional, for later)
- **Location**: `tests/integration/`
- **Tests**: Full pipeline from Kafka to RisingWave
- **Requirements**: Running Kafka and RisingWave

### Key Test Cases
1. Feature calculations produce correct values
2. Timestamp alignment works across solar/weather data
3. Consumer handles various message formats
4. RisingWave writes are idempotent
5. Graceful handling of missing data

---

## Validation Commands

Run these commands in order to validate the implementation:

```bash
# 1. Sync dependencies
uv sync --all-packages

# 2. Run linting
uv run ruff check services/features/

# 3. Run formatting
uv run ruff format services/features/

# 4. Run unit tests
uv run pytest tests/unit/features/ -v

# 5. Run all tests with coverage
uv run pytest --cov=services.features.src --cov-report=term-missing tests/unit/features/

# 6. Type check (if using mypy)
uv run mypy services/features/src/

# 7. Test service starts (dry run)
uv run python -m services.features.src.main --help
```

---

## Integration Notes

### How This Connects to Existing Code
- **Input**: Consumes from Kafka topics created by Pipeline 1 (extraction)
- **Output**: Writes to RisingWave which will be read by Pipeline 3 (training)
- **Pattern**: Follows same service structure as extraction

### Potential Breaking Changes
- None - this is a new service

### Migration Steps
1. Ensure RisingWave is running: `kubectl -n risingwave port-forward svc/risingwave 4567:4567`
2. Ensure Kafka topics have data (run extraction first)
3. Run features service in historical mode first to backfill

### Documentation Updates
- Update CLAUDE.md if new patterns emerge
- Consider adding README.md to services/features/

---

## Execution Checklist

Before considering this plan complete, verify:

- [ ] All files listed above are created
- [ ] `uv sync --all-packages` succeeds
- [ ] `uv run ruff check .` passes with no errors
- [ ] `uv run ruff format .` makes no changes
- [ ] `uv run pytest tests/unit/features/` passes
- [ ] Service starts with `--help` flag
- [ ] Service connects to Kafka and RisingWave when run
