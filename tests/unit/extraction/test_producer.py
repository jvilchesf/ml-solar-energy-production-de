import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from services.extraction.src.models import SolarProductionRecord, WeatherRecord


class TestKafkaProducerService:
    """Tests for KafkaProducerService."""

    @pytest.fixture(autouse=True)
    def mock_confluent_kafka(self):
        """Mock confluent_kafka.Producer before importing the service."""
        mock_producer_instance = MagicMock()

        with patch.dict(sys.modules, {"confluent_kafka": MagicMock()}):
            # Create mock Producer class
            mock_producer_class = MagicMock(return_value=mock_producer_instance)

            # Patch the Producer in confluent_kafka module
            sys.modules["confluent_kafka"].Producer = mock_producer_class
            sys.modules["confluent_kafka"].KafkaError = MagicMock

            # Import fresh
            if "services.extraction.src.producer" in sys.modules:
                del sys.modules["services.extraction.src.producer"]

            from services.extraction.src.producer import KafkaProducerService

            self.KafkaProducerService = KafkaProducerService
            self.mock_producer = mock_producer_instance
            self.mock_producer_class = mock_producer_class

            yield

    def test_produce_solar_records(self):
        """produce_solar_records should produce all records to Kafka."""
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

        producer = self.KafkaProducerService()
        count = producer.produce_solar_records(records, topic="test_topic")

        assert self.mock_producer.produce.call_count == 2
        assert count == 2

    def test_produce_weather_records(self):
        """produce_weather_records should produce all records to Kafka."""
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

        producer = self.KafkaProducerService()
        count = producer.produce_weather_records(records, topic="test_topic")

        assert self.mock_producer.produce.call_count == 1
        assert count == 1

    def test_produce_calls_flush(self):
        """Producer should flush after producing records."""
        records = [
            SolarProductionRecord(
                timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
                production_mw=1500.0,
                region="DE",
            ),
        ]

        producer = self.KafkaProducerService()
        producer.produce_solar_records(records)

        self.mock_producer.flush.assert_called()
