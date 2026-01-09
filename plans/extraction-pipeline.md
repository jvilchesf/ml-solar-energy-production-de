# Plan: Extraction Pipeline (Pipeline 1)

## Overview

Implement the first pipeline service that extracts solar energy production data from SMARD API and weather data from Open-Meteo API, then publishes both to Kafka topics for downstream processing.

### Operating Modes

The service supports two operating modes:

| Mode | Description | Behavior |
|------|-------------|----------|
| **historical** | Backfill data since 2025-01-01 | Fetches all available data, then exits |
| **stream** | Real-time continuous extraction | Polls at regular intervals indefinitely |

### Key Requirements
- Fetch solar energy production data (MW) from SMARD API (German Federal Network Agency)
- Fetch weather data (temperature, cloud cover, solar radiation) from Open-Meteo API
- Support **historical mode** (backfill since 2025-01-01) and **stream mode** (continuous polling)
- Publish raw data to Kafka topics: `solar_production_raw` and `weather_raw`
- Use Open-Meteo Archive API for historical weather data
- Follow project conventions from CLAUDE.md

### Success Criteria
- Service starts and connects to Kafka successfully
- `--mode historical` fetches all data since 2025-01-01 and exits
- `--mode stream` runs continuously with configurable poll interval
- SMARD client fetches solar production data and returns validated Pydantic models
- Weather client fetches data for Germany's geographic center using appropriate API (Archive vs Forecast)
- Data is successfully produced to Kafka topics
- All tests pass
- Code passes ruff check and format

---

## Relevant Files

| File | Action | Description |
|------|--------|-------------|
| `services/extraction/pyproject.toml` | Create | Service dependencies |
| `services/extraction/src/__init__.py` | Create | Package init |
| `services/extraction/src/config.py` | Create | Pydantic settings |
| `services/extraction/src/models.py` | Create | Data models |
| `services/extraction/src/smard_client.py` | Create | SMARD API client |
| `services/extraction/src/weather_client.py` | Create | Open-Meteo API client (Forecast + Archive) |
| `services/extraction/src/producer.py` | Create | Kafka producer service |
| `services/extraction/src/main.py` | Create | Entry point with CLI and mode handling |
| `services/extraction/settings.env.example` | Create | Example env file |
| `tests/unit/extraction/__init__.py` | Create | Test package init |
| `tests/unit/extraction/test_smard_client.py` | Create | SMARD client tests |
| `tests/unit/extraction/test_weather_client.py` | Create | Weather client tests |
| `tests/unit/extraction/test_producer.py` | Create | Producer tests |
| `tests/conftest.py` | Create | Shared test fixtures |
| `pyproject.toml` | Modify | Add workspace member |

---

## Dependencies

### New Libraries (in services/extraction/pyproject.toml)
```toml
dependencies = [
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "confluent-kafka>=2.0",
    "httpx>=0.27",
    "structlog>=24.0",
]
```

### API Information

**SMARD API (Solar Production)**
- Base URL: `https://www.smard.de/app/chart_data`
- Filter ID for Photovoltaic: `4068`
- Timestamps endpoint: `/{filter}/{region}/index_{resolution}.json`
- Timeseries endpoint: `/{filter}/{region}/{filter}_{region}_{resolution}_{timestamp}.json`
- Resolution options: `quarterhour`, `hour`, `day`
- Region: `DE` (Germany)
- No authentication required

**Open-Meteo Forecast API (Stream Mode - Weather)**
- Base URL: `https://api.open-meteo.com/v1`
- Endpoint: `/forecast`
- Supports `past_days` (0-92) and `forecast_days` (0-16)

**Open-Meteo Archive API (Historical Mode - Weather)**
- Base URL: `https://archive-api.open-meteo.com/v1`
- Endpoint: `/archive`
- Parameters: `start_date`, `end_date` (ISO format YYYY-MM-DD)
- Historical data from 1940 to present

**Common Weather Parameters**
- Germany center coordinates: latitude=51.1657, longitude=10.4515
- Required variables: `temperature_2m`, `cloud_cover`, `direct_radiation`
- No authentication required

---

## Step by Step Tasks

### Task 1: Create Service Directory Structure

**Action**: Create the extraction service directory and package structure

```bash
mkdir -p services/extraction/src
touch services/extraction/src/__init__.py
```

---

### Task 2: Create Service pyproject.toml

**File**: `services/extraction/pyproject.toml` (create new)

**Action**: Define service dependencies and metadata

