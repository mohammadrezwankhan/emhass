"""Exercise the shipped JavaScript against hostile saved configuration values."""

import json
import shutil
import subprocess
import unittest
from html.parser import HTMLParser
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "src" / "emhass" / "static"
NODE = shutil.which("node")


class _Inputs(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.elements = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


@unittest.skipUnless(NODE, "Node.js is required to execute the shipped browser JavaScript")
class TestConfigurationRendering(unittest.TestCase):
    def evaluate(self, script, expression, data):
        runner = """
const fs = require('node:fs');
const vm = require('node:vm');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const context = vm.createContext({window: {}, console, input: input.data, Response});
vm.runInContext(fs.readFileSync(input.script, 'utf8'), context);
Promise.resolve(vm.runInContext(input.expression, context)).then(
    result => process.stdout.write(JSON.stringify(result)),
    error => { console.error(error); process.exitCode = 1; }
);
"""
        result = subprocess.run(
            [NODE, "-e", runner],
            input=json.dumps(
                {"script": str(STATIC / script), "expression": expression, "data": data}
            ),
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def render(self, kind, value, default="default"):
        return self.evaluate(
            "configuration_script.js",
            "buildParamElement(input.definition, 'setting', {setting: input.value})",
            {"definition": {"input": kind, "default_value": default}, "value": value},
        )

    def assert_safe_values(self, html, expected):
        elements = _Inputs(html).elements
        self.assertTrue(all(tag in {"input", "br"} for tag, _ in elements), elements)
        inputs = [attrs for tag, attrs in elements if tag == "input"]
        self.assertEqual([attrs.get("value") for attrs in inputs], expected)
        for attrs in inputs:
            self.assertEqual(set(attrs), {"class", "type", "placeholder", "value"})

    def test_scalar_configuration_is_literal_attribute_data(self):
        value = 'house load "<&>\' autofocus onfocus="window.auditInjected=1"'
        self.assert_safe_values(self.render("string", value), [value])

    def test_array_configuration_cannot_create_html_elements(self):
        value = 'x><img src=x onerror="window.auditInjected=1">'
        self.assert_safe_values(
            self.render("array.string", ["normal value", value]), ["normal value", value]
        )

    def test_nested_time_configuration_is_literal_attribute_data(self):
        value = '01:00 autofocus onfocus="window.auditInjected=1"'
        config = {"period1": {"start": [value], "end": ["02:00"]}}
        self.assert_safe_values(self.render("array.time", config), [value, "02:00"])

    def test_object_placeholder_cannot_create_attributes(self):
        value = {"name": '"<&>'}
        default = {"name": 'x" autofocus onfocus="window.auditInjected=1'}
        html = self.render("object", value, default)
        self.assert_safe_values(html, [json.dumps(value, separators=(",", ":"))])
        attrs = _Inputs(html).elements[0][1]
        self.assertEqual(attrs["placeholder"], json.dumps(default, separators=(",", ":")))

    def test_http_200_action_is_shown_as_success(self):
        result = self.evaluate(
            "script.js",
            """(async () => {
                const loader = {innerHTML: '', classList: {add() {}, remove() {}}};
                const alertText = {textContent: ''};
                document = {getElementById: id => ({loader, 'alert-text': alertText, alert: {style: {}}}[id])};
                fetch = async () => new Response('EMHASS >> Action executed...\\n', {status: 200});
                getTemplate = () => {};
                const success = await formAction('dayahead-optim', 'basic');
                return {success, loader: loader.innerHTML, alert: alertText.textContent};
            })()""",
            {},
        )
        self.assertTrue(result["success"])
        self.assertIn("class=tick", result["loader"])
        self.assertEqual(result["alert"], "")
