# ruff: noqa: A002, A003  # Attribute names shadowing Python builtin
import datetime as dt
import os
from decimal import Decimal
from enum import Enum
from typing import Any, Generic, Literal, TypeVar
from uuid import UUID

import requests
from pydantic import BaseModel, HttpUrl, PrivateAttr, constr, model_serializer

from bridgeapi.base_client import BaseClient
from bridgeapi.exceptions import PaginationError

ModelT = TypeVar("ModelT", bound="BaseResponseModel")


class BaseResponseModel(BaseModel):
    """Base model for all API resources. Allows storing the API response object along
    with the parsed data, accessible through the property `.response`.

    When there are nested models, the response will only be stored on the root
    container, and the property will be None in the children.
    """

    _response: requests.Response | None = PrivateAttr(None)

    @classmethod
    def from_response(cls: type[ModelT], response: requests.Response) -> ModelT:
        value = cls.model_validate(response.json())
        value._response = response
        return value

    @property
    def response(self) -> requests.Response | None:
        return self._response

    if os.environ.get("BRIDGEAPI_MODEL_SERIALIZATION_HOOK") == "1":

        @model_serializer(mode="wrap")
        def _serialize(self, default_ser) -> dict[str, Any]:
            """Hook to turn on custom serialization. Needs redefinition of `.serialize()`.

            Activation of the hook is controlled by the `BRIDGEAPI_MODEL_SERIALIZATION_HOOK`
            environment variable. No performance impact if disabled. Used for tests.
            """
            return self.serialize(default_ser)


_T = TypeVar("_T")


class Pagination(BaseModel):
    next_uri: str | None = None


class PaginatedResult(BaseResponseModel, Generic[_T]):
    """Container storing results of a paginated API call."""

    resources: list[_T]
    pagination: Pagination
    generated_at: dt.datetime | None = None

    _client: "BaseClient" = PrivateAttr()
    _page_number: int = PrivateAttr()

    @classmethod
    def from_response(
        cls, response: requests.Response, client: "BaseClient", page_number: int = 0
    ) -> "PaginatedResult[_T]":
        result = cls.model_validate(response.json())
        result._response = response
        result._client = client
        result._page_number = page_number
        return result

    def has_more(self) -> bool:
        return self.pagination.next_uri is not None

    def next_page(self) -> "PaginatedResult[_T]":
        if self.pagination.next_uri is None:
            msg = "no more results to fetch"
            raise PaginationError(msg)
        response = self._client.request("GET", self.pagination.next_uri)
        return self.__class__.from_response(response, self._client, self._page_number + 1)

    def fetch_all(self) -> list[_T]:
        if self._page_number != 0:
            msg = "paginated result has already been partially consumed"
            raise PaginationError(msg)
        result = self
        resources = result.resources.copy()
        while result.has_more():
            result = result.next_page()
            resources.extend(result.resources)
        return resources


# Banks
class BankFormFieldType(Enum):
    USER = "USER"
    PWD = "PWD"
    PWD2 = "PWD2"


class BankFormField(BaseResponseModel):
    label: str
    type: BankFormFieldType
    isNum: str  # '0' or '1'  # noqa: N815  # mixedCase
    maxLength: int | None = None  # noqa: N815
    minLength: int | None = None  # noqa: N815


class BankTransferProperties(BaseResponseModel):
    nb_max_transactions: int
    max_size_label: int | None = None
    multiple_dates_transfers: bool


class BankPaymentProperties(BaseResponseModel):
    nb_max_transactions: int
    max_size_label: int
    multiple_dates_payments: bool
    sender_iban_available: bool


class BankAuthenticationType(Enum):
    INTERNAL_CREDS = "INTERNAL_CREDS"
    WEBVIEW = "WEBVIEW"


class BankCapability(Enum):
    AIS = "ais"
    ACCOUNT_CHECK = "account_check"
    SINGLE_TRANSFER = "single_transfer"
    BULK_TRANSFER = "bulk_transfer"
    SINGLE_TRANSFER_SCHEDULED = "single_transfer_scheduled"
    BULK_TRANSFER_SCHEDULED = "bulk_transfer_scheduled"
    SINGLE_PAYMENT = "single_payment"
    BULK_PAYMENT = "bulk_payment"
    SINGLE_PAYMENT_SCHEDULED = "single_payment_scheduled"
    BULK_PAYMENT_SCHEDULED = "bulk_payment_scheduled"


class BankChannelType(Enum):
    DSP2 = "dsp2"
    DIRECT_ACCESS = "direct_access"


