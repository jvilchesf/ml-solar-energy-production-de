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
