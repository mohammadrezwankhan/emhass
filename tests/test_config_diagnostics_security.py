"""Configuration diagnostics must not serialize configured private paths."""

from unittest.mock import Mock

import pytest

from emhass import utils


class DiagnosticReached(Exception):
    pass


@pytest.mark.asyncio
@pytest.mark.parametrize("entrypoint", ["runtime", "legacy", "params"])
async def test_missing_associations_diagnostic_does_not_expose_configured_path(
    tmp_path, entrypoint
):
    marker = "PRIVATE_CONFIG_CANARY"
    config = {"associations_path": tmp_path / marker / "associations.csv"}
    logger = Mock()
    logger.warning.side_effect = DiagnosticReached
    logger.error.side_effect = DiagnosticReached
    with pytest.raises(DiagnosticReached):
        if entrypoint == "runtime":
            params = {
                "retrieve_hass_conf": {},
                "optim_conf": {"number_of_deferrable_loads": 0},
                "plant_conf": {},
            }
            await utils.treat_runtimeparams(
                "{}", params, {}, {}, {}, "dayahead-optim", logger, config
            )
        elif entrypoint == "legacy":
            await utils.build_legacy_config_params(config, {}, logger)
        else:
            await utils.build_params(config, {}, {}, logger)
    diagnostic = str(logger.mock_calls)
    assert "associations" in diagnostic.lower()
    assert marker not in diagnostic
