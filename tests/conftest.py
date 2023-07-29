import os

import pytest

_intial_model_serialization_hook = os.environ.get("BRIDGEAPI_MODEL_SERIALIZATION_HOOK")


def pytest_configure(config):
    os.environ["BRIDGEAPI_MODEL_SERIALIZATION_HOOK"] = "1"


def pytest_unconfigure(config):
    if _intial_model_serialization_hook is None:
        del os.environ["BRIDGEAPI_MODEL_SERIALIZATION_HOOK"]
    else:
        os.environ["BRIDGEAPI_MODEL_SERIALIZATION_HOOK"] = _intial_model_serialization_hook


@pytest.fixture(scope="session")
def vcr_config():
    return {"filter_headers": ["Client-Id", "Client-Secret", "Authorization"]}
