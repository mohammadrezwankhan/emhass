"""Offline regression tests for file, HTML, and InfluxQL input boundaries."""

import asyncio
import json
import logging
import pathlib
import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from emhass import command_line, utils
from emhass.forecast import Forecast
from emhass.retrieve_hass import RetrieveHass

LOGGER = logging.getLogger(__name__)


@pytest.mark.parametrize("from_file", [False, True])
@pytest.mark.parametrize("path_kind", ["parent", "absolute", "symlink"])
def test_regressor_csv_cannot_leave_data_directory(tmp_path, from_file, path_kind):
    data_path = tmp_path / "data"
    data_path.mkdir()
    outside = tmp_path / "outside.csv"
    outside.write_text("feature,target\n1,2\n", encoding="utf-8")
    if path_kind == "symlink":
        (data_path / "link.csv").symlink_to(outside)
        filename = "link.csv"
    else:
        filename = "../outside.csv" if path_kind == "parent" else str(outside)
    ctx = SimpleNamespace(
        params={"passed_data": {"csv_file": filename}},
        emhass_conf={"data_path": data_path},
        get_data_from_file=from_file,
        logger=LOGGER,
    )
    with pytest.raises(ValueError, match="data directory"):
        command_line._prepare_regressor_fit(ctx)


@pytest.mark.parametrize("from_file", [False, True])
def test_regressor_csv_allows_relative_subdirectory(tmp_path, from_file):
    nested = tmp_path / "training"
    nested.mkdir()
    (nested / "input.csv").write_text("feature,target\n1,2\n", encoding="utf-8")
    ctx = SimpleNamespace(
        params={"passed_data": {"csv_file": "training/input.csv", "target": "target"}},
        emhass_conf={"data_path": tmp_path},
        get_data_from_file=from_file,
        logger=LOGGER,
    )
    result = command_line._prepare_regressor_fit(ctx)
    assert result["df_input_data"]["target"].tolist() == [2]


@pytest.mark.parametrize(
    "action", ["forecast_model_predict", "forecast_model_tune", "regressor_model_predict"]
)
@pytest.mark.parametrize("name", ["../outside", "/outside", "C:\\outside"])
def test_model_actions_reject_paths_before_loading(tmp_path, action, name):
    inputs = {
        "params": {"passed_data": {"model_type": name}},
        "emhass_conf": {"data_path": tmp_path},
    }
    with pytest.raises(ValueError, match="data directory"):
        asyncio.run(getattr(command_line, action)(inputs, LOGGER))


def test_ml_training_pickle_rejects_parent_path(tmp_path):
    ctx = SimpleNamespace(
        params={
            "passed_data": {
                "model_type": "../outside",
                "var_model": "load",
                "historic_days_to_retrieve": 1,
            }
        },
        emhass_conf={"data_path": tmp_path},
        get_data_from_file=True,
    )
    with pytest.raises(ValueError, match="data directory"):
        asyncio.run(command_line._prepare_ml_fit_predict(ctx))


def test_load_forecast_rejects_model_parent_path(tmp_path):
    forecast = Forecast.__new__(Forecast)
    forecast.params = {"passed_data": {"model_type": "../outside"}}
    forecast.emhass_conf = {"data_path": tmp_path}
    forecast.logger = LOGGER
    with pytest.raises(ValueError, match="data directory"):
        asyncio.run(forecast._get_load_forecast_ml(None, False, None, False))


def test_csv_export_rejects_parent_path_before_retrieval(tmp_path):
    reader = SimpleNamespace(time_zone="UTC")
    inputs = {
        "params": {
            "passed_data": {"sensor_list": ["sensor.sample"], "csv_filename": "../outside.csv"}
        },
        "emhass_conf": {"data_path": tmp_path},
        "rh": reader,
    }
    with pytest.raises(ValueError, match="data directory"):
        asyncio.run(command_line.export_influxdb_to_csv(inputs, LOGGER))
    assert not (tmp_path.parent / "outside.csv").exists()


def test_data_file_resolver_rejects_symlink_directory_for_new_file(tmp_path):
    data_path = tmp_path / "data"
    outside = tmp_path / "data-other"
    data_path.mkdir()
    outside.mkdir()
    (data_path / "models").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="data directory"):
        utils.resolve_data_file(data_path, "models/new_mlf.pkl")


def test_data_file_resolver_allows_new_file_inside_data_directory(tmp_path):
    (tmp_path / "models").mkdir()
    assert (
        utils.resolve_data_file(tmp_path, "models/new_mlf.pkl") == tmp_path / "models/new_mlf.pkl"
    )


@pytest.mark.parametrize(
    "builder",
    [utils.get_injection_dict_forecast_model_fit, utils.get_injection_dict_forecast_model_tune],
)
def test_forecast_headings_preserve_names_as_text(builder):
    figure = Mock()
    figure.to_html.return_value = "<div>trusted plot</div>"
    frame = Mock()
    frame.plot.return_value = figure
    model = SimpleNamespace(model_type="<b>demo</b> & model", var_model="load < sample")
    result = builder(frame, model)
    assert "&lt;b&gt;demo&lt;/b&gt; &amp; model" in result["subsubtitle0"]
    assert "load &lt; sample" in result["subsubtitle0"]
    assert result["figure_0"] == "<div>trusted plot</div>"


