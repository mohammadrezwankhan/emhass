"""Runtime filenames must stay inside the configured EMHASS data directory."""

import logging
import pickle
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pandas as pd

from emhass import command_line, web_server
from emhass.forecast import Forecast
from emhass.utils import UnsafeDataPath

from .test_export_influxdb_async import _Retrieval

LOGGER = logging.getLogger(__name__)


class TestRuntimeDataFiles(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.data = self.root / "data"
        self.data.mkdir()

    def context(self, **passed_data):
        return SimpleNamespace(
            params={"passed_data": passed_data},
            emhass_conf={"data_path": self.data},
            logger=LOGGER,
            get_data_from_file=True,
        )

    def test_regressor_cannot_read_csv_outside_data_directory(self):
        outside = self.root / "outside.csv"
        outside.write_text("power\n314\n", encoding="utf-8")
        for filename in ("../outside.csv", str(outside)):
            with (
                self.subTest(filename=filename),
                self.assertRaisesRegex(ValueError, "data directory"),
            ):
                command_line._prepare_regressor_fit(self.context(csv_file=filename))

    def test_relative_csv_inside_data_directory_still_loads(self):
        (self.data / "training").mkdir()
        (self.data / "training" / "load.csv").write_text("power\n314\n", encoding="utf-8")
        result = command_line._prepare_regressor_fit(self.context(csv_file="training/load.csv"))
        self.assertEqual(result["df_input_data"]["power"].tolist(), [314])

    def test_symlink_cannot_redirect_csv_read_outside_data_directory(self):
        outside = self.root / "outside.csv"
        outside.write_text("power\n314\n", encoding="utf-8")
        (self.data / "link.csv").symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "data directory"):
            command_line._prepare_regressor_fit(self.context(csv_file="link.csv"))

    async def test_training_pickle_cannot_be_read_outside_data_directory(self):
        frame = pd.DataFrame({"power": [10, 20]}, index=pd.date_range("2025-01-01", periods=2))
        (self.root / "outside.pkl").write_bytes(pickle.dumps((frame, None, None, None)))
        with self.assertRaisesRegex(ValueError, "data directory"):
            await command_line._prepare_ml_fit_predict(
                self.context(
                    model_type="../outside", var_model="power", historic_days_to_retrieve=1
                )
            )

    async def test_model_loaders_reject_escape_before_deserialization(self):
        for suffix in ("_mlf.pkl", "_mlr.pkl"):
            (self.root / ("outside" + suffix)).write_bytes(b"outside model artifact")
        input_data = {
            "params": {"passed_data": {"model_type": "../outside"}},
            "emhass_conf": {"data_path": self.data},
        }
        for loader in (
            command_line.forecast_model_predict,
            command_line.forecast_model_tune,
            command_line.regressor_model_predict,
        ):
            with (
                self.subTest(loader=loader.__name__),
                patch.object(
                    command_line.pickle,
                    "loads",
                    side_effect=AssertionError("outside model reached deserializer"),
                ) as loads,
            ):
                with self.assertRaisesRegex(ValueError, "data directory"):
                    await loader(input_data, LOGGER)
                loads.assert_not_called()

    async def test_optimization_model_loader_rejects_escape_before_deserialization(self):
        (self.root / "outside_mlf.pkl").write_bytes(b"outside model artifact")
        forecast = Forecast.__new__(Forecast)
        forecast.params = {"passed_data": {"model_type": "../outside"}}
        forecast.emhass_conf = {"data_path": self.data}
        with (
            patch.object(
                command_line.pickle,
                "loads",
                side_effect=AssertionError("outside model reached deserializer"),
            ) as loads,
            self.assertRaisesRegex(ValueError, "data directory"),
        ):
            await forecast._get_load_forecast_ml(pd.DataFrame(), False, None, False)
        loads.assert_not_called()

    async def test_csv_export_cannot_overwrite_outside_data_directory(self):
        outside = self.root / "outside.csv"
        outside.write_text("preserve this file\n", encoding="utf-8")
        retrieval = _Retrieval(True)
        input_data = {
            "rh": retrieval,
            "emhass_conf": {"data_path": self.data},
            "params": {
                "passed_data": {
                    "sensor_list": ["sensor.load"],
                    "csv_filename": "../outside.csv",
                    "start_time": "2025-01-01T00:00:00+00:00",
                    "end_time": "2025-01-01T02:00:00+00:00",
                }
            },
        }
        with self.assertRaisesRegex(ValueError, "data directory"):
            await command_line.export_influxdb_to_csv(input_data, LOGGER)
        self.assertEqual(outside.read_text(encoding="utf-8"), "preserve this file\n")
        self.assertIsNone(retrieval.df_final)

    async def test_invalid_action_filename_returns_client_error(self):
        with (
            patch.object(
                web_server,
                "_load_params_and_runtime",
                AsyncMock(return_value=("{}", "profit", "{}")),
            ),
            patch.object(
                web_server,
                "_handle_action_dispatch",
                AsyncMock(
                    side_effect=UnsafeDataPath(
                        "Filename must refer to a file inside the data directory"
                    )
                ),
            ),
        ):
            response = await web_server.app.test_client().post(
                "/action/export-influxdb-to-csv", json={}
            )
        self.assertEqual(response.status_code, 400)
        self.assertIn("data directory", (await response.get_json())[0])
