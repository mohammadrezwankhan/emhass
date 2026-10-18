"""Provider outages must not turn a missing forecast into an exception."""

import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

import pandas as pd

from emhass.forecast import Forecast


class TestMissingOpenMeteoForecast(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.forecast = Forecast.__new__(Forecast)
        self.forecast.optim_conf = {
            "open_meteo_cache_max_age": 30,
            "delta_forecast_daily": pd.Timedelta(days=1),
        }
        self.forecast.logger = logging.getLogger(__name__)
        self.forecast.get_cached_open_meteo_forecast_json = AsyncMock(return_value=None)
        self.cache_path = str(Path(self.folder.name) / "missing.pkl")

    async def test_exhausted_provider_without_cache_returns_failure(self):
        result = await self.forecast._get_weather_open_meteo(self.cache_path, False)
        self.assertIs(result, False)

    async def test_optional_weather_failure_preserves_supplied_pv(self):
        supplied = pd.DataFrame(
            {"yhat": [100, 200]}, index=pd.date_range("2025-01-01", periods=2, freq="h", tz="UTC")
        )
        result = await self.forecast._augment_list_with_open_meteo(supplied, self.cache_path, False)
        pd.testing.assert_frame_equal(result, supplied)
