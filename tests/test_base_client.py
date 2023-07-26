import re

import pytest
from pytest_mock import MockerFixture

from bridgeapi.base_client import BaseClient
from bridgeapi.exceptions import ErrorResponseData, RequestError


def test_init():
    client = BaseClient("CLIENT_ID", "CLIENT_SECRET")
    assert client.client_id == "CLIENT_ID"
    assert client.client_secret == "CLIENT_SECRET"
    assert isinstance(client.base_url, str)
    assert client.base_url.startswith("https://")
    assert re.match(r"\d{4}-\d{2}-\d{2}", client.api_version)


@pytest.fixture
def setup_assets(mocker: MockerFixture):
    client = BaseClient("CLIENT_ID", "CLIENT_SECRET")
    client.base_url = "https://BASE_URL/"
    client.api_version = "API_VERSION"

    response = mocker.Mock(status_code=200)
    m_request = mocker.patch.object(client.session, "request", return_value=response)

    base_headers = {
        "Bridge-Version": "API_VERSION",
        "Client-Id": "CLIENT_ID",
        "Client-Secret": "CLIENT_SECRET",
        "Content-Type": "application/json",
    }

    return client, m_request, response, base_headers


def test_request(setup_assets):
    client, m_request, response, base_headers = setup_assets

    assert client.request("METH", "path") is response
    m_request.assert_called_once_with(
        "METH", "https://BASE_URL/path", params=None, headers=base_headers, json=None
    )


def test_request_with_args(mocker: MockerFixture, setup_assets):
    client, m_request, response, base_headers = setup_assets
    client.base_url = "https://BASE_URL/foo/"

    result = client.request(
        "METH",
        "/path",
        params=mocker.sentinel.params,
        headers={"Foo": "bar"},
        json=mocker.sentinel.json,
    )
    assert result is response
    m_request.assert_called_once_with(
        "METH",
        "https://BASE_URL/path",
        params=mocker.sentinel.params,
        headers={**base_headers, "Foo": "bar"},
        json=mocker.sentinel.json,
    )


def test_request_error(setup_assets):
    client, m_request, response, base_headers = setup_assets

    response.status_code = 400
    response.json.return_value = {
        "type": "ERROR_TYPE",
        "message": "ERROR_MESSAGE",
        "documentation_url": "ERROR_DOC_URL",
    }

    with pytest.raises(RequestError) as exc_info:
        client.request("METH", "path")
    assert exc_info.type is RequestError
    assert exc_info.value.response is response
    assert exc_info.value.status_code == 400
    assert exc_info.value.response_data == ErrorResponseData(
        type="ERROR_TYPE", message="ERROR_MESSAGE", documentation_url="ERROR_DOC_URL"
    )
    assert str(exc_info.value).startswith("HTTP error 400 (ERROR_TYPE)")
    m_request.assert_called_once_with(
        "METH", "https://BASE_URL/path", params=None, headers=base_headers, json=None
    )
