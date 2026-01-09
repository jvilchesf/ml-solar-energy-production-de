from datetime import datetime, timedelta, timezone

import structlog

from .config import settings
from .models import EnrichedFeatureRecord, SolarProductionRecord, WeatherRecord

logger = structlog.get_logger()


class FeatureEngineer:
    """Feature engineering for solar production and weather data."""

    def __init__(self, window_hours: int | None = None):
        self._window_hours = window_hours or settings.feature_window_hours
        self._solar_records: dict[datetime, SolarProductionRecord] = {}
        self._weather_records: dict[datetime, WeatherRecord] = {}

    def add_solar_records(self, records: list[SolarProductionRecord]) -> None:
        """Add solar production records to the internal state."""
        for record in records:
            # Round to nearest hour for alignment
            hour_key = self._round_to_hour(record.timestamp)
            # Keep the most recent record for each hour
            existing = self._solar_records.get(hour_key)
            if existing is None or record.timestamp > existing.timestamp:
                self._solar_records[hour_key] = record

        logger.debug(
            "solar_records_added",
            new_count=len(records),
            total_hours=len(self._solar_records),
        )

    def add_weather_records(self, records: list[WeatherRecord]) -> None:
        """Add weather records to the internal state."""
        for record in records:
            hour_key = self._round_to_hour(record.timestamp)
            existing = self._weather_records.get(hour_key)
            if existing is None or record.timestamp > existing.timestamp:
                self._weather_records[hour_key] = record

        logger.debug(
            "weather_records_added",
            new_count=len(records),
            total_hours=len(self._weather_records),
        )

    def compute_features(self) -> list[EnrichedFeatureRecord]:
        """Compute enriched features from aligned solar and weather records."""
        aligned = self._align_records()

        if not aligned:
            return []

        # Sort by timestamp for correct lag calculations
        aligned.sort(key=lambda x: x[0].timestamp)

        # Build lookup for lag calculations
        production_by_hour: dict[datetime, float] = {}
        for solar, _ in aligned:
            hour_key = self._round_to_hour(solar.timestamp)
            production_by_hour[hour_key] = solar.production_mw

        enriched_records: list[EnrichedFeatureRecord] = []

        for solar, weather in aligned:
            hour_key = self._round_to_hour(solar.timestamp)

            # Calculate moving averages
            production_ma = self._calculate_moving_average(
                production_by_hour, hour_key, self._window_hours
            )
            temperature_ma = self._calculate_weather_moving_average(
                "temperature_c", hour_key, self._window_hours
            )
            cloud_cover_ma = self._calculate_weather_moving_average(
                "cloud_cover_pct", hour_key, self._window_hours
            )

            # Calculate lagged features
            production_lag_1h = production_by_hour.get(hour_key - timedelta(hours=1))
            production_lag_24h = production_by_hour.get(hour_key - timedelta(hours=24))

            # Extract temporal features
            hour_of_day = solar.timestamp.hour
            day_of_week = solar.timestamp.weekday()
            is_weekend = day_of_week >= 5

            enriched = EnrichedFeatureRecord(
                timestamp=solar.timestamp,
                region=solar.region,
                production_mw=solar.production_mw,
                temperature_c=weather.temperature_c,
                cloud_cover_pct=weather.cloud_cover_pct,
                solar_radiation_wm2=weather.solar_radiation_wm2,
                latitude=weather.latitude,
                longitude=weather.longitude,
                production_ma_24h=production_ma,
                temperature_ma_24h=temperature_ma,
                cloud_cover_ma_24h=cloud_cover_ma,
                production_lag_1h=production_lag_1h,
                production_lag_24h=production_lag_24h,
                hour_of_day=hour_of_day,
                day_of_week=day_of_week,
                is_weekend=is_weekend,
            )
            enriched_records.append(enriched)

        logger.info(
            "features_computed",
            record_count=len(enriched_records),
        )

        return enriched_records

    def clear_old_records(self, older_than: datetime) -> None:
        """Remove records older than the specified timestamp to manage memory."""
        cutoff = self._round_to_hour(older_than)

        old_solar_count = len(self._solar_records)
        old_weather_count = len(self._weather_records)

        self._solar_records = {k: v for k, v in self._solar_records.items() if k >= cutoff}
        self._weather_records = {k: v for k, v in self._weather_records.items() if k >= cutoff}

        logger.debug(
            "old_records_cleared",
            solar_removed=old_solar_count - len(self._solar_records),
            weather_removed=old_weather_count - len(self._weather_records),
            cutoff=cutoff.isoformat(),
        )

    def _round_to_hour(self, dt: datetime) -> datetime:
        """Round a datetime to the nearest hour."""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.replace(minute=0, second=0, microsecond=0)

    def _align_records(self) -> list[tuple[SolarProductionRecord, WeatherRecord]]:
        """Align solar and weather records by hour."""
        aligned: list[tuple[SolarProductionRecord, WeatherRecord]] = []

        for hour_key, solar in self._solar_records.items():
            if hour_key in self._weather_records:
                aligned.append((solar, self._weather_records[hour_key]))

        return aligned

    def _calculate_moving_average(
        self,
        production_by_hour: dict[datetime, float],
        current_hour: datetime,
        window_hours: int,
    ) -> float | None:
        """Calculate moving average of production over the window."""
        values: list[float] = []

        for i in range(window_hours):
            hour = current_hour - timedelta(hours=i)
            if hour in production_by_hour:
                values.append(production_by_hour[hour])

        if not values:
            return None

        return sum(values) / len(values)

    def _calculate_weather_moving_average(
        self,
        field: str,
        current_hour: datetime,
        window_hours: int,
    ) -> float | None:
        """Calculate moving average of a weather field over the window."""
        values: list[float] = []

        for i in range(window_hours):
            hour = current_hour - timedelta(hours=i)
            if hour in self._weather_records:
                record = self._weather_records[hour]
                values.append(getattr(record, field))

        if not values:
            return None

        return sum(values) / len(values)

    @property
    def solar_record_count(self) -> int:
        """Return the number of solar records in state."""
        return len(self._solar_records)

    @property
    def weather_record_count(self) -> int:
        """Return the number of weather records in state."""
        return len(self._weather_records)
