![Home Energy Automation Lab: original vector system illustration](assets/hero-25d.svg)

This fork preserves EMHASS energy optimization, forecasts, and Home Assistant interfaces. A synthetic EV charging exercise explains energy windows and the distinction between a planner and a device executor.

**[Native-source lesson guide](docs/portfolio/) · [Offline interactive lab](docs/index.html) · [Lesson configuration](docs/lesson-config.json) · [Configuration schema](docs/lesson-config.schema.json)**

## Your first interactive result

1. Download or clone this repository and open `docs/index.html` in a modern browser.
2. Select **Module 1**, apply its preset, and compare the declared checkpoint with the plotted result.
3. Change one slider, inspect the model assumptions, then export the configuration or telemetry for your notes.

The browser lab runs offline with no packages, accounts, or live data feeds. Its numbers are deterministic teaching simulations. Each checkpoint states its model time and tolerance; passing it demonstrates agreement with that model, not field calibration or production readiness.

## Four-module learning path

| Module | Investigation | Approximate time |
|---|---|---:|
| 1. Translate a charging target into stored energy | Relate battery capacity, charge efficiency, power, and a fixed time window. | 12 min |
| 2. Check the time-window calculation | Determine whether a nominal charging target is reachable within a stated window. | 15 min |
| 3. Expose the constant-power approximation | Explain how a physical charging taper changes a naive energy-over-power estimate. | 15 min |
| 4. Reject an infeasible target before automation | Document an energy shortfall and preserve the planner/executor responsibility boundary. | 18 min |

**Who this is for:** Home-energy developers, automation learners, and contributors studying deferrable-load planning.

### Continue into the implementation

- [README.md](README.md)
- [LICENSE](LICENSE)
- [AGENTS.md](AGENTS.md)
- [pyproject.toml](pyproject.toml)
- [docs/develop.md](docs/develop.md)
- [docs/quick_start.md](docs/quick_start.md)
- [docs/study_cases/ev.md](docs/study_cases/ev.md)

### Explore or run the source

Python >=3.10,<3.13 for the native fork. The documented test extra installs its optimization and test dependencies; no hardware is needed for this browser lab.

```bash
python -m pip install -e ".[test]"
python -m pytest tests/test_defaults_smoke.py
python -m pytest tests/test_optimization.py
```

These commands come from the audited source revision. Runtime requirements and the project's own validation limits are documented below; the standalone browser lab does not execute these commands.