class _FragmentParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.elements = []
        self.text = []

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))

    def handle_data(self, data):
        self.text.append(data)


def _configuration_fragment(definition, value):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is needed to exercise the configuration renderer")
    source = pathlib.Path(utils.__file__).parent / "static" / "configuration_script.js"
    program = """
const fs = require('node:fs');
const vm = require('node:vm');
const data = JSON.parse(fs.readFileSync(0, 'utf8'));
const context = vm.createContext({window: {}});
vm.runInContext(fs.readFileSync(data.source, 'utf8'), context);
process.stdout.write(context.buildParamElement(data.definition, 'sample', {sample: data.value}));
"""
    completed = subprocess.run(
        [node, "-e", program],
        input=json.dumps({"source": str(source), "definition": definition, "value": value}),
        text=True,
        capture_output=True,
        check=True,
        timeout=10,
    )
    parsed = _FragmentParser()
    parsed.feed(completed.stdout)
    return parsed


@pytest.mark.parametrize("value", ['alpha " data-example="beta', "<b>sample</b>", "a &quot; b & c"])
@pytest.mark.parametrize("as_array", [False, True])
def test_configuration_values_stay_inside_one_input(value, as_array):
    definition = {
        "input": "array.string" if as_array else "string",
        "default_value": "default text",
    }
    parsed = _configuration_fragment(definition, [value] if as_array else value)
    assert len(parsed.elements) == 1
    tag, attrs = parsed.elements[0]
    assert tag == "input"
    assert attrs == {
        "class": "param_input",
        "type": "text",
        "placeholder": "default text",
        "value": value,
    }


def test_configuration_object_placeholder_and_value_are_text():
    value = {"label": '<b>sample</b> & "details"'}
    parsed = _configuration_fragment({"input": "object", "default_value": value}, value)
    assert len(parsed.elements) == 1
    attrs = parsed.elements[0][1]
    assert json.loads(attrs["placeholder"]) == value
    assert json.loads(attrs["value"]) == value


def test_configuration_nested_values_are_text():
    value = '07:00 " data-example="sample'
    parsed = _configuration_fragment(
        {"input": "array.time", "default_value": "00:00"}, {"period": [{"start": value}]}
    )
    assert len(parsed.elements) == 1
    assert parsed.elements[0][1]["value"] == value
    assert "data-example" not in parsed.elements[0][1]


def test_configuration_select_options_are_text():
    value = "<b>sample</b> & choice"
    parsed = _configuration_fragment(
        {"input": "select", "default_value": "", "select_options": [value]}, value
    )
    assert [tag for tag, _ in parsed.elements] == ["select", "option"]
    assert parsed.elements[1][1]["selected"] == "selected"
    assert value in parsed.text


@pytest.mark.parametrize("value", [True, False])
def test_configuration_checkbox_preserves_boolean_value(value):
    parsed = _configuration_fragment({"input": "boolean", "default_value": "false"}, value)
    attrs = next(attrs for tag, attrs in parsed.elements if tag == "input")
    assert attrs["type"] == "checkbox"
    assert attrs["value"] == str(value).lower()


def _influx_reader():
    reader = RetrieveHass.__new__(RetrieveHass)
    reader.freq = timedelta(minutes=30)
    reader.influxdb_database = "homeassistant"
    reader.influxdb_retention_policy = "autogen"
    reader.influxdb_measurement = "W"
    reader._measurement_cache = {}
    reader.logger = LOGGER
    return reader


def test_influx_query_escapes_identifier_and_string_delimiters():
    reader = _influx_reader()
    reader.influxdb_database = 'home"site'
    reader.influxdb_retention_policy = "auto\\gen"
    query = reader._build_influx_query_for_measurement(
        "O'Brien\\meter",
        'W"sample',
        datetime(2026, 1, 1, tzinfo=UTC),
        datetime(2026, 1, 2, tzinfo=UTC),
    )
    assert 'FROM "home\\"site"."auto\\\\gen"."W\\"sample"' in query
    assert "AND \"entity_id\"='O\\'Brien\\\\meter'" in query
    assert "GROUP BY time(30m) FILL(previous)" in query


def test_influx_discovery_quotes_database_measurement_name():
    reader = _influx_reader()
    measurement = 'W"sample'
    client = Mock()
    client.query.side_effect = [
        SimpleNamespace(get_points=lambda: iter([{"name": measurement}])),
        SimpleNamespace(get_points=lambda: iter([{"value": "sample"}])),
    ]
    assert reader._discover_entity_measurement(client, "sample") == measurement
    assert (
        client.query.call_args_list[1].args[0]
        == 'SHOW TAG VALUES FROM "W\\"sample" WITH KEY = "entity_id"'
    )
