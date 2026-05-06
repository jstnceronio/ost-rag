from app.confluence.errors import ConfluenceAPIError


def test_error_message_format():
    err = ConfluenceAPIError(404, "Not Found", "https://wiki.example.com/rest/api/content/99")
    assert "404" in str(err)
    assert "https://wiki.example.com/rest/api/content/99" in str(err)


def test_error_stores_attributes():
    err = ConfluenceAPIError(500, "Internal Error", "https://wiki.example.com/")
    assert err.status_code == 500
    assert err.message == "Internal Error"
    assert err.url == "https://wiki.example.com/"


def test_error_is_exception():
    err = ConfluenceAPIError(401, "Unauthorized", "https://wiki.example.com/")
    with pytest.raises(Exception):
        raise err


import pytest
