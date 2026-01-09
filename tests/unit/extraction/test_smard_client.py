from unittest.mock import MagicMock, patch

from services.extraction.src.models import SolarProductionRecord
from services.extraction.src.smard_client import SmardClient


class TestSmardClient:
    """Tests for SmardClient."""

    def test_parse_response_creates_records(self, sample_smard_response):
        """_parse_response should create SolarProductionRecord from valid data."""
        client = SmardClient()
        records = client._parse_response(sample_smard_response)

        assert len(records) == 3  # One null value skipped
        assert all(isinstance(r, SolarProductionRecord) for r in records)
        assert records[0].production_mw == 1500.5
        assert records[0].region == "DE"

    def test_parse_response_skips_null_values(self, sample_smard_response):
        """_parse_response should skip entries with null production values."""
        client = SmardClient()
        records = client._parse_response(sample_smard_response)

        assert len(records) == 3
        production_values = [r.production_mw for r in records]
        assert None not in production_values

    def test_parse_response_handles_empty_series(self):
        """_parse_response should handle empty series gracefully."""
        client = SmardClient()
        records = client._parse_response({"series": []})

        assert records == []

    @patch("httpx.Client")
    def test_fetch_available_timestamps(self, mock_client_class, sample_timestamps_response):
        """fetch_available_timestamps should return list of timestamps."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.json.return_value = sample_timestamps_response
        mock_client.get.return_value = mock_response

        client = SmardClient()
        timestamps = client.fetch_available_timestamps()

        assert len(timestamps) == 3
        assert timestamps == sample_timestamps_response["timestamps"]

    @patch("httpx.Client")
    def test_fetch_latest(
        self, mock_client_class, sample_smard_response, sample_timestamps_response
    ):
        """fetch_latest should return records from most recent timestamp."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client

        # First call returns timestamps, second returns data
        mock_response_timestamps = MagicMock()
        mock_response_timestamps.json.return_value = sample_timestamps_response
        mock_response_data = MagicMock()
        mock_response_data.json.return_value = sample_smard_response

        mock_client.get.side_effect = [mock_response_timestamps, mock_response_data]

        client = SmardClient()
        records = client.fetch_latest()

        assert len(records) == 3
        assert all(isinstance(r, SolarProductionRecord) for r in records)
