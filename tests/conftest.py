from unittest.mock import MagicMock, patch

import pytest


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
            [1704074400000, None],  # Null value should be skipped
            [1704078000000, 1800.25],  # 2024-01-01 03:00:00 UTC
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
        },
    }


@pytest.fixture
def sample_timestamps_response():
    """Sample SMARD timestamps response for testing."""
    return {"timestamps": [1704067200000, 1704153600000, 1704240000000]}