class Bank(BaseResponseModel):
    id: int
    name: str
    # Known countries as of 2023-07: BE, DE, ES, FR, GB, IT, LU, NL, PT
    country_code: constr(min_length=2, max_length=2)
    logo_url: str  # Should be HttpUrl, but found ""
    authentication_type: BankAuthenticationType
    form: list[BankFormField]
    is_highlighted: bool
    capabilities: list[BankCapability]
    channel_type: list[BankChannelType]
    url: HttpUrl | None = None
    primary_color: str | None = None  # 6 chars hex, ex "007942"
    secondary_color: str | None = None  # 6 chars hex, ex "00AC7B"
    parent_name: str | None = None
    transfer: BankTransferProperties | None = None
    payment: BankPaymentProperties | None = None
    display_order: int | None = None
    authentication_page_url: str | None = None


# Users
class User(BaseResponseModel):
    uuid: UUID
    email: str


class UserAuthInfo(BaseResponseModel):
    access_token: str
    expires_at: dt.datetime
    user: User


class UserEmailValidation(BaseResponseModel):
    name: Literal["email"]
    is_confirmed: bool


# Bridge Connect
class BridgeConnectUrl(BaseResponseModel):
    redirect_url: HttpUrl


# Items
class Item(BaseResponseModel):
    # Codes and documentation at https://docs.bridgeapi.io/reference/item-resource
    id: int
    status: int
    status_code_info: str
    status_code_description: str | None
    bank_id: int


class ItemMfa(BaseResponseModel):
    type: str | None  # SMS or APP_TO_APP
    description: str | None
    label: str
    is_numeric: bool


class ItemRefreshStatus(BaseResponseModel):
    # Codes and documentation at https://docs.bridgeapi.io/reference/get-a-refresh-status
    id: str
    status: str
    refreshed_at: dt.datetime
    mfa: ItemMfa | None
    refreshed_accounts_count: int | None
    total_accounts_count: int | None


# Accounts
class LoanAccountDetails(BaseResponseModel):
    next_payment_date: dt.date
    next_payment_amount: Decimal
    maturity_date: dt.date
    opening_date: dt.date
    interest_rate: float
    type: str
    borrowed_capital: Decimal
    repaid_capital: Decimal
    remaining_capital: Decimal


class SavingsAccountDetails(BaseResponseModel):
    opening_date: dt.date
    interest_rate: float
    ceiling: Decimal


class AccountType(Enum):
    CHECKING = "checking"
    SAVINGS = "savings"
    BROKERAGE = "brokerage"
    CARD = "card"
    LOAN = "loan"
    SHARED_SAVING_PLAN = "shared_saving_plan"
    PENDING = "pending"
    LIFE_INSURANCE = "life_insurance"
    SPECIAL = "special"
    UNKNOWN = "unknown"


class Account(BaseResponseModel):
    id: int
    name: str
    balance: Decimal
    status: int
    status_code_info: str
    status_code_description: str | None
    updated_at: dt.datetime
    type: AccountType
    is_paused: bool
    currency_code: constr(min_length=3, max_length=3)  # 3-letter ISO4217 currency code
    item_id: int
    bank_id: int
    loan_details: LoanAccountDetails | None
    savings_details: SavingsAccountDetails | None
    is_pro: bool
    iban: str | None


# Transactions
class Transaction(BaseResponseModel):
    id: int
    clean_description: str
    bank_description: str
    amount: Decimal
    date: dt.date
    updated_at: dt.datetime
    currency_code: constr(min_length=3, max_length=3)  # 3-letter ISO 4217 currency code
    is_deleted: bool
    category_id: int
    account_id: int
    is_future: bool
    show_client_side: bool


# Stocks
class Stock(BaseResponseModel):
    id: int
    current_price: Decimal
    quantity: Decimal
    total_value: Decimal
    average_purchase_price: Decimal
    updated_at: dt.datetime
    ticker: str  # Stock 4-character identifier
    stock_key: str
    created_at: dt.datetime
    isin: str  # Stock's ISIN identifier (ISO 6166)
    currency_code: constr(min_length=3, max_length=3)  # 3-letter ISO 4217 currency code
    marketplace: str | None
    label: str
    value_date: dt.date
    is_deleted: bool
    account_id: int


# Categories
class Category(BaseResponseModel):
    id: int
    name: str
    parent_id: int | None


class ChildCategory(BaseResponseModel):
    id: int
    name: str


class ParentCategory(BaseResponseModel):
    id: int
    name: str
    categories: list[ChildCategory]
