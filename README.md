# bridgeapi

[![PyPI - Version](https://img.shields.io/pypi/v/bridgeapi.svg)](https://pypi.org/project/bridgeapi)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/bridgeapi.svg)](https://pypi.org/project/bridgeapi)

-----

`bridgeapi` is a client for the [Bridge open banking API aggregator](https://bridgeapi.io).

## Requirements

Python 3.10+

## Installation

```console
pip install bridgeapi
```

## Example

```python
from bridgeapi import AppClient, UserClient

app_client = AppClient("CLIENT_ID", "CLIENT_SECRET")
print(app_client.list_banks())
print(app_client.list_users())
print(app_client.create_user("john@doe.com", "password"))

user_client = UserClient("CLIENT_ID", "CLIENT_SECRET", "john@doe.com", "password")
print(user_client.list_items())
print(user_client.connect_item())
print(user_client.list_accounts())
print(user_client.list_transactions())
```

API endpoints are split between two clients:
* `AppClient` handles all application-scoped endpoints, that don't depend on a user being
  authenticated. It only needs (client_id, client_secret) credentials to communicate with the API.
* `UserClient` handles user-scoped endpoints, those that are specific to a user and require an
  access token and the `Authorization` header to communicate with the API. It needs (user_email,
  user_password) credentials, in addition to the same client credentials as `AppClient`.

## Authentication management with `UserClient`

The simplest usage of `UserClient` is to it handle all the authorization lifecyle. It will
automatically obtain an access token and renew it when it expires (after 2 hours):

```python
user_client = UserClient("CLIENT_ID", "CLIENT_SECRET", "john@doe.com", "password")
print(user_client.list_items())  # OK

# 2+ hours later
print(user_client.list_items())  # OK
```

If you wish to manage the user authorization lifecycle yourself, pass `auto_renew=False` at
creation. You will need to call `.renew_auth()` manually:

```python
user_client = UserClient(
    "CLIENT_ID", "CLIENT_SECRET", "john@doe.com", "password", auto_renew=False
)
print(user_client.is_authenticated())  # False
user_client.list_items()  # UserAuthenticationError

user_client.renew_auth()
print(user_client.is_authenticated())  # True
print(user_client.list_items())  # OK

# 2+ hours later
print(user_client.is_authenticated())  # False
user_client.renew_auth()
print(user_client.is_authenticated())  # True
```

Additionally, if you are managing user tokens externally and persisting them to external storage,
you can provide them at creation as well:

```python
user_client = UserClient(
    "CLIENT_ID",
    "CLIENT_SECRET",
    "john@doe.com",
    "password",
    user_uuid="uuid",
    access_token="token",
    expires_at="yyyy-mm-dd HH:MM:SS",
    auto_renew=False,
)
print(user_client.is_authenticated())  # True
user_client.list_items()  # OK

# Generate and store new authorization info
auth_info = user_client.renew_auth()
store_user_auth_to_db(
    user_email=auth_info.user.email,
    user_uuid=auth_info.user.uuid,
    access_token=auth_info.access_token,
    expires_at=auth_info.expires_at,
)
```

## License

`bridgeapi` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.
