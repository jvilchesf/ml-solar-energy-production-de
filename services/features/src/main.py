import argparse
import signal
import time
from datetime import datetime, timedelta, timezone

import structlog

from .config import settings
from .consumer import KafkaConsumerService
from .feature_engineer import FeatureEngineer
from .models import FeatureMode
from .risingwave_client import RisingWaveClient

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
)

logger = structlog.get_logger()

# Global flag for graceful shutdown
_shutdown_requested = False


def signal_handler(signum: int, frame) -> None:
    """Handle shutdown signals."""
    global _shutdown_requested
    logger.info("shutdown_requested", signal=signum)
    _shutdown_requested = True


def run_historical_mode(
    consumer: KafkaConsumerService,
    engineer: FeatureEngineer,
    risingwave: RisingWaveClient,
) -> None:
    """Run historical backfill mode - process all data then exit."""
    global _shutdown_requested

    logger.info("historical_mode_starting")

    # Ensure table exists
    risingwave.ensure_table_exists()

    total_solar = 0
    total_weather = 0
    total_features = 0
    empty_batches = 0
    max_empty_batches = 10  # Exit after this many consecutive empty batches

    while not _shutdown_requested and empty_batches < max_empty_batches:
        # Consume batch
        solar_records, weather_records = consumer.consume_batch(
            max_messages=settings.batch_size,
            timeout=2.0,
        )

        if not solar_records and not weather_records:
            empty_batches += 1
            logger.debug("empty_batch", consecutive_empty=empty_batches)
            continue

        empty_batches = 0
        total_solar += len(solar_records)
        total_weather += len(weather_records)

        # Add to feature engineer
        if solar_records:
            engineer.add_solar_records(solar_records)
        if weather_records:
            engineer.add_weather_records(weather_records)

        # Log progress periodically
        if (total_solar + total_weather) % 10000 == 0:
            logger.info(
                "historical_progress",
                solar_consumed=total_solar,
                weather_consumed=total_weather,
            )

    # Compute all features
    logger.info(
        "computing_features",
        solar_records=engineer.solar_record_count,
        weather_records=engineer.weather_record_count,
    )

    features = engineer.compute_features()
    if features:
        written = risingwave.write_features(features)
        total_features = written

    # Commit offsets
    consumer.commit()

    logger.info(
        "historical_mode_completed",
        solar_consumed=total_solar,
        weather_consumed=total_weather,
        features_written=total_features,
    )


def run_stream_mode(
    consumer: KafkaConsumerService,
    engineer: FeatureEngineer,
    risingwave: RisingWaveClient,
) -> None:
    """Run continuous stream mode - poll at regular intervals."""
    global _shutdown_requested

    logger.info(
        "stream_mode_starting",
        poll_interval=settings.poll_interval_seconds,
    )

    # Ensure table exists
    risingwave.ensure_table_exists()

    while not _shutdown_requested:
        # Consume batch
        solar_records, weather_records = consumer.consume_batch(
            max_messages=settings.batch_size,
            timeout=1.0,
        )

        # Add to feature engineer
        if solar_records:
            engineer.add_solar_records(solar_records)
        if weather_records:
            engineer.add_weather_records(weather_records)

        # Compute and write features if we have new data
        if solar_records or weather_records:
            features = engineer.compute_features()
            if features:
                risingwave.write_features(features)

            # Commit offsets after successful processing
            consumer.commit()

            # Clear old records to manage memory
            cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.feature_window_hours * 2)
            engineer.clear_old_records(cutoff)

        # Sleep with periodic checks for shutdown
        for _ in range(settings.poll_interval_seconds):
            if _shutdown_requested:
                break
            time.sleep(1)

    logger.info("stream_mode_stopped")


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Feature engineering pipeline for solar and weather data"
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=[m.value for m in FeatureMode],
        default=FeatureMode.STREAM.value,
        help="Operating mode: 'historical' (backfill all data, then exit) "
        "or 'stream' (continuous processing, default)",
    )
    return parser.parse_args()


def main() -> None:
    """Main entry point for the feature engineering service."""
    global _shutdown_requested

    # Parse arguments
    args = parse_args()
    mode = FeatureMode(args.mode)

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info(
        "feature_service_starting",
        mode=mode.value,
        kafka_servers=settings.kafka_bootstrap_servers,
        risingwave_host=settings.risingwave_host,
        risingwave_port=settings.risingwave_port,
    )

    # Initialize components
    consumer = KafkaConsumerService()
    engineer = FeatureEngineer()
    risingwave = RisingWaveClient()

    try:
        if mode == FeatureMode.HISTORICAL:
            run_historical_mode(consumer, engineer, risingwave)
        else:
            run_stream_mode(consumer, engineer, risingwave)
    finally:
        logger.info("feature_service_stopping")
        consumer.close()
        risingwave.close()
        logger.info("feature_service_stopped")


if __name__ == "__main__":
    main()
