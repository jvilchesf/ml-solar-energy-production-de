from datetime import datetime

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
