"""Untrusted names must remain single InfluxQL tokens, never query syntax."""

import logging
import re
import unittest
from types import SimpleNamespace

import pandas as pd

from emhass.retrieve_hass import RetrieveHass

# InfluxQL strings/identifiers use quoted tokens with backslash escapes.
# This lexer is independent of the application's encoder and does not run SQL.
QUOTED = re.compile(r"'(?:\\[\\'\"n]|[^'\\\r\n])*'|\"(?:\\[\\'\"n]|[^\"\\\r\n])*\"")


def tokens(query):
    def decode(token):
        return re.sub(
            r"\\([\\'\"n])", lambda match: "\n" if match[1] == "n" else match[1], token[1:-1]
        )

    return [(match[0][0], decode(match[0])) for match in QUOTED.finditer(query)], QUOTED.sub(
        "TOKEN", query
    )


class TestInfluxQueryTokens(unittest.TestCase):
    def setUp(self):
        self.retrieval = RetrieveHass.__new__(RetrieveHass)
        self.retrieval.freq = pd.Timedelta(minutes=30)
        self.retrieval.influxdb_database = "homeassistant"
        self.retrieval.influxdb_retention_policy = "autogen"
        self.retrieval.influxdb_measurement = "W"
        self.retrieval._measurement_cache = {}
        self.retrieval.logger = logging.getLogger(__name__)

    def query(self, entity="house_load", measurement="W"):
        return self.retrieval._build_influx_query_for_measurement(
            entity, measurement, pd.Timestamp("2025-01-01"), pd.Timestamp("2025-01-02")
        )

    def test_normal_names_preserve_existing_query(self):
        query = " ".join(self.query().split())
        self.assertEqual(
            query,
            'SELECT mean("value") AS "mean_value" FROM "homeassistant"."autogen"."W" '
            "WHERE time >= '2025-01-01T00:00:00Z' AND time < '2025-01-02T00:00:00Z' "
            "AND \"entity_id\"='house_load' GROUP BY time(30m) FILL(previous)",
        )

    def test_entity_cannot_add_a_filter_or_another_statement(self):
        for entity in (
            "load' OR 'x'='x",
            "load'; SHOW USERS; SELECT * FROM W WHERE 'x'='x",
            "load\\' OR true",
        ):
            with self.subTest(entity=entity):
                quoted, syntax = tokens(self.query(entity=entity))
                self.assertIn(("'", entity), quoted)
                self.assertNotIn(";", syntax)
                self.assertNotRegex(syntax, r"\bOR\b|\bSHOW\b")

    def test_database_retention_and_measurement_names_remain_identifiers(self):
        database = 'db"; SHOW USERS; --'
        retention = 'rp\\"'
        measurement = 'W" WHERE true; SELECT * FROM "elsewhere'
        self.retrieval.influxdb_database = database
        self.retrieval.influxdb_retention_policy = retention
        quoted, syntax = tokens(self.query(measurement=measurement))
        for identifier in (database, retention, measurement):
            self.assertIn(('"', identifier), quoted)
        self.assertNotIn(";", syntax)
        self.assertNotIn("SHOW", syntax)

    def test_discovery_quotes_measurement_names_from_server(self):
        measurement = 'W"; SHOW USERS; --'
        queries = []

        def query(statement):
            queries.append(statement)
            points = (
                [{"name": measurement}]
                if statement == "SHOW MEASUREMENTS"
                else [{"value": "house_load"}]
            )
            return SimpleNamespace(get_points=lambda: iter(points))

        found = self.retrieval._discover_entity_measurement(
            SimpleNamespace(query=query), "house_load"
        )
        self.assertEqual(found, measurement)
        quoted, syntax = tokens(queries[-1])
        self.assertIn(('"', measurement), quoted)
        self.assertNotIn(";", syntax)
        self.assertEqual(syntax.count("SHOW"), 1)

    def test_control_characters_are_rejected_before_querying(self):
        for bad in ("load\nother", "load\rother", "load\x00other"):
            with self.subTest(value=bad), self.assertRaises(ValueError):
                self.query(entity=bad)
