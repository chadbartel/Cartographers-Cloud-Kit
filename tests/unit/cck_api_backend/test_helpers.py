# Standard Library
import base64
from unittest.mock import patch

# Third Party
import pytest

# My Modules
from api_backend.utils.helpers import extract_username_from_basic_auth


class TestExtractUsernameFromBasicAuth:
    """Test cases for extract_username_from_basic_auth function."""

    def test_extract_username_valid_credentials(self):
        """Test successful extraction of username from valid credentials."""
        # Arrange
        username = "testuser"
        password = "testpassword"
        credentials = f"{username}:{password}"
        encoded_credentials = base64.b64encode(
            credentials.encode("utf-8")
        ).decode("utf-8")

        # Act
        result = extract_username_from_basic_auth(encoded_credentials)

        # Assert
        assert result == username

    def test_extract_username_with_special_characters(self):
        """Test extraction with username containing special characters."""
        # Arrange
        username = "user@example.com"
        password = "p@ssw0rd!"
        credentials = f"{username}:{password}"
        encoded_credentials = base64.b64encode(
            credentials.encode("utf-8")
        ).decode("utf-8")

        # Act
        result = extract_username_from_basic_auth(encoded_credentials)

        # Assert
        assert result == username

    def test_extract_username_with_empty_password(self):
        """Test extraction when password is empty."""
        # Arrange
        username = "testuser"
        password = ""
        credentials = f"{username}:{password}"
        encoded_credentials = base64.b64encode(
            credentials.encode("utf-8")
        ).decode("utf-8")

        # Act
        result = extract_username_from_basic_auth(encoded_credentials)

        # Assert
        assert result == username

    def test_extract_username_with_empty_username(self):
        """Test extraction when username is empty."""
        # Arrange
        username = ""
        password = "testpassword"
        credentials = f"{username}:{password}"
        encoded_credentials = base64.b64encode(
            credentials.encode("utf-8")
        ).decode("utf-8")

        # Act
        result = extract_username_from_basic_auth(encoded_credentials)

        # Assert
        assert result == username

    def test_extract_username_with_multiple_colons(self):
        """Test extraction when password contains colons."""
        # Arrange
        username = "testuser"
        password = "pass:word:with:colons"
        credentials = f"{username}:{password}"
        encoded_credentials = base64.b64encode(
            credentials.encode("utf-8")
        ).decode("utf-8")

        # Act
        result = extract_username_from_basic_auth(encoded_credentials)

        # Assert
        assert result == username

    def test_extract_username_missing_colon_separator(self):
        """Test handling of credentials without colon separator."""
        # Arrange
        credentials_without_colon = "usernamewithoutcolon"
        encoded_credentials = base64.b64encode(
            credentials_without_colon.encode("utf-8")
        ).decode("utf-8")

        # Act
        with patch("api_backend.utils.helpers.logger") as mock_logger:
            result = extract_username_from_basic_auth(encoded_credentials)

        # Assert
        assert result is None
        mock_logger.error.assert_called_once_with(
            "Failed to extract username from Basic Auth credentials",
            exc_info=True,
        )

    def test_extract_username_invalid_base64(self):
        """Test handling of invalid Base64 encoded credentials."""
        # Arrange
        invalid_base64 = "this-is-not-valid-base64!!!"

        # Act
        with patch("api_backend.utils.helpers.logger") as mock_logger:
            result = extract_username_from_basic_auth(invalid_base64)

        # Assert
        assert result is None
        mock_logger.error.assert_called_once_with(
            "Failed to extract username from Basic Auth credentials",
            exc_info=True,
        )

    def test_extract_username_invalid_utf8_after_base64_decode(self):
        """Test handling of valid Base64 that decodes to invalid UTF-8."""
        # Arrange
        # Create valid Base64 that decodes to invalid UTF-8
        invalid_utf8_bytes = b"\xff\xfe\xfd"
        encoded_credentials = base64.b64encode(invalid_utf8_bytes).decode(
            "utf-8"
        )

        # Act
        with patch("api_backend.utils.helpers.logger") as mock_logger:
            result = extract_username_from_basic_auth(encoded_credentials)

        # Assert
        assert result is None
        mock_logger.error.assert_called_once_with(
            "Failed to extract username from Basic Auth credentials",
            exc_info=True,
        )

    def test_extract_username_empty_string(self):
        """Test handling of empty string input."""
        # Arrange
        empty_string = ""

        # Act
        with patch("api_backend.utils.helpers.logger") as mock_logger:
            result = extract_username_from_basic_auth(empty_string)

        # Assert
        assert result is None
        mock_logger.error.assert_called_once_with(
            "Failed to extract username from Basic Auth credentials",
            exc_info=True,
        )

    def test_extract_username_none_input(self):
        """Test handling of None input."""
        # Arrange
        none_input = None

        # Act
        with patch("api_backend.utils.helpers.logger") as mock_logger:
            # This will raise TypeError, but function catches all exceptions
            result = extract_username_from_basic_auth(none_input)

        # Assert
        assert result is None
        mock_logger.error.assert_called_once_with(
            "Failed to extract username from Basic Auth credentials",
            exc_info=True,
        )

    def test_extract_username_unicode_characters(self):
        """Test extraction with Unicode characters in username and password."""
        # Arrange
        username = "测试用户"  # Chinese characters
        password = "パスワード"  # Japanese characters
        credentials = f"{username}:{password}"
        encoded_credentials = base64.b64encode(
            credentials.encode("utf-8")
        ).decode("utf-8")

        # Act
        result = extract_username_from_basic_auth(encoded_credentials)

        # Assert
        assert result == username

    @pytest.mark.parametrize(
        "username,password",
        [
            ("user1", "pass1"),
            ("admin", "admin123"),
            ("test.user@domain.com", "complex!P@ssw0rd"),
            ("user_with_underscores", "simple"),
            ("123numeric", "456789"),
        ],
    )
    def test_extract_username_parametrized_valid_cases(
        self, username, password
    ):
        """Test multiple valid username/password combinations."""
        # Arrange
        credentials = f"{username}:{password}"
        encoded_credentials = base64.b64encode(
            credentials.encode("utf-8")
        ).decode("utf-8")

        # Act
        result = extract_username_from_basic_auth(encoded_credentials)

        # Assert
        assert result == username

    def test_extract_username_with_padding_variations(self):
        """Test with different Base64 padding scenarios."""
        # Arrange
        username = "usr"  # Will create Base64 with padding
        password = "pwd"
        credentials = f"{username}:{password}"
        encoded_credentials = base64.b64encode(
            credentials.encode("utf-8")
        ).decode("utf-8")

        # Act
        result = extract_username_from_basic_auth(encoded_credentials)

        # Assert
        assert result == username
        # Verify that the encoded string has padding
        assert encoded_credentials.endswith("=")

    def test_extract_username_logger_service_initialization(self):
        """Test that logger is properly initialized with service name."""
        # This test verifies the module-level logger initialization
        from api_backend.utils.helpers import logger

        # Assert
        assert logger.service == "api_backend.utils.helpers"
