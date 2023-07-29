import datetime as dt
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, get_type_hints
from unittest.mock import _Call, call, patch

import pytest
import vcr
from pydantic_core import Url

from bridgeapi.base_client import BaseClient
from bridgeapi.client import AppClient, UserClient
from bridgeapi.models import BankCapability, BaseResponseModel

DEMO_BANK_ID = 574
USER_UUID = "998945b4-c977-43e4-a854-d9680fa00fd5"
ITEM_ID = 8170358
ACCOUNT_ID = 37271913


@pytest.fixture
def app_auth() -> dict[str, str | None]:
    return {
        "client_id": os.environ.get("BRIDGEAPI_CLIENT_ID"),
        "client_secret": os.environ.get("BRIDGEAPI_SECRET_ID"),
    }


@pytest.fixture
def app_client(app_auth: dict):
    return AppClient(**app_auth)


@pytest.fixture
def user_auth(app_auth: dict):
    email = "john@doe.com"
    password = "password123"
    client = UserClient(
        **app_auth,
        user_email=email,
        user_password=password,
        auto_renew=False,
    )
    with vcr.use_cassette("tests/cassettes/test_client/user_auth.yaml"):
        client.renew_auth()
    return {
        "user_email": email,
        "user_password": password,
        "user_uuid": client.user_uuid,
        "access_token": client.access_token,
        "expires_at": dt.datetime(3000, 1, 1, tzinfo=dt.timezone.utc),
    }


@pytest.fixture
def user_client(app_auth: dict, user_auth: dict):
    return UserClient(**app_auth, **user_auth, auto_renew=False)


@dataclass
class CaseParameters:
    method: Callable[..., BaseResponseModel]
    call_args: _Call = field(default_factory=call)
    extra_id: str | None = None

    @property
    def case_id(self) -> str:
        if self.extra_id is None:
            return self.method.__name__
        else:
            return f"{self.method.__name__}_{self.extra_id}"


app_client_params = [
    CaseParameters(AppClient.list_banks),
    CaseParameters(AppClient.list_banks, call(countries="fr"), "one_country"),
    CaseParameters(AppClient.list_banks, call(countries=["fr", "de"]), "multi_country"),
    CaseParameters(
        AppClient.list_banks, call(capabilities=BankCapability.BULK_PAYMENT), "one_capability"
    ),
    CaseParameters(
        AppClient.list_banks,
        call(capabilities=[BankCapability.BULK_PAYMENT, BankCapability.BULK_TRANSFER]),
        "multi_capability",
    ),
    CaseParameters(AppClient.list_banks, call(limit=2), "limit"),
    CaseParameters(AppClient.get_bank, call(bank_id=DEMO_BANK_ID)),
    # CaseParameters(AppClient.get_bank_connectors_status),  # Standalone test
    CaseParameters(AppClient.list_users),
    CaseParameters(AppClient.get_user, call(user_uuid=USER_UUID)),
    # CaseParameters(AppClient.create_user),  # User life cycle test
    # CaseParameters(AppClient.delete_user),  # User life cycle test
    # CaseParameters(AppClient.delete_all_users),
    # CaseParameters(AppClient.authenticate_user),  # Happens in user_auth fixture
    # CaseParameters(AppClient.update_user_email),  # User life cycle test
    # CaseParameters(AppClient.update_user_password),  # User life cycle test
    CaseParameters(AppClient.list_categories),
    CaseParameters(AppClient.get_category, call(category_id=1)),
]
app_client_param_ids = [p.case_id for p in app_client_params]


user_client_params = [
    CaseParameters(UserClient.get_email_validation),
    CaseParameters(UserClient.connect_item, call(prefill_email="john@doe.com")),
    CaseParameters(UserClient.edit_item, call(item_id=ITEM_ID, redirect_url="https://test.com")),
    CaseParameters(UserClient.manage_sca_sync_item, call(item_id=ITEM_ID)),
    CaseParameters(UserClient.validate_pro_items),
    CaseParameters(UserClient.manage_accounts_iban),
    CaseParameters(UserClient.list_items),
    CaseParameters(UserClient.get_item, call(item_id=ITEM_ID)),
    CaseParameters(UserClient.refresh_item, call(item_id=ITEM_ID)),
    CaseParameters(UserClient.get_item_refresh_status, call(item_id=ITEM_ID)),
    # CaseParameters(UserClient.delete_item, call(item_id=1)),
    CaseParameters(UserClient.list_accounts),
    CaseParameters(UserClient.get_account, call(account_id=ACCOUNT_ID)),
    CaseParameters(UserClient.list_transactions),
    CaseParameters(UserClient.list_updated_transactions),
    CaseParameters(UserClient.list_account_transactions, call(account_id=ACCOUNT_ID)),
    CaseParameters(UserClient.list_account_updated_transactions, call(account_id=ACCOUNT_ID)),
    CaseParameters(UserClient.list_stocks),
    CaseParameters(UserClient.list_updated_stocks),
    # CaseParameters(UserClient.get_stock, call(stock_id=1)),
]
user_client_param_ids = [p.case_id for p in user_client_params]


def serialize_datetime(val: dt.datetime) -> str:
    s = val.astimezone(dt.timezone.utc).isoformat(sep="T", timespec="milliseconds")
    return s.split("+")[0] + "Z"


def serialize_model(model: BaseResponseModel, default_ser: Callable) -> dict[str, Any]:
    serialized = default_ser(model)
    for field_name, field_value in model:
        if isinstance(field_value, dt.datetime):
            serialized[field_name] = serialize_datetime(field_value)
        if isinstance(field_value, Url) and field_value.path == "/":
            serialized[field_name] = str(field_value).replace("/?", "?")
    return serialized


def assert_json_eq(result: BaseResponseModel) -> None:
    response_json = result.response.json(parse_float=str)
    with patch.object(BaseResponseModel, "serialize", serialize_model, create=True):
        result_json = result.model_dump(mode="json", exclude_unset=True)
    assert response_json == result_json


def check_client_api_method(
    client: BaseClient, method: Callable[..., BaseResponseModel], call_args: _Call
):
    result = method(client, *call_args.args, **call_args.kwargs)

    return_type = get_type_hints(method)["return"]
    if return_type is type(None):
        assert result is None
        return

    assert isinstance(result, return_type)
    assert_json_eq(result)


@pytest.mark.vcr
@pytest.mark.parametrize("params", app_client_params, ids=app_client_param_ids)
def test_app_client(app_client: AppClient, params: CaseParameters):
    check_client_api_method(app_client, params.method, params.call_args)


@pytest.mark.vcr
@pytest.mark.parametrize("params", user_client_params, ids=user_client_param_ids)
def test_user_client(user_client: UserClient, params: CaseParameters):
    check_client_api_method(user_client, params.method, params.call_args)


@pytest.mark.vcr
def test_app_client_get_bank_connectors_status(app_client: AppClient):
    result = app_client.get_bank_connectors_status()
    assert isinstance(result, list)


@pytest.mark.vcr
def test_user_life_cycle(app_client: AppClient):
    email = "foo@email.com"
    email2 = "bar@email.com"
    password = "password123"
    password2 = "yolo"

    user = app_client.create_user(email, password)
    try:
        assert_json_eq(user)
        assert user.email == email

        # 404 errors with update_user_email and update_user_password
        # user = app_client.update_user_email(user.uuid, password, email2)
        # assert_json_eq(user)
        # assert user.email == email2

        # user = app_client.update_user_password(user.uuid, password, password2)
        # assert_json_eq(user)
        # assert user.email == email2
    finally:
        assert app_client.delete_user(user.uuid, password) is None
