import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from services.features.src.models import EnrichedFeatureRecord


class TestRisingWaveClient:
    """Tests for RisingWaveClient."""

    @pytest.fixture(autouse=True)
    def mock_psycopg2(self):
        """Mock psycopg2 before importing the client."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch.dict(sys.modules, {"psycopg2": MagicMock()}):
            sys.modules["psycopg2"].connect = MagicMock(return_value=mock_conn)
            sys.modules["psycopg2"].extensions = MagicMock()

            # Import fresh
            if "services.features.src.risingwave_client" in sys.modules:
                del sys.modules["services.features.src.risingwave_client"]

            from services.features.src.risingwave_client import RisingWaveClient

            self.RisingWaveClient = RisingWaveClient
            self.mock_conn = mock_conn
            self.mock_cursor = mock_cursor
            self.mock_connect = sys.modules["psycopg2"].connect

            yield

    @pytest.fixture
    def sample_features(self):
        """Create sample enriched feature records."""
        return [
            EnrichedFeatureRecord(
                timestamp=datetime(2025, 1, 15, 12, 0, tzinfo=timezone.utc),
                region="DE",
                production_mw=1500.0,
                temperature_c=10.0,
                cloud_cover_pct=50.0,
                solar_radiation_wm2=500.0,
                latitude=51.1657,
                longitude=10.4515,
                production_ma_24h=1400.0,
                temperature_ma_24h=9.5,
                cloud_cover_ma_24h=55.0,
                production_lag_1h=1450.0,
                production_lag_24h=1300.0,
                hour_of_day=12,
                day_of_week=2,
                is_weekend=False,
            ),
            EnrichedFeatureRecord(
                timestamp=datetime(2025, 1, 15, 13, 0, tzinfo=timezone.utc),
                region="DE",
                production_mw=1600.0,
                temperature_c=11.0,
                cloud_cover_pct=45.0,
                solar_radiation_wm2=550.0,
                latitude=51.1657,
                longitude=10.4515,
                production_ma_24h=1450.0,
                temperature_ma_24h=10.0,
                cloud_cover_ma_24h=50.0,
                production_lag_1h=1500.0,
                production_lag_24h=1350.0,
                hour_of_day=13,
                day_of_week=2,
                is_weekend=False,
            ),
        ]

    def test_ensure_table_exists_creates_table(self):
        """ensure_table_exists should execute CREATE TABLE statement."""
        client = self.RisingWaveClient()
        client.ensure_table_exists()

        # Verify execute was called with CREATE TABLE
        self.mock_cursor.execute.assert_called()
        call_args = self.mock_cursor.execute.call_args[0][0]
        assert "CREATE TABLE IF NOT EXISTS features_enriched" in call_args

        # Verify commit was called
        self.mock_conn.commit.assert_called()

    def test_write_features_inserts_records(self, sample_features):
        """write_features should insert all records."""
        client = self.RisingWaveClient()
        count = client.write_features(sample_features)

        # Verify execute was called for each record
        assert self.mock_cursor.execute.call_count == 2
        assert count == 2

        # Verify commit was called
        self.mock_conn.commit.assert_called()

    def test_write_features_returns_count(self, sample_features):
        """write_features should return the number of records written."""
        client = self.RisingWaveClient()
        count = client.write_features(sample_features)

        assert count == 2

    def test_write_features_empty_list(self):
        """write_features should handle empty list."""
        client = self.RisingWaveClient()
        count = client.write_features([])

        assert count == 0
        # Should not attempt to connect for empty list
        # (connect is called once for initialization logging,
        # but not for write operation)

    def test_write_features_uses_insert(self, sample_features):
        """write_features should use INSERT statement."""
        client = self.RisingWaveClient()
        client.write_features(sample_features)

        call_args = self.mock_cursor.execute.call_args[0][0]
        assert "INSERT INTO features_enriched" in call_args

    def test_get_record_count(self):
        """get_record_count should return the count from database."""
        self.mock_cursor.fetchone.return_value = (42,)

        client = self.RisingWaveClient()
        count = client.get_record_count()

        assert count == 42
        self.mock_cursor.execute.assert_called()
        assert "SELECT COUNT(*)" in self.mock_cursor.execute.call_args[0][0]

    def test_get_record_count_empty_table(self):
        """get_record_count should return 0 for empty table."""
        self.mock_cursor.fetchone.return_value = (0,)

        client = self.RisingWaveClient()
        count = client.get_record_count()

        assert count == 0

    def test_get_record_count_no_result(self):
        """get_record_count should return 0 when fetchone returns None."""
        self.mock_cursor.fetchone.return_value = None

        client = self.RisingWaveClient()
        count = client.get_record_count()

        assert count == 0

    def test_close_logs_message(self):
        """close should complete without error."""
        client = self.RisingWaveClient()
        # Should not raise
        client.close()

    def test_connection_uses_config_values(self):
        """Client should use configuration values for connection."""
        client = self.RisingWaveClient(
            host="custom-host",
            port=5432,
            database="custom-db",
            user="custom-user",
            password="custom-pass",
        )

        # Trigger a connection
        client.ensure_table_exists()

        # Verify connect was called with custom values
        self.mock_connect.assert_called_with(
            host="custom-host",
            port=5432,
            database="custom-db",
            user="custom-user",
            password="custom-pass",
        )

    def test_write_features_correct_values(self, sample_features):
        """write_features should pass correct values to execute."""
        client = self.RisingWaveClient()
        client.write_features([sample_features[0]])

        # Get the values passed to execute
        call_args = self.mock_cursor.execute.call_args
        values = call_args[0][1]  # Second argument is the tuple of values

        assert values[0] == datetime(2025, 1, 15, 12, 0, tzinfo=timezone.utc)
        assert values[1] == "DE"
        assert values[2] == 1500.0
        assert values[3] == 10.0
        assert values[13] == 12  # hour_of_day
        assert values[14] == 2  # day_of_week
        assert values[15] is False  # is_weekend
