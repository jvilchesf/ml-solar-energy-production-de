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
        self._producer = Producer(
            {
                "bootstrap.servers": self._bootstrap_servers,
                "enable.idempotence": True,
                "acks": "all",
                "retries": 3,
                "retry.backoff.ms": 1000,
                "linger.ms": 100,  # Batch messages for efficiency
                "batch.num.messages": 1000,
            }
        )
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
            value = json.dumps(
                {
                    "timestamp": record.timestamp.isoformat(),
                    "production_mw": record.production_mw,
                    "region": record.region,
                }
            ).encode("utf-8")

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
            value = json.dumps(
                {
                    "timestamp": record.timestamp.isoformat(),
                    "temperature_c": record.temperature_c,
                    "cloud_cover_pct": record.cloud_cover_pct,
                    "solar_radiation_wm2": record.solar_radiation_wm2,
                    "latitude": record.latitude,
                    "longitude": record.longitude,
                }
            ).encode("utf-8")

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
