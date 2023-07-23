import requests
from pydantic import BaseModel


class BridgeAPIError(Exception):
    pass


class PaginationError(BridgeAPIError):
    pass


class UserAuthenticationError(BridgeAPIError):
    pass


class ErrorResponseData(BaseModel):
    type: str  # noqa: A003  # Attribute shadowing Python builtin
    message: str
    documentation_url: str | None


class RequestError(BridgeAPIError):
    def __init__(self, response, status_code: int, response_data: ErrorResponseData):
        self.response = response
        self.status_code = status_code
        self.response_data = response_data

    @classmethod
    def from_response(cls, response: requests.Response) -> "RequestError":
        response_data = ErrorResponseData.parse_obj(response.json())
        return cls(response, response.status_code, response_data)

    def __str__(self) -> str:
        msg = (
            f"HTTP error {self.status_code} ({self.response_data.type}) upon request to URL "
            f"{self.response.url}"
        )
        if self.response_data.message is not None:
            msg += f": {self.response_data.message!r}"
        if self.response_data.documentation_url is not None:
            msg += f" (see {self.response_data.documentation_url})"
        return msg
