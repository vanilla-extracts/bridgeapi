from urllib.parse import urljoin

import requests

from bridgeapi.exceptions import RequestError


class BaseClient:
    base_url = "https://api.bridgeapi.io/v2/"
    api_version = "2021-06-01"

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.session = requests.Session()

    def _request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        headers: dict | None = None,
        json=None,
    ) -> requests.Response:
        prepared_headers = {
            "Bridge-Version": self.api_version,
            "Client-Id": self.client_id,
            "Client-Secret": self.client_secret,
            "Content-Type": "application/json",
        }
        if headers is not None:
            prepared_headers.update(headers)
        response = self.session.request(
            method,
            urljoin(self.base_url, path),
            params=params,
            headers=prepared_headers,
            json=json,
        )
        if 200 <= response.status_code < 300:  # noqa: PLR2004
            return response
        raise RequestError.from_response(response)

    request = _request
