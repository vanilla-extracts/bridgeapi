import pytest
from pytest_mock import MockerFixture

from bridgeapi.exceptions import PaginationError
from bridgeapi.models import PaginatedResult, Pagination


@pytest.fixture
def json_data() -> list:
    return [
        {"resources": [{"page": 0}], "pagination": {"next_uri": "NEXT_URI"}},
        {"resources": [{"page": 1}], "pagination": {"next_uri": None}},
    ]


@pytest.fixture
def responses(mocker: MockerFixture, json_data):
    return [
        mocker.Mock(json=mocker.Mock(return_value=json_data[0])),
        mocker.Mock(json=mocker.Mock(return_value=json_data[1])),
    ]


@pytest.fixture
def client(mocker: MockerFixture, responses):
    return mocker.Mock(request=mocker.Mock(return_value=responses[1]))


def test_pagination(responses, client):
    result0 = PaginatedResult.from_response(responses[0], client)
    assert result0.resources == [{"page": 0}]
    assert result0.pagination == Pagination(next_uri="NEXT_URI")
    assert result0.response is responses[0]
    assert result0._client is client
    assert result0._page_number == 0
    assert result0.has_more()

    result1 = result0.next_page()
    assert result1.resources == [{"page": 1}]
    assert result1.pagination == Pagination(next_uri=None)
    assert result1.response is responses[1]
    assert result1._client is client
    assert result1._page_number == 1
    assert not result1.has_more()

    with pytest.raises(PaginationError):
        result1.next_page()

    assert result0.fetch_all() == result0.resources + result1.resources

    with pytest.raises(PaginationError):
        result1.fetch_all()
