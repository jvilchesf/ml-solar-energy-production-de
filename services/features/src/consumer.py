import json
from datetime import datetime, timezone

import structlog
from confluent_kafka import Consumer, KafkaError

from .config import settings
from .models import SolarProductionRecord, WeatherRecord

logger = structlog.get_logger()


class KafkaConsumerService:
    """Kafka consumer for solar and weather data topics."""

    def __init__(
        self,
        bootstrap_servers: str | None = None,
        consumer_group: str | None = None,
    ):
        self._bootstrap_servers = bootstrap_servers or settings.kafka_bootstrap_servers
        self._consumer_group = consumer_group or settings.kafka_consumer_group
        self._topics = [settings.kafka_topic_solar, settings.kafka_topic_weather]

        self._consumer = Consumer(
            {
                "bootstrap.servers": self._bootstrap_servers,
                "group.id": self._consumer_group,
                "auto.offset.reset": "earliest",
                "enable.auto.commit": False,
            }
        )
        self._consumer.subscribe(self._topics)

        logger.info(
            "kafka_consumer_initialized",
            bootstrap_servers=self._bootstrap_servers,
            consumer_group=self._consumer_group,
            topics=self._topics,
        )

    def consume_batch(
        self,
        max_messages: int = 100,
        timeout: float = 1.0,
    ) -> tuple[list[SolarProductionRecord], list[WeatherRecord]]:
        """Consume a batch of messages from both topics.

        Returns a tuple of (solar_records, weather_records).
        """
        solar_records: list[SolarProductionRecord] = []
        weather_records: list[WeatherRecord] = []

        messages = self._consumer.consume(num_messages=max_messages, timeout=timeout)

        for msg in messages:
            if msg is None:
                continue

            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    logger.debug(
                        "kafka_partition_eof",
                        topic=msg.topic(),
                        partition=msg.partition(),
                    )
                else:
                    logger.error(
                        "kafka_consume_error",
                        error=str(msg.error()),
                        topic=msg.topic(),
                    )
                continue

            try:
                value = json.loads(msg.value().decode("utf-8"))
                topic = msg.topic()

                if topic == settings.kafka_topic_solar:
                    record = self._parse_solar_record(value)
                    if record:
                        solar_records.append(record)
                elif topic == settings.kafka_topic_weather:
                    record = self._parse_weather_record(value)
                    if record:
                        weather_records.append(record)

            except json.JSONDecodeError as e:
                logger.error(
                    "kafka_json_decode_error",
                    error=str(e),
                    topic=msg.topic(),
                    offset=msg.offset(),
                )
            except Exception as e:
                logger.error(
                    "kafka_message_parse_error",
                    error=str(e),
                    topic=msg.topic(),
                    offset=msg.offset(),
                )

        if solar_records or weather_records:
            logger.debug(
                "kafka_batch_consumed",
                solar_count=len(solar_records),
                weather_count=len(weather_records),
            )

        return solar_records, weather_records

    def _parse_solar_record(self, data: dict) -> SolarProductionRecord | None:
        """Parse a solar production record from JSON data."""
        try:
            timestamp = datetime.fromisoformat(data["timestamp"])
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)

            return SolarProductionRecord(
                timestamp=timestamp,
                production_mw=data["production_mw"],
                region=data.get("region", "DE"),
            )
        except (KeyError, ValueError) as e:
            logger.error("solar_record_parse_error", error=str(e), data=data)
            return None

    def _parse_weather_record(self, data: dict) -> WeatherRecord | None:
        """Parse a weather record from JSON data."""
        try:
            timestamp = datetime.fromisoformat(data["timestamp"])
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)

            return WeatherRecord(
                timestamp=timestamp,
                temperature_c=data["temperature_c"],
                cloud_cover_pct=data["cloud_cover_pct"],
                solar_radiation_wm2=data["solar_radiation_wm2"],
                latitude=data["latitude"],
                longitude=data["longitude"],
            )
        except (KeyError, ValueError) as e:
            logger.error("weather_record_parse_error", error=str(e), data=data)
            return None

    def commit(self) -> None:
        """Commit current offsets."""
        self._consumer.commit()
        logger.debug("kafka_offsets_committed")

    def close(self) -> None:
        """Close the consumer."""
        self._consumer.close()
        logger.info("kafka_consumer_closed")
