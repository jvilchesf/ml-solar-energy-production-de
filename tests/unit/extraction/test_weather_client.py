from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from services.extraction.src.models import WeatherRecord
from services.extraction.src.weather_client import WeatherClient


class TestWeatherClient:
    """Tests for WeatherClient."""

    def test_parse_response_creates_records(self, sample_weather_response):
        """_parse_response should create WeatherRecord from valid data."""
        client = WeatherClient()
        records = client._parse_response(sample_weather_response)

        assert len(records) == 3
        assert all(isinstance(r, WeatherRecord) for r in records)
        assert records[0].temperature_c == 5.5
        assert records[0].cloud_cover_pct == 75
        assert records[0].solar_radiation_wm2 == 0

    def test_parse_response_includes_coordinates(self, sample_weather_response):
        """_parse_response should include latitude/longitude in records."""
        client = WeatherClient()
        records = client._parse_response(sample_weather_response)

        assert records[0].latitude == 51.1657
        assert records[0].longitude == 10.4515

    def test_parse_response_handles_empty_data(self):
        """_parse_response should handle empty hourly data gracefully."""
        client = WeatherClient()
        records = client._parse_response({"hourly": {}})

        assert records == []

    @patch("httpx.Client")
    def test_fetch_weather_forecast(self, mock_client_class, sample_weather_response):
        """fetch_weather_forecast should use forecast API."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.json.return_value = sample_weather_response
        mock_client.get.return_value = mock_response

        client = WeatherClient()
        records = client.fetch_weather_forecast(past_days=7, forecast_days=1)

        assert len(records) == 3
        # Verify forecast URL was used
        call_args = mock_client.get.call_args
        assert "forecast" in call_args.args[0]

    @patch("httpx.Client")
    def test_fetch_weather_archive(self, mock_client_class, sample_weather_response):
        """fetch_weather_archive should use archive API with date range."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.json.return_value = sample_weather_response
        mock_client.get.return_value = mock_response

        client = WeatherClient()
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 1, 7, tzinfo=timezone.utc)
        records = client.fetch_weather_archive(start_date=start, end_date=end)

        assert len(records) == 3
        # Verify archive URL was used
        call_args = mock_client.get.call_args
        assert "archive" in call_args.args[0]
        assert call_args.kwargs["params"]["start_date"] == "2025-01-01"

    def test_init_with_custom_coordinates(self):
        """WeatherClient should accept custom coordinates."""
        client = WeatherClient(latitude=52.52, longitude=13.405)

        assert client._latitude == 52.52
        assert client._longitude == 13.405