**Fork provenance.** This repository retains the upstream project and its attribution. [https://github.com/davidusb-geek/emhass](https://github.com/davidusb-geek/emhass) The interactive lab is an additional educational companion; it does not imply upstream endorsement or relicense the existing material.

The detailed project guide below remains the source for installation, supported features, licences, and scientific limits. The browser equations and laboratory settings do not change the original application or numerical engine.

<details>
<summary>Project documentation, installation, attribution, and existing validation</summary>

<div align="center">
  <br>
  <img alt="EMHASS" src="https://raw.githubusercontent.com/davidusb-geek/emhass/master/docs/images/logo_docs.png" width="700px">
  <h1>Energy Management for Home Assistant</h1>
  <strong></strong>
</div>
<br>

<p align="center">
  <a style="text-decoration:none" href="https://pypi.org/project/emhass/">
    <img alt="PyPI - Version" src="https://img.shields.io/pypi/v/emhass">
  </a>
  <a style="text-decoration:none" href="https://anaconda.org/channels/davidusb/packages/emhass/overview">
    <img alt="Conda - Version" src="https://img.shields.io/conda/v/davidusb/emhass">
  </a>
  <a style="text-decoration:none" href="https://github.com/davidusb-geek/emhass/actions">
    <img alt="EMHASS GitHub Workflow Status" src="https://github.com/davidusb-geek/emhass/actions/workflows/publish_docker.yaml/badge.svg?event=release">
  </a>
  <a style="text-decoration:none" href="https://github.com/davidusb-geek/emhass/blob/master/LICENSE">
    <img alt="GitHub" src="https://img.shields.io/github/license/davidusb-geek/emhass">
  </a>
  <a style="text-decoration:none" href="https://pypi.org/project/emhass/">
    <img alt="PyPI - Python Version" src="https://img.shields.io/pypi/pyversions/emhass">
  </a>
  <a style="text-decoration:none" href="https://pypi.org/project/emhass/">
    <img alt="PyPI - Status" src="https://img.shields.io/pypi/status/emhass">
  </a>
  <a style="text-decoration:none" href="https://emhass.readthedocs.io/en/latest/">
    <img alt="Read the Docs" src="https://img.shields.io/readthedocs/emhass">
  </a>
    <a style="text-decoration:none" href="https://codecov.io/github/davidusb-geek/emhass" >
    <img alt="Upstream EMHASS coverage" src="https://codecov.io/github/davidusb-geek/emhass/branch/master/graph/badge.svg?token=BW7KSCHN90"/>
  </a>
  <a style="text-decoration:none" href="https://github.com/davidusb-geek/emhass/actions/workflows/codeql.yml" >
    <img alt="Upstream EMHASS CodeQL workflow" src="https://github.com/davidusb-geek/emhass/actions/workflows/codeql.yml/badge.svg?branch=master&event=schedule"/>
  </a>
  <a style="text-decoration:none" href="https://sonarcloud.io/summary/new_code?id=davidusb-geek_emhass">
    <img alt="SonarQube security rating" src="https://sonarcloud.io/api/project_badges/measure?project=davidusb-geek_emhass&metric=security_rating">
  </a>
  <a style="text-decoration:none" href="https://sonarcloud.io/summary/new_code?id=davidusb-geek_emhass">
    <img alt="SonarQube security Vulnerabilities" src="https://sonarcloud.io/api/project_badges/measure?project=davidusb-geek_emhass&metric=vulnerabilities">
  </a>
  <a style="text-decoration:none" href="https://sonarcloud.io/summary/new_code?id=davidusb-geek_emhass">
    <img alt="SonarQube reliability" src="https://sonarcloud.io/api/project_badges/measure?project=davidusb-geek_emhass&metric=reliability_rating">
  </a>
  <a style="text-decoration:none" href="https://sonarcloud.io/summary/new_code?id=davidusb-geek_emhass">
    <img alt="SonarQube bugs" src="https://sonarcloud.io/api/project_badges/measure?project=davidusb-geek_emhass&metric=bugs">
  </a>

</p>

<div align="center">
 <a style="text-decoration:none" href="https://emhass.readthedocs.io/en/latest/">
      <img src="https://raw.githubusercontent.com/davidusb-geek/emhass/master/docs/images/Documentation_button.svg" alt="Documentation">
  </a>
   <a style="text-decoration:none" href="https://community.home-assistant.io/t/emhass-an-energy-management-for-home-assistant/338126">
      <img src="https://raw.githubusercontent.com/davidusb-geek/emhass/master/docs/images/Community_button.svg" alt="Community">
  </a>
  <a style="text-decoration:none" href="https://github.com/davidusb-geek/emhass/issues">
      <img src="https://raw.githubusercontent.com/davidusb-geek/emhass/master/docs/images/Issues_button.svg" alt="Issues">
  </a>
  <a style="text-decoration:none" href="https://github.com/davidusb-geek/emhass-add-on">
     <img src="https://raw.githubusercontent.com/davidusb-geek/emhass/master/docs/images/EMHASS_Add_on_button.svg" alt="EMHASS Add-on">
  </a>
</div>

<br>
<p align="left">
EMHASS is a Python module designed to optimize your home energy interfacing with Home Assistant.
</p>

## Introduction

EMHASS (Energy Management for Home Assistant) is an optimization tool designed for residential households. The package uses a Linear Programming approach to optimize energy usage while considering factors such as electricity prices, power generation from solar panels, and energy storage from batteries. EMHASS provides a high degree of configurability, making it easy to integrate with Home Assistant and other smart home systems. Whether you have solar panels, energy storage, or just a controllable load, EMHASS can provide an optimized daily schedule for your devices, allowing you to save money and minimize your environmental impact.

The complete documentation for this package is [available here](https://emhass.readthedocs.io/en/latest/).

To get started you can follow our [🚀 Quick Start](docs/quick_start.md) guide in the documentation.

Here are the guides for:

- [📦 Installation methods](docs/installation_methods.md)
- [📖 Usage](docs/usage_guide.md)
- [🤖 Home Assistant Automations](docs/automations.md)

## Development

Pull requests are very much accepted on this project. For development, you can find some instructions here [Development](docs/develop.md).

## License

MIT License

Copyright (c) 2021-2026 David HERNANDEZ TORRES

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

</details>
