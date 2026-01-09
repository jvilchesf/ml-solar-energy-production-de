import argparse
import signal
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
    smard_client: SmardClient,
    weather_client: WeatherClient,
    producer: KafkaProducerService,
) -> None:
    """Run historical backfill mode - fetch all data since start date, then exit."""
    start_date = datetime.fromisoformat(settings.historical_start_date).replace(tzinfo=timezone.utc)
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
    parser = argparse.ArgumentParser(description="Extraction pipeline for solar and weather data")
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
