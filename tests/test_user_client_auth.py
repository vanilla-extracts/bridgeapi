import datetime as dt

import pytest
from pytest_mock import MockerFixture

from bridgeapi.client import UserClient
from bridgeapi.exceptions import UserAuthenticationError
from bridgeapi.models import User, UserAuthInfo


@pytest.fixture
def base_args():
    return ["CLIENT_ID", "CLIENT_SECRET", "john@doe.com", "password"]


@pytest.fixture
def fixed_now(mocker: MockerFixture):
    now = dt.datetime(2023, 1, 1, tzinfo=dt.timezone.utc)
    mocker.patch(
        "bridgeapi.client.dt", mocker.Mock(datetime=mocker.Mock(now=mocker.Mock(return_value=now)))
    )
    return now


def test_user_client_init(fixed_now, base_args):
    client = UserClient(*base_args, auto_renew=True)
    assert client.user_uuid is None
    assert client.access_token is None
    assert client.expires_at is None

    client = UserClient(*base_args, "UUID", "TOKEN", fixed_now)
    assert client.user_uuid == "UUID"
    assert client.access_token == "TOKEN"
    assert client.expires_at == fixed_now

    with pytest.raises(ValueError):
        UserClient(*base_args, "UUID")


def test_is_authenticated(fixed_now, base_args):
    client = UserClient(*base_args)
    assert not client.is_authenticated()

    client = UserClient(*base_args, "UUID", "TOKEN", fixed_now)
    assert not client.is_authenticated()

    client = UserClient(*base_args, "UUID", "TOKEN", fixed_now + dt.timedelta(minutes=2))
    assert client.is_authenticated()
    assert not client.is_authenticated(delay=dt.timedelta(minutes=2))


def test_renew_auth(mocker: MockerFixture, fixed_now, base_args):
    expires_at = fixed_now + dt.timedelta(hours=2)
    auth_info = UserAuthInfo(
        access_token="TOKEN",
        expires_at=expires_at,
        user=User.model_construct(uuid="UUID", email="john@doe.com"),
    )
    m_auth = mocker.Mock(return_value=auth_info)
    mocker.patch(
        "bridgeapi.client.AppClient",
        mocker.Mock(return_value=mocker.Mock(authenticate_user=m_auth)),
    )

    client = UserClient(*base_args)
    assert not client.is_authenticated()
    assert client.renew_auth() is auth_info
    assert client.user_uuid == "UUID"
    assert client.access_token == "TOKEN"
    assert client.expires_at == expires_at
    assert client.is_authenticated()


def test_user_request(mocker: MockerFixture, fixed_now, base_args):
    m_renew_auth = mocker.patch.object(UserClient, "renew_auth")
    m_request = mocker.patch.object(UserClient, "_request")

    # No auth and auto_renew=True
    client = UserClient(*base_args, auto_renew=True)
    result = client._user_request("METH", "path", "PARAMS", {"foo": "bar"}, "JSON")

    assert result is m_request.return_value
    m_request.assert_called_once_with(
        "METH", "path", "PARAMS", {"Authorization": "Bearer None", "foo": "bar"}, "JSON"
    )
    m_renew_auth.assert_called_once_with()

    # With valid auth
    m_renew_auth.reset_mock()
    m_request.reset_mock()

    expires_at = fixed_now + dt.timedelta(hours=2)
    client = UserClient(*base_args, "UUID", "TOKEN", expires_at, auto_renew=True)
    result = client._user_request("METH", "path", "PARAMS", {"foo": "bar"}, "JSON")

    assert result is m_request.return_value
    m_request.assert_called_once_with(
        "METH", "path", "PARAMS", {"Authorization": "Bearer TOKEN", "foo": "bar"}, "JSON"
    )
    m_renew_auth.assert_not_called()

    # No auth and auto_renew=False
    m_renew_auth.reset_mock()
    m_request.reset_mock()

    client = UserClient(*base_args, auto_renew=False)
    with pytest.raises(UserAuthenticationError):
        client._user_request("METH", "path", "PARAMS", {"foo": "bar"}, "JSON")
    m_renew_auth.assert_not_called()
    m_request.assert_not_called()
