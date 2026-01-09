import json
import sys
from datetime import timezone
from unittest.mock import MagicMock, patch

import pytest


class TestKafkaConsumerService:
    """Tests for KafkaConsumerService."""

    @pytest.fixture(autouse=True)
    def mock_confluent_kafka(self):
        """Mock confluent_kafka.Consumer before importing the service."""
        mock_consumer_instance = MagicMock()

        with patch.dict(sys.modules, {"confluent_kafka": MagicMock()}):
            mock_consumer_class = MagicMock(return_value=mock_consumer_instance)
            mock_kafka_error = MagicMock()
            mock_kafka_error._PARTITION_EOF = -191

            sys.modules["confluent_kafka"].Consumer = mock_consumer_class
            sys.modules["confluent_kafka"].KafkaError = mock_kafka_error

            # Import fresh
            if "services.features.src.consumer" in sys.modules:
                del sys.modules["services.features.src.consumer"]

            from services.features.src.consumer import KafkaConsumerService

            self.KafkaConsumerService = KafkaConsumerService
            self.mock_consumer = mock_consumer_instance
            self.mock_consumer_class = mock_consumer_class

            yield

    def test_consume_batch_returns_parsed_solar_records(self):
        """consume_batch should parse solar records correctly."""
        solar_msg = MagicMock()
        solar_msg.error.return_value = None
        solar_msg.topic.return_value = "solar_production_raw"
        solar_msg.value.return_value = json.dumps(
            {
                "timestamp": "2025-01-15T12:00:00+00:00",
                "production_mw": 1500.0,
                "region": "DE",
            }
        ).encode("utf-8")

        self.mock_consumer.consume.return_value = [solar_msg]

        consumer = self.KafkaConsumerService()
        solar_records, weather_records = consumer.consume_batch()

        assert len(solar_records) == 1
        assert len(weather_records) == 0
        assert solar_records[0].production_mw == 1500.0
        assert solar_records[0].region == "DE"

    def test_consume_batch_returns_parsed_weather_records(self):
        """consume_batch should parse weather records correctly."""
        weather_msg = MagicMock()
        weather_msg.error.return_value = None
        weather_msg.topic.return_value = "weather_raw"
        weather_msg.value.return_value = json.dumps(
            {
                "timestamp": "2025-01-15T12:00:00+00:00",
                "temperature_c": 10.5,
                "cloud_cover_pct": 75.0,
                "solar_radiation_wm2": 350.0,
                "latitude": 51.1657,
                "longitude": 10.4515,
            }
        ).encode("utf-8")

        self.mock_consumer.consume.return_value = [weather_msg]

        consumer = self.KafkaConsumerService()
        solar_records, weather_records = consumer.consume_batch()

        assert len(solar_records) == 0
        assert len(weather_records) == 1
        assert weather_records[0].temperature_c == 10.5
        assert weather_records[0].cloud_cover_pct == 75.0

    def test_consume_batch_handles_empty_response(self):
        """consume_batch should handle empty message list."""
        self.mock_consumer.consume.return_value = []

        consumer = self.KafkaConsumerService()
        solar_records, weather_records = consumer.consume_batch()

        assert len(solar_records) == 0
        assert len(weather_records) == 0

    def test_consume_batch_handles_none_messages(self):
        """consume_batch should skip None messages."""
        self.mock_consumer.consume.return_value = [None, None]

        consumer = self.KafkaConsumerService()
        solar_records, weather_records = consumer.consume_batch()

        assert len(solar_records) == 0
        assert len(weather_records) == 0

    def test_commit_calls_consumer_commit(self):
        """commit should call the underlying consumer commit."""
        consumer = self.KafkaConsumerService()
        consumer.commit()

        self.mock_consumer.commit.assert_called_once()

    def test_close_calls_consumer_close(self):
        """close should call the underlying consumer close."""
        consumer = self.KafkaConsumerService()
        consumer.close()

        self.mock_consumer.close.assert_called_once()

    def test_handles_malformed_json_gracefully(self):
        """consume_batch should handle malformed JSON without crashing."""
        bad_msg = MagicMock()
        bad_msg.error.return_value = None
        bad_msg.topic.return_value = "solar_production_raw"
        bad_msg.value.return_value = b"not valid json"
        bad_msg.offset.return_value = 123

        self.mock_consumer.consume.return_value = [bad_msg]

        consumer = self.KafkaConsumerService()
        solar_records, weather_records = consumer.consume_batch()

        # Should not crash, just return empty
        assert len(solar_records) == 0
        assert len(weather_records) == 0

    def test_handles_missing_fields_gracefully(self):
        """consume_batch should handle records with missing fields."""
        incomplete_msg = MagicMock()
        incomplete_msg.error.return_value = None
        incomplete_msg.topic.return_value = "solar_production_raw"
        incomplete_msg.value.return_value = json.dumps(
            {
                "timestamp": "2025-01-15T12:00:00+00:00",
                # missing production_mw
            }
        ).encode("utf-8")
        incomplete_msg.offset.return_value = 123

        self.mock_consumer.consume.return_value = [incomplete_msg]

        consumer = self.KafkaConsumerService()
        solar_records, weather_records = consumer.consume_batch()

        # Should skip invalid records
        assert len(solar_records) == 0
        assert len(weather_records) == 0

    def test_handles_kafka_error(self):
        """consume_batch should handle Kafka errors gracefully."""
        error_msg = MagicMock()
        error = MagicMock()
        error.code.return_value = -100  # Not partition EOF
        error_msg.error.return_value = error
        error_msg.topic.return_value = "solar_production_raw"

        self.mock_consumer.consume.return_value = [error_msg]

        consumer = self.KafkaConsumerService()
        solar_records, weather_records = consumer.consume_batch()

        assert len(solar_records) == 0
        assert len(weather_records) == 0

    def test_handles_partition_eof(self):
        """consume_batch should handle partition EOF gracefully."""
        eof_msg = MagicMock()
        error = MagicMock()
        error.code.return_value = -191  # PARTITION_EOF
        eof_msg.error.return_value = error
        eof_msg.topic.return_value = "solar_production_raw"
        eof_msg.partition.return_value = 0

        self.mock_consumer.consume.return_value = [eof_msg]

        consumer = self.KafkaConsumerService()
        solar_records, weather_records = consumer.consume_batch()

        # Should not crash
        assert len(solar_records) == 0
        assert len(weather_records) == 0

    def test_parses_timestamp_without_timezone(self):
        """consume_batch should handle timestamps without timezone info."""
        solar_msg = MagicMock()
        solar_msg.error.return_value = None
        solar_msg.topic.return_value = "solar_production_raw"
        solar_msg.value.return_value = json.dumps(
            {
                "timestamp": "2025-01-15T12:00:00",  # No timezone
                "production_mw": 1500.0,
                "region": "DE",
            }
        ).encode("utf-8")

        self.mock_consumer.consume.return_value = [solar_msg]

        consumer = self.KafkaConsumerService()
        solar_records, weather_records = consumer.consume_batch()

        assert len(solar_records) == 1
        assert solar_records[0].timestamp.tzinfo == timezone.utc
