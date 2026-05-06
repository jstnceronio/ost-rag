from unittest.mock import patch
import pytest
from fastapi import HTTPException
from app.api.deps import verify_api_key


class TestVerifyApiKey:
    def test_valid_key_does_not_raise(self):
        with patch("app.api.deps.settings") as mock_settings:
            mock_settings.api_key = "secret-key"
            verify_api_key("secret-key")  # No exception

    def test_missing_key_raises_401(self):
        with patch("app.api.deps.settings") as mock_settings:
            mock_settings.api_key = "secret-key"
            with pytest.raises(HTTPException) as exc:
                verify_api_key(None)
            assert exc.value.status_code == 401

    def test_wrong_key_raises_401(self):
        with patch("app.api.deps.settings") as mock_settings:
            mock_settings.api_key = "secret-key"
            with pytest.raises(HTTPException) as exc:
                verify_api_key("wrong-key")
            assert exc.value.status_code == 401

    def test_empty_string_raises_401(self):
        with patch("app.api.deps.settings") as mock_settings:
            mock_settings.api_key = "secret-key"
            with pytest.raises(HTTPException) as exc:
                verify_api_key("")
            assert exc.value.status_code == 401
