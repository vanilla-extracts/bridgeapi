"""Clients for the Bridge API (https://bridgeapi.io).
"""

# TODO (20230719):
# * Handle return code of endpoints (200, 202, 204)
# * Check presence of language header
# * Add doc and links to Bridge API doc
# * Sections left to implement:
#   * Payment links: app-scoped
#   * Payment initiation: app-scoped
#   * Bridge transfer: user-scoped, requires sales team activation
#   * Insights: user-scoped, requires sales team activation
#   * Account check: user-scoped
#   * Subscriptions: user-scoped, requires sales team activation

import datetime as dt

import requests

from bridgeapi.base_client import BaseClient
from bridgeapi.exceptions import UserAuthenticationError
from bridgeapi.models import (
    Account,
    Bank,
    BankCapability,
    BridgeConnectUrl,
    Category,
    Item,
    ItemRefreshStatus,
    PaginatedResult,
    ParentCategory,
    Stock,
    Transaction,
    User,
    UserAuthInfo,
    UserEmailValidation,
)


class AppClient(BaseClient):
    """Bridge API client for application-scoped endpoints (not linked to a user context).

    Args:
        client_id (str): Client ID from application credentials.
        client_secret (str): Client secret from application credentials.
    """

    # Banks endpoints
    def list_banks(
        self,
        countries: str | list[str] | None = None,
        capabilities: BankCapability | list[BankCapability] | None = None,
        after: str | None = None,
        limit: int | None = None,
    ) -> PaginatedResult[Bank]:
        params = {
            "countries": countries,
            "capabilities": capabilities,
            "after": after,
            "limit": limit,
        }
        response = self._request("GET", "banks", params)
        return PaginatedResult[Bank].from_response(response, self)

    def get_bank(self, bank_id: int) -> Bank:
        response = self._request("GET", f"banks/{bank_id}")
        return Bank.from_response(response)

    def get_bank_connectors_status(self):
        # TODO (20230719): Deserialization models
        response = self._request("GET", "banks/insights")
        return response.json()

    # Users endpoints
    def list_users(
        self, after: str | None = None, limit: int | None = None
    ) -> PaginatedResult[User]:
        params = {"after": after, "limit": limit}
        response = self._request("GET", "users", params)
        return PaginatedResult[User].from_response(response, self)

    def get_user(self, user_uuid: str) -> User:
        response = self._request("GET", f"users/{user_uuid}")
        return User.from_response(response)

    def create_user(self, email: str, password: str) -> User:
        json_data = {"email": email, "password": password}
        response = self._request("POST", "users", json=json_data)
        return User.from_response(response)

    def delete_user(self, user_uuid: str, password: str = "******") -> None:
        """A password JSON body field is expected, and the documentation states that it
        should be the user's current password, but in practice anything works as long
        as it is at least 6 characters long.
        """
        json_data = {"password": password}
        self._request("POST", f"users/{user_uuid}/delete", json=json_data)

    def delete_all_users(self) -> None:
        """Warning: available in sandbox mode only."""
        self._request("DELETE", "users")

    def authenticate_user(self, email: str, password: str) -> UserAuthInfo:
        json_data = {"email": email, "password": password}
        response = self._request("POST", "authenticate", json=json_data)
        return UserAuthInfo.from_response(response)

    def update_user_email(self, user_uuid: str, password: str, new_email: str) -> User:
        """Will revoke all user's active sessions, they will need to log in again using
        the new info.
        """
        json_data = {"password": password, "new_email": new_email}
        response = self._request("POST", f"users/{user_uuid}/email", json=json_data)
        return User.from_response(response)

    def update_user_password(
        self, user_uuid: str, current_password: str, new_password: str
    ) -> User:
        """Will revoke all user's active sessions, they will need to log in again using
        the new info.
        """
        json_data = {"current_password": current_password, "new_password": new_password}
        response = self._request("POST", f"users/{user_uuid}/password", json=json_data)
        return User.from_response(response)

    # Categories endpoints
    def list_categories(self, language: str | None = None) -> PaginatedResult[ParentCategory]:
        headers = {"Accept-Language": language}
        response = self._request("GET", "categories", headers=headers)
        return PaginatedResult[ParentCategory].from_response(response, self)

    def get_category(self, category_id: int, language: str | None = None) -> Category:
        headers = {"Accept-Language": language}
        response = self._request("GET", f"categories/{category_id}", headers=headers)
        return Category.from_response(response)