**Content**:
```toml
[project]
name = "extraction"
version = "0.1.0"
description = "Pipeline 1: Data extraction from SMARD and Open-Meteo APIs"
requires-python = ">=3.12"
dependencies = [
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "confluent-kafka>=2.0",
    "httpx>=0.27",
    "structlog>=24.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

---

### Task 3: Create Configuration Module

**File**: `services/extraction/src/config.py` (create new)

**Action**: Define Pydantic settings for the service

**Details**:
```python
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Extraction service configuration."""

    # Kafka
    kafka_bootstrap_servers: str = Field(default="localhost:9092")
    kafka_topic_solar: str = Field(default="solar_production_raw")
    kafka_topic_weather: str = Field(default="weather_raw")

    # SMARD API
    smard_base_url: str = Field(default="https://www.smard.de/app/chart_data")
    smard_filter_solar: str = Field(default="4068")
    smard_region: str = Field(default="DE")
    smard_resolution: str = Field(default="quarterhour")

    # Open-Meteo API
    openmeteo_forecast_url: str = Field(default="https://api.open-meteo.com/v1")
    openmeteo_archive_url: str = Field(default="https://archive-api.open-meteo.com/v1")
    # Germany geographic center
    weather_latitude: float = Field(default=51.1657)
    weather_longitude: float = Field(default=10.4515)

    # Service
    poll_interval_seconds: int = Field(default=900)  # 15 minutes
    historical_start_date: str = Field(default="2025-01-01")  # ISO format
    batch_size: int = Field(default=50)  # Timestamps per batch in historical mode
    rate_limit_delay: float = Field(default=0.5)  # Seconds between API calls

    model_config = {"env_file": "settings.env", "env_file_encoding": "utf-8"}


settings = Settings()
```

---

### Task 4: Create Data Models

**File**: `services/extraction/src/models.py` (create new)

**Action**: Define Pydantic models for solar and weather data

**Details**:
```python
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ExtractionMode(str, Enum):
    """Operating mode for the extraction service."""

    HISTORICAL = "historical"
    STREAM = "stream"


class SolarProductionRecord(BaseModel):
    """Solar energy production record from SMARD API."""

    timestamp: datetime
    production_mw: float = Field(ge=0, description="Solar production in megawatts")
    region: str = Field(default="DE", description="Region code")

    model_config = {"frozen": True}


class WeatherRecord(BaseModel):
    """Weather observation record from Open-Meteo API."""

    timestamp: datetime
    temperature_c: float = Field(description="Temperature in Celsius")
    cloud_cover_pct: float = Field(ge=0, le=100, description="Cloud cover percentage")
    solar_radiation_wm2: float = Field(ge=0, description="Direct solar radiation W/m²")
    latitude: float
    longitude: float

    model_config = {"frozen": True}
```

---

### Task 5: Create SMARD API Client

**File**: `services/extraction/src/smard_client.py` (create new)

**Action**: Implement client to fetch solar production data from SMARD API

**Details**:
- Fetch available timestamps from index endpoint
- `fetch_latest()` for stream mode - gets most recent data
- `fetch_all_since(start_date)` for historical mode - iterates through all timestamps since date
- Parse response and convert to SolarProductionRecord models
- Handle API errors gracefully with structured logging
- Rate limiting for historical batch processing

```python
import time
from datetime import datetime, timezone

import httpx
import structlog

from .config import settings
from .models import SolarProductionRecord

logger = structlog.get_logger()


class SmardClient:
    """Client for fetching solar production data from SMARD API."""

    def __init__(self, base_url: str | None = None):
        self._base_url = base_url or settings.smard_base_url
        self._filter = settings.smard_filter_solar
        self._region = settings.smard_region
        self._resolution = settings.smard_resolution
        self._rate_limit_delay = settings.rate_limit_delay

    def fetch_available_timestamps(self) -> list[int]:
        """Fetch available data timestamps from SMARD API."""
        url = f"{self._base_url}/{self._filter}/{self._region}/index_{self._resolution}.json"

        with httpx.Client(timeout=30.0) as client:
            logger.info("fetching_timestamps", url=url)
            response = client.get(url)
            response.raise_for_status()
            data = response.json()

        timestamps = data.get("timestamps", [])
        logger.info("timestamps_fetched", count=len(timestamps))
        return timestamps

    def fetch_solar_data(self, timestamp: int) -> list[SolarProductionRecord]:
        """Fetch solar production data for a specific timestamp."""
        url = (
            f"{self._base_url}/{self._filter}/{self._region}/"
            f"{self._filter}_{self._region}_{self._resolution}_{timestamp}.json"
        )

        with httpx.Client(timeout=30.0) as client:
            logger.debug("fetching_solar_data", timestamp=timestamp)
            response = client.get(url)
            response.raise_for_status()
            data = response.json()

        return self._parse_response(data)

    def _parse_response(self, data: dict) -> list[SolarProductionRecord]:
        """Parse SMARD API response into SolarProductionRecord models."""
        records = []
        series = data.get("series", [])

        for entry in series:
            if len(entry) >= 2 and entry[1] is not None:
                timestamp_ms, production_mw = entry[0], entry[1]
                record = SolarProductionRecord(
                    timestamp=datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc),
                    production_mw=float(production_mw),
                    region=self._region,
                )
                records.append(record)

        return records

    def fetch_latest(self) -> list[SolarProductionRecord]:
        """Fetch the most recent solar production data (stream mode)."""
        timestamps = self.fetch_available_timestamps()
        if not timestamps:
            logger.warning("no_timestamps_available")
            return []

        latest_timestamp = max(timestamps)
        records = self.fetch_solar_data(latest_timestamp)
        logger.info("latest_solar_data_fetched", record_count=len(records))
        return records

    def fetch_all_since(self, start_date: datetime) -> list[SolarProductionRecord]:
        """Fetch all solar data since a given date (historical mode)."""
        start_timestamp_ms = int(start_date.timestamp() * 1000)

        timestamps = self.fetch_available_timestamps()
        relevant_timestamps = [ts for ts in timestamps if ts >= start_timestamp_ms]
        relevant_timestamps.sort()

        logger.info(
            "historical_fetch_starting",
            start_date=start_date.isoformat(),
            total_timestamps=len(relevant_timestamps),
        )

        all_records = []
        for i, timestamp in enumerate(relevant_timestamps):
            try:
                records = self.fetch_solar_data(timestamp)
                all_records.extend(records)

                if (i + 1) % 10 == 0:
                    logger.info(
                        "historical_fetch_progress",
                        processed=i + 1,
                        total=len(relevant_timestamps),
                        records_so_far=len(all_records),
                    )

                # Rate limiting
                time.sleep(self._rate_limit_delay)

            except httpx.HTTPError as e:
                logger.error(
                    "historical_fetch_error",
                    timestamp=timestamp,
                    error=str(e),
                )
                continue

        logger.info(
            "historical_fetch_completed",
            total_records=len(all_records),
        )
        return all_records
```

---

### Task 6: Create Weather API Client

**File**: `services/extraction/src/weather_client.py` (create new)

**Action**: Implement client to fetch weather data from Open-Meteo API

**Details**:
- `fetch_weather_forecast()` for stream mode - uses Forecast API with past_days
- `fetch_weather_archive()` for historical mode - uses Archive API with date range
- Parse response into WeatherRecord models
- Handle date chunking for large historical ranges

```python
from datetime import datetime, timedelta

import httpx
import structlog

from .config import settings
from .models import WeatherRecord

logger = structlog.get_logger()

# Weather variables to fetch
WEATHER_VARIABLES = "temperature_2m,cloud_cover,direct_radiation"


class WeatherClient:
    """Client for fetching weather data from Open-Meteo API."""

    def __init__(
        self,
        forecast_url: str | None = None,
        archive_url: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
    ):
        self._forecast_url = forecast_url or settings.openmeteo_forecast_url
        self._archive_url = archive_url or settings.openmeteo_archive_url
        self._latitude = latitude or settings.weather_latitude
        self._longitude = longitude or settings.weather_longitude

    def fetch_weather_forecast(
        self,
        past_days: int = 7,
        forecast_days: int = 1,
    ) -> list[WeatherRecord]:
        """Fetch weather data using Forecast API (stream mode)."""
        url = f"{self._forecast_url}/forecast"
        params = {
            "latitude": self._latitude,
            "longitude": self._longitude,
            "hourly": WEATHER_VARIABLES,
            "past_days": past_days,
            "forecast_days": forecast_days,
            "timezone": "UTC",
        }

        with httpx.Client(timeout=30.0) as client:
            logger.info(
                "fetching_weather_forecast",
                past_days=past_days,
                forecast_days=forecast_days,
            )
            response = client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        records = self._parse_response(data)
        logger.info("weather_forecast_fetched", record_count=len(records))
        return records

    def fetch_weather_archive(
        self,
        start_date: datetime,
        end_date: datetime | None = None,
    ) -> list[WeatherRecord]:
        """Fetch historical weather data using Archive API (historical mode)."""
        if end_date is None:
            end_date = datetime.now()

        url = f"{self._archive_url}/archive"
        params = {
            "latitude": self._latitude,
            "longitude": self._longitude,
            "hourly": WEATHER_VARIABLES,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "timezone": "UTC",
        }

        with httpx.Client(timeout=60.0) as client:
            logger.info(
                "fetching_weather_archive",
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d"),
            )
            response = client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        records = self._parse_response(data)
        logger.info("weather_archive_fetched", record_count=len(records))
        return records

    def _parse_response(self, data: dict) -> list[WeatherRecord]:
        """Parse Open-Meteo API response into WeatherRecord models."""
        records = []
        hourly = data.get("hourly", {})

        times = hourly.get("time", [])
        temperatures = hourly.get("temperature_2m", [])
        cloud_covers = hourly.get("cloud_cover", [])
        radiations = hourly.get("direct_radiation", [])

        latitude = data.get("latitude", self._latitude)
        longitude = data.get("longitude", self._longitude)

        for i, time_str in enumerate(times):
            if i < len(temperatures) and i < len(cloud_covers) and i < len(radiations):
                # Handle None values
                temp = temperatures[i] if temperatures[i] is not None else 0.0
                cloud = cloud_covers[i] if cloud_covers[i] is not None else 0.0
                radiation = radiations[i] if radiations[i] is not None else 0.0

                # Parse timestamp - handle both formats
                if "T" in time_str:
                    timestamp = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                else:
                    timestamp = datetime.fromisoformat(f"{time_str}:00+00:00")

                record = WeatherRecord(
                    timestamp=timestamp,
                    temperature_c=float(temp),
                    cloud_cover_pct=float(cloud),
                    solar_radiation_wm2=float(radiation),
                    latitude=latitude,
                    longitude=longitude,
                )
                records.append(record)

        return records
```

---

### Task 7: Create Kafka Producer Service

**File**: `services/extraction/src/producer.py` (create new)

**Action**: Implement Kafka producer for publishing data to topics

**Details**:
- Initialize producer with idempotence enabled
- Produce records to specified topics with timestamp as key
- Handle delivery callbacks and errors
- Flush messages after producing
- Support batch production for historical mode

```python
import json

import structlog
from confluent_kafka import KafkaError, Producer

from .config import settings
from .models import SolarProductionRecord, WeatherRecord

logger = structlog.get_logger()


class KafkaProducerService:
    """Kafka producer for publishing extraction data."""

    def __init__(self, bootstrap_servers: str | None = None):
        self._bootstrap_servers = bootstrap_servers or settings.kafka_bootstrap_servers
        self._producer = Producer({
            "bootstrap.servers": self._bootstrap_servers,
            "enable.idempotence": True,
            "acks": "all",
            "retries": 3,
            "retry.backoff.ms": 1000,
            "linger.ms": 100,  # Batch messages for efficiency
            "batch.num.messages": 1000,
        })
        self._delivery_errors: list[str] = []

    def _delivery_callback(self, err: KafkaError | None, msg) -> None:
        """Callback for message delivery reports."""
        if err is not None:
            error_msg = f"Delivery failed: {err}"
            self._delivery_errors.append(error_msg)
            logger.error(
                "kafka_delivery_failed",
                error=str(err),
                topic=msg.topic() if msg else "unknown",
            )

    def produce_solar_records(
        self,
        records: list[SolarProductionRecord],
        topic: str | None = None,
    ) -> int:
        """Produce solar production records to Kafka."""
        topic = topic or settings.kafka_topic_solar
        self._delivery_errors = []

        for record in records:
            key = record.timestamp.isoformat().encode("utf-8")
            value = json.dumps({
                "timestamp": record.timestamp.isoformat(),
                "production_mw": record.production_mw,
                "region": record.region,
            }).encode("utf-8")

            self._producer.produce(
                topic=topic,
                key=key,
                value=value,
                callback=self._delivery_callback,
            )

            # Poll to trigger callbacks and avoid queue buildup
            self._producer.poll(0)

        self._producer.flush(timeout=60)

        success_count = len(records) - len(self._delivery_errors)
        logger.info(
            "solar_records_produced",
            topic=topic,
            total=len(records),
            success=success_count,
            errors=len(self._delivery_errors),
        )
        return success_count

    def produce_weather_records(
        self,
        records: list[WeatherRecord],
        topic: str | None = None,
    ) -> int:
        """Produce weather records to Kafka."""
        topic = topic or settings.kafka_topic_weather
        self._delivery_errors = []

        for record in records:
            key = record.timestamp.isoformat().encode("utf-8")
            value = json.dumps({
                "timestamp": record.timestamp.isoformat(),
                "temperature_c": record.temperature_c,
                "cloud_cover_pct": record.cloud_cover_pct,
                "solar_radiation_wm2": record.solar_radiation_wm2,
                "latitude": record.latitude,
                "longitude": record.longitude,
            }).encode("utf-8")

            self._producer.produce(
                topic=topic,
                key=key,
                value=value,
                callback=self._delivery_callback,
            )

            # Poll to trigger callbacks
            self._producer.poll(0)

        self._producer.flush(timeout=60)

        success_count = len(records) - len(self._delivery_errors)
        logger.info(
            "weather_records_produced",
            topic=topic,
            total=len(records),
            success=success_count,
            errors=len(self._delivery_errors),
        )
        return success_count

    def close(self) -> None:
        """Flush and close the producer."""
        self._producer.flush(timeout=30)
```

---

### Task 8: Create Main Entry Point

**File**: `services/extraction/src/main.py` (create new)

**Action**: Implement the main entry point with CLI argument parsing and mode handling

**Details**:
- Parse `--mode` argument (historical or stream)
- Configure structlog for JSON logging
- Historical mode: fetch all data since 2025-01-01, produce to Kafka, exit
- Stream mode: run extraction loop with configurable poll interval
- Handle graceful shutdown on SIGINT/SIGTERM

```python
import argparse
import signal
import sys
import time
from datetime import datetime, timezone

import structlog

from .config import settings
from .models import ExtractionMode
from .producer import KafkaProducerService
from .smard_client import SmardClient
from .weather_client import WeatherClient

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(structlog.INFO),
)

logger = structlog.get_logger()

# Global flag for graceful shutdown
_shutdown_requested = False


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    global _shutdown_requested
    logger.info("shutdown_requested", signal=signum)
    _shutdown_requested = True


def run_historical_mode(
    smard_client: SmardClient,
    weather_client: WeatherClient,
    producer: KafkaProducerService,
) -> None:
    """Run historical backfill mode - fetch all data since start date, then exit."""
    start_date = datetime.fromisoformat(settings.historical_start_date).replace(
        tzinfo=timezone.utc
    )
    end_date = datetime.now(timezone.utc)

    logger.info(
        "historical_mode_starting",
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
    )

    # Fetch and produce solar data
    logger.info("fetching_historical_solar_data")
    try:
        solar_records = smard_client.fetch_all_since(start_date)
        if solar_records:
            producer.produce_solar_records(solar_records)
            logger.info("historical_solar_data_complete", records=len(solar_records))
    except Exception as e:
        logger.error("historical_solar_extraction_failed", error=str(e), exc_info=True)

    # Fetch and produce weather data
    logger.info("fetching_historical_weather_data")
    try:
        weather_records = weather_client.fetch_weather_archive(
            start_date=start_date,
            end_date=end_date,
        )
        if weather_records:
            producer.produce_weather_records(weather_records)
            logger.info("historical_weather_data_complete", records=len(weather_records))
    except Exception as e:
        logger.error("historical_weather_extraction_failed", error=str(e), exc_info=True)

    logger.info("historical_mode_completed")


def run_stream_extraction_cycle(
    smard_client: SmardClient,
    weather_client: WeatherClient,
    producer: KafkaProducerService,
) -> None:
    """Run a single extraction cycle for stream mode."""
    # Fetch and produce solar data
    try:
        solar_records = smard_client.fetch_latest()
        if solar_records:
            producer.produce_solar_records(solar_records)
    except Exception as e:
        logger.error("solar_extraction_failed", error=str(e), exc_info=True)

    # Fetch and produce weather data (7 days back + 1 day forecast)
    try:
        weather_records = weather_client.fetch_weather_forecast(
            past_days=7,
            forecast_days=1,
        )
        if weather_records:
            producer.produce_weather_records(weather_records)
    except Exception as e:
        logger.error("weather_extraction_failed", error=str(e), exc_info=True)


def run_stream_mode(
    smard_client: SmardClient,
    weather_client: WeatherClient,
    producer: KafkaProducerService,
) -> None:
    """Run continuous stream mode - poll at regular intervals."""
    global _shutdown_requested

    logger.info(
        "stream_mode_starting",
        poll_interval=settings.poll_interval_seconds,
    )

    while not _shutdown_requested:
        run_stream_extraction_cycle(smard_client, weather_client, producer)

        # Sleep with periodic checks for shutdown
        for _ in range(settings.poll_interval_seconds):
            if _shutdown_requested:
                break
            time.sleep(1)

    logger.info("stream_mode_stopped")


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Extraction pipeline for solar and weather data"
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=[m.value for m in ExtractionMode],
        default=ExtractionMode.STREAM.value,
        help="Operating mode: 'historical' (backfill since 2025-01-01, then exit) "
        "or 'stream' (continuous polling, default)",
    )
    return parser.parse_args()


def main() -> None:
    """Main entry point for the extraction service."""
    global _shutdown_requested

    # Parse arguments
    args = parse_args()
    mode = ExtractionMode(args.mode)

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info(
        "extraction_service_starting",
        mode=mode.value,
        kafka_servers=settings.kafka_bootstrap_servers,
        smard_base_url=settings.smard_base_url,
    )

    # Initialize clients
    smard_client = SmardClient()
    weather_client = WeatherClient()
    producer = KafkaProducerService()

    try:
        if mode == ExtractionMode.HISTORICAL:
            run_historical_mode(smard_client, weather_client, producer)
        else:
            run_stream_mode(smard_client, weather_client, producer)
    finally:
        logger.info("extraction_service_stopping")
        producer.close()
        logger.info("extraction_service_stopped")


if __name__ == "__main__":
    main()
```

---

### Task 9: Create Example Settings File

**File**: `services/extraction/settings.env.example` (create new)

**Action**: Create example environment configuration file

**Content**:
```env
# Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_TOPIC_SOLAR=solar_production_raw
KAFKA_TOPIC_WEATHER=weather_raw

# SMARD API Configuration
SMARD_BASE_URL=https://www.smard.de/app/chart_data
SMARD_FILTER_SOLAR=4068
SMARD_REGION=DE
SMARD_RESOLUTION=quarterhour

# Open-Meteo API Configuration
OPENMETEO_FORECAST_URL=https://api.open-meteo.com/v1
OPENMETEO_ARCHIVE_URL=https://archive-api.open-meteo.com/v1
WEATHER_LATITUDE=51.1657
WEATHER_LONGITUDE=10.4515

# Service Configuration
POLL_INTERVAL_SECONDS=900
HISTORICAL_START_DATE=2025-01-01
BATCH_SIZE=50
RATE_LIMIT_DELAY=0.5
```

---

### Task 10: Update Root pyproject.toml

**File**: `pyproject.toml` (modify)

**Action**: Add extraction service as workspace member

**Details**: Add to the existing pyproject.toml:
```toml
[tool.uv.workspace]
members = ["services/extraction"]
```

---

### Task 11: Create Test Directory Structure

**Action**: Create test directories and init files

```bash
mkdir -p tests/unit/extraction
touch tests/__init__.py
touch tests/unit/__init__.py
touch tests/unit/extraction/__init__.py
```

---

### Task 12: Create Test Fixtures

**File**: `tests/conftest.py` (create new)

**Action**: Create shared test fixtures

**Content**:
```python
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_kafka_producer():
    """Mock Kafka producer for testing."""
    with patch("confluent_kafka.Producer") as mock:
        producer_instance = MagicMock()
        mock.return_value = producer_instance
        yield producer_instance


@pytest.fixture
def sample_smard_response():
    """Sample SMARD API response for testing."""
    return {
        "series": [
            [1704067200000, 1500.5],  # 2024-01-01 00:00:00 UTC
            [1704070800000, 1600.0],  # 2024-01-01 01:00:00 UTC
            [1704074400000, None],    # Null value should be skipped
            [1704078000000, 1800.25], # 2024-01-01 03:00:00 UTC
        ]
    }


@pytest.fixture
def sample_weather_response():
    """Sample Open-Meteo API response for testing."""
    return {
        "latitude": 51.1657,
        "longitude": 10.4515,
        "hourly": {
            "time": [
                "2024-01-01T00:00",
                "2024-01-01T01:00",
                "2024-01-01T02:00",
            ],
            "temperature_2m": [5.5, 5.2, 4.8],
            "cloud_cover": [75, 80, 85],
            "direct_radiation": [0, 0, 50],
        }
    }


@pytest.fixture
def sample_timestamps_response():
    """Sample SMARD timestamps response for testing."""
    return {
        "timestamps": [1704067200000, 1704153600000, 1704240000000]
    }
```

---

### Task 13: Create SMARD Client Tests

**File**: `tests/unit/extraction/test_smard_client.py` (create new)

**Action**: Create unit tests for SMARD client

**Content**:
```python
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from services.extraction.src.models import SolarProductionRecord
from services.extraction.src.smard_client import SmardClient


class TestSmardClient:
    """Tests for SmardClient."""

    def test_parse_response_creates_records(self, sample_smard_response):
        """_parse_response should create SolarProductionRecord from valid data."""
        client = SmardClient()
        records = client._parse_response(sample_smard_response)

        assert len(records) == 3  # One null value skipped
        assert all(isinstance(r, SolarProductionRecord) for r in records)
        assert records[0].production_mw == 1500.5
        assert records[0].region == "DE"

    def test_parse_response_skips_null_values(self, sample_smard_response):
        """_parse_response should skip entries with null production values."""
        client = SmardClient()
        records = client._parse_response(sample_smard_response)

        assert len(records) == 3
        production_values = [r.production_mw for r in records]
        assert None not in production_values

    def test_parse_response_handles_empty_series(self):
        """_parse_response should handle empty series gracefully."""
        client = SmardClient()
        records = client._parse_response({"series": []})

        assert records == []

    @patch("httpx.Client")
    def test_fetch_available_timestamps(
        self, mock_client_class, sample_timestamps_response
    ):
        """fetch_available_timestamps should return list of timestamps."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.json.return_value = sample_timestamps_response
        mock_client.get.return_value = mock_response

        client = SmardClient()
        timestamps = client.fetch_available_timestamps()

        assert len(timestamps) == 3
        assert timestamps == sample_timestamps_response["timestamps"]

    @patch("httpx.Client")
    def test_fetch_latest(self, mock_client_class, sample_smard_response, sample_timestamps_response):
        """fetch_latest should return records from most recent timestamp."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client

        # First call returns timestamps, second returns data
        mock_response_timestamps = MagicMock()
        mock_response_timestamps.json.return_value = sample_timestamps_response
        mock_response_data = MagicMock()
        mock_response_data.json.return_value = sample_smard_response

        mock_client.get.side_effect = [mock_response_timestamps, mock_response_data]

        client = SmardClient()
        records = client.fetch_latest()

        assert len(records) == 3
        assert all(isinstance(r, SolarProductionRecord) for r in records)
```

---

### Task 14: Create Weather Client Tests

**File**: `tests/unit/extraction/test_weather_client.py` (create new)

**Action**: Create unit tests for Weather client

**Content**:
```python
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from services.extraction.src.models import WeatherRecord
from services.extraction.src.weather_client import WeatherClient


class TestWeatherClient:
    """Tests for WeatherClient."""

    def test_parse_response_creates_records(self, sample_weather_response):
        """_parse_response should create WeatherRecord from valid data."""
        client = WeatherClient()
        records = client._parse_response(sample_weather_response)

        assert len(records) == 3
        assert all(isinstance(r, WeatherRecord) for r in records)
        assert records[0].temperature_c == 5.5
        assert records[0].cloud_cover_pct == 75
        assert records[0].solar_radiation_wm2 == 0

    def test_parse_response_includes_coordinates(self, sample_weather_response):
        """_parse_response should include latitude/longitude in records."""
        client = WeatherClient()
        records = client._parse_response(sample_weather_response)

        assert records[0].latitude == 51.1657
        assert records[0].longitude == 10.4515

    def test_parse_response_handles_empty_data(self):
        """_parse_response should handle empty hourly data gracefully."""
        client = WeatherClient()
        records = client._parse_response({"hourly": {}})

        assert records == []

    @patch("httpx.Client")
    def test_fetch_weather_forecast(self, mock_client_class, sample_weather_response):
        """fetch_weather_forecast should use forecast API."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.json.return_value = sample_weather_response
        mock_client.get.return_value = mock_response

        client = WeatherClient()
        records = client.fetch_weather_forecast(past_days=7, forecast_days=1)

        assert len(records) == 3
        # Verify forecast URL was used
        call_args = mock_client.get.call_args
        assert "forecast" in call_args.args[0]

    @patch("httpx.Client")
    def test_fetch_weather_archive(self, mock_client_class, sample_weather_response):
        """fetch_weather_archive should use archive API with date range."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.json.return_value = sample_weather_response
        mock_client.get.return_value = mock_response

        client = WeatherClient()
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 1, 7, tzinfo=timezone.utc)
        records = client.fetch_weather_archive(start_date=start, end_date=end)

        assert len(records) == 3
        # Verify archive URL was used
        call_args = mock_client.get.call_args
        assert "archive" in call_args.args[0]
        assert call_args.kwargs["params"]["start_date"] == "2025-01-01"

    def test_init_with_custom_coordinates(self):
        """WeatherClient should accept custom coordinates."""
        client = WeatherClient(latitude=52.52, longitude=13.405)

        assert client._latitude == 52.52
        assert client._longitude == 13.405
```

---

### Task 15: Create Producer Tests

**File**: `tests/unit/extraction/test_producer.py` (create new)

**Action**: Create unit tests for Kafka producer

**Content**:
```python
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, call, patch

from services.extraction.src.models import SolarProductionRecord, WeatherRecord
from services.extraction.src.producer import KafkaProducerService


class TestKafkaProducerService:
    """Tests for KafkaProducerService."""

    @patch("confluent_kafka.Producer")
    def test_produce_solar_records(self, mock_producer_class):
        """produce_solar_records should produce all records to Kafka."""
        mock_producer = MagicMock()
        mock_producer_class.return_value = mock_producer

        records = [
            SolarProductionRecord(
                timestamp=datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
                production_mw=1500.0,
                region="DE",
            ),
            SolarProductionRecord(
                timestamp=datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
                production_mw=1600.0,
                region="DE",
            ),
        ]

        producer = KafkaProducerService()
        count = producer.produce_solar_records(records, topic="test_topic")

        assert mock_producer.produce.call_count == 2
        assert count == 2

    @patch("confluent_kafka.Producer")
    def test_produce_weather_records(self, mock_producer_class):
        """produce_weather_records should produce all records to Kafka."""
        mock_producer = MagicMock()
        mock_producer_class.return_value = mock_producer

        records = [
            WeatherRecord(
                timestamp=datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
                temperature_c=5.5,
                cloud_cover_pct=75.0,
                solar_radiation_wm2=0.0,
                latitude=51.1657,
                longitude=10.4515,
            ),
        ]

        producer = KafkaProducerService()
        count = producer.produce_weather_records(records, topic="test_topic")

        assert mock_producer.produce.call_count == 1
        assert count == 1

    @patch("confluent_kafka.Producer")
    def test_produce_calls_flush(self, mock_producer_class):
        """Producer should flush after producing records."""
        mock_producer = MagicMock()
        mock_producer_class.return_value = mock_producer

        records = [
            SolarProductionRecord(
                timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
                production_mw=1500.0,
                region="DE",
            ),
        ]

        producer = KafkaProducerService()
        producer.produce_solar_records(records)

        mock_producer.flush.assert_called()
```

---

## Testing Strategy

### Unit Tests
- Test SMARD client response parsing and API methods
- Test Weather client with both Forecast and Archive APIs
- Test Kafka producer message production
- Mock external dependencies (HTTP, Kafka)

### Integration Tests (future)
- Test actual API calls to SMARD and Open-Meteo
- Test Kafka round-trip with local cluster
- Test full extraction cycle in both modes

### Test Locations
```
tests/
├── conftest.py
└── unit/
    └── extraction/
        ├── __init__.py
        ├── test_smard_client.py
        ├── test_weather_client.py
        └── test_producer.py
```

---

## Validation Commands

Run these commands in order to validate the implementation:

```bash
# 1. Sync dependencies
uv sync

# 2. Lint check
uv run ruff check .

# 3. Format check
uv run ruff format --check .

# 4. Format code (if needed)
uv run ruff format .

# 5. Run tests
uv run pytest tests/unit/extraction/ -v

# 6. Run tests with coverage
uv run pytest tests/unit/extraction/ --cov=services/extraction/src --cov-report=term-missing

# 7. Test service import (verify no import errors)
uv run python -c "from services.extraction.src.main import main; print('Import OK')"
```

---

## Integration Notes

### Kafka Topics
The service produces to two topics:
- `solar_production_raw` - Solar energy production data
- `weather_raw` - Weather observations

These topics should be auto-created by Kafka (configured with `auto.create.topics.enable: true`).

### Running the Service

```bash
# Historical mode - backfill since 2025-01-01, then exit
uv run python -m services.extraction.src.main --mode historical

# Stream mode - continuous polling (default)
uv run python -m services.extraction.src.main --mode stream

# Or simply (defaults to stream)
uv run python -m services.extraction.src.main
```

### Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                    EXTRACTION PIPELINE                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐         ┌──────────────────┐                     │
│  │  SMARD API   │────────▶│  SmardClient     │──┐                  │
│  │  (Solar)     │         │  fetch_latest()  │  │                  │
│  └──────────────┘         │  fetch_all_since │  │                  │
│                           └──────────────────┘  │                  │
│                                                 ▼                  │
│                                          ┌─────────────┐           │
│                                          │   Kafka     │           │
│                                          │  Producer   │           │
│                                          └─────────────┘           │
│                                                 │                  │
│  ┌──────────────┐         ┌──────────────────┐  │                  │
│  │ Open-Meteo   │────────▶│  WeatherClient   │──┘                  │
│  │ Forecast API │         │  fetch_forecast()│                     │
│  │ Archive API  │         │  fetch_archive() │                     │
│  └──────────────┘         └──────────────────┘                     │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │           KAFKA               │
                    ├───────────────┬───────────────┤
                    │ solar_        │ weather_raw   │
                    │ production_raw│               │
                    └───────────────┴───────────────┘
```

### Docker (future task)
A Dockerfile will be added in `dockers/extraction.Dockerfile` for containerized deployment.

### Kubernetes (future task)
Kustomize manifests will be added in `deployments/dev/services/extraction/` for K8s deployment.

---

## Confirmation

- ✅ Feature name created: `extraction-pipeline`
- ✅ Plan saved to `plans/extraction-pipeline.md`
- ✅ All tasks are explicit with file paths
- ✅ Validation commands are exact
- ✅ Supports both `--mode historical` and `--mode stream`
- ✅ Another agent could execute this without context

**Next step**: Run `/execute plans/extraction-pipeline.md` to implement this feature