class UserClient(BaseClient):
    """Bridge API client for user-scoped endpoints.

    Args:
        client_id (str): Client ID from application credentials.
        client_secret (str): Client secret from application credentials.
        user_email (str): User email from user credentials.
        user_password (str): User password from user credentials.
        user_uuid (str or None, default None): User UUID, if managing auth tokens
            externally.
        access_token (str or None, default None): Auth access token, if managing auth
            tokens externally.
        expires_at (dt.datetime or None, default None): Expiration time, if managing
            auth tokens externally.
        auto_renew (bool, default True): If True, `UserClient` manages user auth
            automatically. Set it to False for manual management.
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        user_email: str,
        user_password: str,
        user_uuid: str | None = None,
        access_token: str | None = None,
        expires_at: dt.datetime | None = None,
        *,
        auto_renew: bool = True,
    ):
        super().__init__(client_id, client_secret)
        self.user_email = user_email
        self.user_password = user_password
        self.auto_renew = auto_renew

        n_auth_args = sum([user_uuid is None, access_token is None, expires_at is None])
        if n_auth_args != 3:  # noqa: PLR2004
            if n_auth_args != 0:
                msg = (
                    "all of [user_uuid, access_token, expires_at] must be passed when setting "
                    "user auth"
                )
                raise ValueError(msg)
            self.user_uuid = user_uuid
            self.access_token = access_token
            self.expires_at = expires_at
        else:
            self.user_uuid = None
            self.access_token = None
            self.expires_at = None

    def is_authenticated(self, delay: dt.timedelta = dt.timedelta(minutes=1)) -> bool:
        """Return whether the user authentication is valid (defined and not expired).

        Args:
            delay (dt.timedelta, default 1 minute): delay by which to anticipate
                renewal before expiration, to avoid edge conditions at expiration time.

        Returns:
            bool: True if user authentication is valid, False otherwise.
        """
        now = dt.datetime.now(dt.timezone.utc)
        return self.access_token is not None and self.expires_at > now + delay

    def renew_auth(self) -> UserAuthInfo:
        """Renew the user access token, valid for 2 hours.

        Returns:
            UserAuthInfo: the UserAuthInfo from the authentication call.
        """
        app_client = AppClient(self.client_id, self.client_secret)
        auth_info = app_client.authenticate_user(self.user_email, self.user_password)
        self.user_uuid = auth_info.user.uuid
        self.access_token = auth_info.access_token
        self.expires_at = auth_info.expires_at
        return auth_info

    def _user_request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        headers: dict | None = None,
        json=None,
    ) -> requests.Response:
        if not self.is_authenticated():
            if self.auto_renew:
                self.renew_auth()
            else:
                msg = "user is not authenticated, call .renew_auth()"
                raise UserAuthenticationError(msg)
        prepared_headers = {"Authorization": f"Bearer {self.access_token}"}
        if headers is not None:
            prepared_headers.update(headers)
        return self._request(method, path, params, prepared_headers, json)

    request = _user_request

    # Users endpoints
    def logout_user(self) -> None:
        self._user_request("POST", "logout")
        self.user_uuid = None
        self.access_token = None
        self.expires_at = None

    def get_email_validation(self) -> UserEmailValidation:
        response = self._user_request("GET", "users/me/email/confirmation")
        return UserEmailValidation.from_response(response)

    # Bridge Connect endpoints
    def connect_item(
        self,
        prefill_email: str,
        country: str | None = None,
        redirect_url: str | None = None,
        context: str | None = None,
        bank_id: int | None = None,
        capabilities: BankCapability | list[BankCapability] | None = None,
    ) -> BridgeConnectUrl:
        json_data = {
            "prefill_email": prefill_email,
            "country": country,
            "redirect_url": redirect_url,
            "context": context,
            "bank_id": bank_id,
            "capabilities": capabilities,
        }
        response = self._user_request("POST", "connect/items/add", json=json_data)
        return BridgeConnectUrl.from_response(response)

    def edit_item(
        self, item_id: int, redirect_url: str | None = None, context: str | None = None
    ) -> BridgeConnectUrl:
        json_data = {
            "item_id": item_id,
            "redirect_url": redirect_url,
            "context": context,
        }
        response = self._user_request("GET", "connect/items/edit", json=json_data)
        return BridgeConnectUrl.from_response(response)

    def manage_sca_sync_item(
        self, item_id: int, redirect_url: str | None = None, context: str | None = None
    ) -> BridgeConnectUrl:
        json_data = {
            "item_id": item_id,
            "redirect_url": redirect_url,
            "context": context,
        }
        response = self._user_request("GET", "connect/items/sync", json=json_data)
        return BridgeConnectUrl.from_response(response)

    def validate_pro_items(
        self, redirect_url: str | None = None, context: str | None = None
    ) -> BridgeConnectUrl:
        json_data = {"redirect_url": redirect_url, "context": context}
        response = self._user_request("GET", "connect/items/pro/confirmation", json=json_data)
        return BridgeConnectUrl.from_response(response)

    def manage_accounts_iban(
        self, redirect_url: str | None = None, context: str | None = None
    ) -> BridgeConnectUrl:
        json_data = {"redirect_url": redirect_url, "context": context}
        response = self._user_request("GET", "connect/manage/accounts/iban", json=json_data)
        return BridgeConnectUrl.from_response(response)

    # Items endpoints
    def list_items(
        self,
        after: str | None = None,
        limit: int | None = None,
        language: str | None = None,
    ) -> PaginatedResult[Item]:
        params = {"after": after, "limit": limit}
        headers = {"Accept-Language": language} if language is not None else None
        response = self._user_request("GET", "items", params=params, headers=headers)
        return PaginatedResult[Item].from_response(response, self)

    def get_item(self, item_id: int, language: str | None = None) -> Item:
        headers = {"Accept-Language": language} if language is not None else None
        response = self._user_request("GET", f"items/{item_id}", headers=headers)
        return Item.from_response(response)

    def refresh_item(self, item_id: int) -> None:
        self._user_request("POST", f"items/{item_id}/refresh")

    def get_item_refresh_status(self, item_id: int) -> ItemRefreshStatus:
        response = self._user_request("GET", f"items/{item_id}/refresh/status")
        return ItemRefreshStatus.from_response(response)

    def delete_item(self, item_id: int) -> None:
        self._user_request("DELETE", f"items/{item_id}")

    # Accounts endpoints
    def list_accounts(
        self,
        item_id: int | None = None,
        after: str | None = None,
        limit: int | None = None,
    ) -> PaginatedResult[Account]:
        params = {"item_id": item_id, "after": after, "limit": limit}
        response = self._user_request("GET", "accounts", params=params)
        return PaginatedResult[Account].from_response(response, self)

    def get_account(self, account_id: int) -> Account:
        response = self._user_request("GET", f"accounts/{account_id}")
        return Account.from_response(response)

    # Transactions endpoints
    def list_transactions(
        self,
        since: dt.date | None = None,
        until: dt.date | None = None,
        after: str | None = None,
        limit: int | None = None,
    ) -> PaginatedResult[Transaction]:
        params = {"since": since, "until": until, "after": after, "limit": limit}
        response = self._user_request("GET", "transactions", params=params)
        return PaginatedResult[Transaction].from_response(response, self)

    def list_updated_transactions(
        self,
        since: dt.datetime | None = None,
        after: str | None = None,
        limit: int | None = None,
    ) -> PaginatedResult[Transaction]:
        params = {"since": since, "after": after, "limit": limit}
        response = self._user_request("GET", "transactions/updated", params=params)
        return PaginatedResult[Transaction].from_response(response, self)

    def get_transaction(self, transaction_id: int) -> Transaction:
        response = self._user_request("GET", f"transactions/{transaction_id}")
        return Transaction.from_response(response)

    def list_account_transactions(
        self,
        account_id: int,
        since: dt.date | None = None,
        until: dt.date | None = None,
        after: str | None = None,
        limit: int | None = None,
    ) -> PaginatedResult[Transaction]:
        params = {"since": since, "until": until, "after": after, "limit": limit}
        response = self._user_request("GET", f"accounts/{account_id}/transactions", params=params)
        return PaginatedResult[Transaction].from_response(response, self)

    def list_account_updated_transactions(
        self,
        account_id: int,
        since: dt.datetime | None = None,
        after: str | None = None,
        limit: int | None = None,
    ) -> PaginatedResult[Transaction]:
        params = {"since": since, "after": after, "limit": limit}
        response = self._user_request(
            "GET", f"accounts/{account_id}/transactions/updated", params=params
        )
        return PaginatedResult[Transaction].from_response(response, self)

    # Stocks endpoints
    def list_stocks(
        self, after: str | None = None, limit: int | None = None
    ) -> PaginatedResult[Stock]:
        params = {"after": after, "limit": limit}
        response = self._user_request("GET", "stocks", params=params)
        return PaginatedResult[Stock].from_response(response, self)

    def list_updated_stocks(
        self,
        since: dt.datetime | None = None,
        after: str | None = None,
        limit: int | None = None,
    ) -> PaginatedResult[Stock]:
        params = {"since": since, "after": after, "limit": limit}
        response = self._user_request("GET", "stocks/updated", params=params)
        return PaginatedResult[Stock].from_response(response, self)

    def get_stock(self, stock_id: int) -> Stock:
        response = self._user_request("GET", f"stocks/{stock_id}")
        return Stock.from_response(response)
