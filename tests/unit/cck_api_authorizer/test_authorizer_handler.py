# Standard Library
import base64
from typing import Any, Dict
from unittest.mock import MagicMock, patch

# Third Party
import pytest
from botocore.exceptions import ClientError

# My Modules
from tests.conftest import import_handler


@pytest.fixture
def handler_module():
    """Import the handler module using the import_handler function."""
    return import_handler("cck-api-authorizer")


@pytest.fixture
def valid_event() -> Dict[str, Any]:
    """Create a valid Lambda event for testing."""
    # Create base64 encoded username:password
    credentials = "testuser:password123"
    encoded_token = base64.b64encode(credentials.encode("utf-8")).decode(
        "utf-8"
    )

    return {
        "authorizationToken": encoded_token,
        "methodArn": "arn:aws:execute-api:us-east-1:123456789012:abcdef123/"
        "test/GET/users",
    }


@pytest.fixture
def lambda_context():
    """Create a mock Lambda context object."""
    context = MagicMock()
    context.function_name = "test-function"
    context.function_version = "1"
    context.invoked_function_arn = (
        "arn:aws:lambda:us-east-1:123456789012:function:test-function"
    )
    context.memory_limit_in_mb = 128
    context.remaining_time_in_millis = lambda: 30000
    context.aws_request_id = "test-request-id"
    return context


def test_lambda_handler_successful_authentication(
    handler_module, valid_event, lambda_context
):
    """Test successful authentication with valid credentials."""
    # Arrange
    mock_cognito_client = MagicMock()
    mock_cognito_client.admin_initiate_auth.return_value = {
        "AuthenticationResult": {
            "AccessToken": "mock-access-token",
            "IdToken": "mock-id-token",
            "RefreshToken": "mock-refresh-token",
        }
    }

    mock_policy = {
        "principalId": "testuser",
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": "Allow",
                    "Resource": valid_event["methodArn"],
                }
            ],
        },
    }

    with (
        patch.object(
            handler_module,
            "get_cognito_client",
            return_value=mock_cognito_client,
        ),
        patch.object(
            handler_module,
            "generate_policy",
            return_value=mock_policy,
        ),
        patch.object(
            handler_module, "USER_POOL_ID", "test-pool-id"
        ),
        patch.object(
            handler_module,
            "USER_POOL_CLIENT_ID",
            "test-client-id",
        ),
    ):
        # Act
        result = handler_module.lambda_handler(valid_event, lambda_context)

        # Assert
        assert result == mock_policy
        mock_cognito_client.admin_initiate_auth.assert_called_once_with(
            UserPoolId="test-pool-id",
            ClientId="test-client-id",
            AuthFlow="ADMIN_NO_SRP_AUTH",
            AuthParameters={"USERNAME": "testuser", "PASSWORD": "password123"},
        )


def test_lambda_handler_cognito_client_not_initialized(
    handler_module, valid_event, lambda_context
):
    """Test exception when Cognito client is not initialized."""
    # Arrange
    with patch.object(
        handler_module, "get_cognito_client", return_value=None
    ):
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            handler_module.lambda_handler(valid_event, lambda_context)

        assert "Unauthorized: Authorizer internal configuration error" in str(
            exc_info.value
        )


def test_lambda_handler_missing_user_pool_id(
    handler_module, valid_event, lambda_context
):
    """Test exception when USER_POOL_ID is not configured."""
    # Arrange
    mock_cognito_client = MagicMock()

    with (
        patch.object(
            handler_module,
            "get_cognito_client",
            return_value=mock_cognito_client,
        ),
        patch.object(handler_module, "USER_POOL_ID", None),
        patch.object(
            handler_module,
            "USER_POOL_CLIENT_ID",
            "test-client-id",
        ),
    ):
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            handler_module.lambda_handler(valid_event, lambda_context)

        assert "Unauthorized: Authorizer configuration error" in str(
            exc_info.value
        )


def test_lambda_handler_missing_user_pool_client_id(
    handler_module, valid_event, lambda_context
):
    """Test exception when USER_POOL_CLIENT_ID is not configured."""
    # Arrange
    mock_cognito_client = MagicMock()

    with (
        patch.object(
            handler_module,
            "get_cognito_client",
            return_value=mock_cognito_client,
        ),
        patch.object(
            handler_module, "USER_POOL_ID", "test-pool-id"
        ),
        patch.object(
            handler_module, "USER_POOL_CLIENT_ID", None
        ),
    ):
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            handler_module.lambda_handler(valid_event, lambda_context)

        assert "Unauthorized: Authorizer configuration error" in str(
            exc_info.value
        )


def test_lambda_handler_missing_authorization_token(
    handler_module, lambda_context
):
    """Test exception when authorization token is not provided."""
    # Arrange
    event = {
        "methodArn": "arn:aws:execute-api:us-east-1:123456789012:abcdef123/test/GET/users"
    }
    mock_cognito_client = MagicMock()

    with (
        patch.object(
            handler_module,
            "get_cognito_client",
            return_value=mock_cognito_client,
        ),
        patch.object(
            handler_module, "USER_POOL_ID", "test-pool-id"
        ),
        patch.object(
            handler_module,
            "USER_POOL_CLIENT_ID",
            "test-client-id",
        ),
    ):
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            handler_module.lambda_handler(event, lambda_context)

        assert "Unauthorized" in str(exc_info.value)


def test_lambda_handler_empty_authorization_token(
    handler_module, lambda_context
):
    """Test exception when authorization token is empty."""
    # Arrange
    event = {
        "authorizationToken": "",
        "methodArn": "arn:aws:execute-api:us-east-1:123456789012:abcdef123/test/GET/users",
    }
    mock_cognito_client = MagicMock()

    with (
        patch.object(
            handler_module,
            "get_cognito_client",
            return_value=mock_cognito_client,
        ),
        patch.object(
            handler_module, "USER_POOL_ID", "test-pool-id"
        ),
        patch.object(
            handler_module,
            "USER_POOL_CLIENT_ID",
            "test-client-id",
        ),
    ):
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            handler_module.lambda_handler(event, lambda_context)

        assert "Unauthorized" in str(exc_info.value)


def test_lambda_handler_invalid_base64_token(handler_module, lambda_context):
    """Test exception when authorization token is not valid base64."""
    # Arrange
    event = {
        "authorizationToken": "invalid-base64!",
        "methodArn": "arn:aws:execute-api:us-east-1:123456789012:abcdef123/test/GET/users",
    }
    mock_cognito_client = MagicMock()

    with (
        patch.object(
            handler_module,
            "get_cognito_client",
            return_value=mock_cognito_client,
        ),
        patch.object(
            handler_module, "USER_POOL_ID", "test-pool-id"
        ),
        patch.object(
            handler_module,
            "USER_POOL_CLIENT_ID",
            "test-client-id",
        ),
    ):
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            handler_module.lambda_handler(event, lambda_context)

        assert "Unauthorized" in str(exc_info.value)


def test_lambda_handler_invalid_utf8_after_base64(
    handler_module, lambda_context
):
    """Test exception when decoded base64 is not valid UTF-8."""
    # Arrange
    # Create invalid UTF-8 bytes and encode to base64
    invalid_utf8_bytes = b"\xff\xfe"
    encoded_token = base64.b64encode(invalid_utf8_bytes).decode("utf-8")

    event = {
        "authorizationToken": encoded_token,
        "methodArn": "arn:aws:execute-api:us-east-1:123456789012:abcdef123/test/GET/users",
    }
    mock_cognito_client = MagicMock()

    with (
        patch.object(
            handler_module,
            "get_cognito_client",
            return_value=mock_cognito_client,
        ),
        patch.object(
            handler_module, "USER_POOL_ID", "test-pool-id"
        ),
        patch.object(
            handler_module,
            "USER_POOL_CLIENT_ID",
            "test-client-id",
        ),
    ):
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            handler_module.lambda_handler(event, lambda_context)

        assert "Unauthorized" in str(exc_info.value)


def test_lambda_handler_missing_colon_separator(
    handler_module, lambda_context
):
    """Test exception when token format is missing colon separator."""
    # Arrange
    credentials = "testuserpassword123"  # No colon
    encoded_token = base64.b64encode(credentials.encode("utf-8")).decode(
        "utf-8"
    )

    event = {
        "authorizationToken": encoded_token,
        "methodArn": "arn:aws:execute-api:us-east-1:123456789012:abcdef123/test/GET/users",
    }
    mock_cognito_client = MagicMock()

    with (
        patch.object(
            handler_module,
            "get_cognito_client",
            return_value=mock_cognito_client,
        ),
        patch.object(
            handler_module, "USER_POOL_ID", "test-pool-id"
        ),
        patch.object(
            handler_module,
            "USER_POOL_CLIENT_ID",
            "test-client-id",
        ),
    ):
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            handler_module.lambda_handler(event, lambda_context)

        assert "Unauthorized" in str(exc_info.value)


def test_lambda_handler_empty_username(handler_module, lambda_context):
    """Test exception when username is empty after decoding."""
    # Arrange
    credentials = ":password123"  # Empty username
    encoded_token = base64.b64encode(credentials.encode("utf-8")).decode(
        "utf-8"
    )

    event = {
        "authorizationToken": encoded_token,
        "methodArn": "arn:aws:execute-api:us-east-1:123456789012:abcdef123/test/GET/users",
    }
    mock_cognito_client = MagicMock()

    with (
        patch.object(
            handler_module,
            "get_cognito_client",
            return_value=mock_cognito_client,
        ),
        patch.object(
            handler_module, "USER_POOL_ID", "test-pool-id"
        ),
        patch.object(
            handler_module,
            "USER_POOL_CLIENT_ID",
            "test-client-id",
        ),
    ):
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            handler_module.lambda_handler(event, lambda_context)

        assert "Unauthorized" in str(exc_info.value)


def test_lambda_handler_empty_password(handler_module, lambda_context):
    """Test exception when password is empty after decoding."""
    # Arrange
    credentials = "testuser:"  # Empty password
    encoded_token = base64.b64encode(credentials.encode("utf-8")).decode(
        "utf-8"
    )

    event = {
        "authorizationToken": encoded_token,
        "methodArn": "arn:aws:execute-api:us-east-1:123456789012:abcdef123/test/GET/users",
    }
    mock_cognito_client = MagicMock()

    with (
        patch.object(
            handler_module,
            "get_cognito_client",
            return_value=mock_cognito_client,
        ),
        patch.object(
            handler_module, "USER_POOL_ID", "test-pool-id"
        ),
        patch.object(
            handler_module,
            "USER_POOL_CLIENT_ID",
            "test-client-id",
        ),
    ):
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            handler_module.lambda_handler(event, lambda_context)

        assert "Unauthorized" in str(exc_info.value)


def test_lambda_handler_cognito_challenge_response(
    handler_module, valid_event, lambda_context
):
    """Test exception when Cognito returns challenge instead of auth result."""
    # Arrange
    mock_cognito_client = MagicMock()
    mock_cognito_client.admin_initiate_auth.return_value = {
        "ChallengeName": "NEW_PASSWORD_REQUIRED",
        "Session": "mock-session",
    }

    with (
        patch.object(
            handler_module,
            "get_cognito_client",
            return_value=mock_cognito_client,
        ),
        patch.object(
            handler_module, "USER_POOL_ID", "test-pool-id"
        ),
        patch.object(
            handler_module,
            "USER_POOL_CLIENT_ID",
            "test-client-id",
        ),
    ):
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            handler_module.lambda_handler(valid_event, lambda_context)

        assert "Unauthorized" in str(exc_info.value)


def test_lambda_handler_cognito_user_not_found(
    handler_module, valid_event, lambda_context
):
    """Test exception when Cognito user is not found."""
    # Arrange
    mock_cognito_client = MagicMock()
    mock_cognito_client.admin_initiate_auth.side_effect = ClientError(
        error_response={
            "Error": {
                "Code": "UserNotFoundException",
                "Message": "User does not exist",
            }
        },
        operation_name="AdminInitiateAuth",
    )

    with (
        patch.object(
            handler_module,
            "get_cognito_client",
            return_value=mock_cognito_client,
        ),
        patch.object(
            handler_module, "USER_POOL_ID", "test-pool-id"
        ),
        patch.object(
            handler_module,
            "USER_POOL_CLIENT_ID",
            "test-client-id",
        ),
    ):
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            handler_module.lambda_handler(valid_event, lambda_context)

        assert "Unauthorized" in str(exc_info.value)


def test_lambda_handler_cognito_not_authorized(
    handler_module, valid_event, lambda_context
):
    """Test exception when Cognito authentication is not authorized."""
    # Arrange
    mock_cognito_client = MagicMock()
    mock_cognito_client.admin_initiate_auth.side_effect = ClientError(
        error_response={
            "Error": {
                "Code": "NotAuthorizedException",
                "Message": "Incorrect username or password",
            }
        },
        operation_name="AdminInitiateAuth",
    )

    with (
        patch.object(
            handler_module,
            "get_cognito_client",
            return_value=mock_cognito_client,
        ),
        patch.object(
            handler_module, "USER_POOL_ID", "test-pool-id"
        ),
        patch.object(
            handler_module,
            "USER_POOL_CLIENT_ID",
            "test-client-id",
        ),
    ):
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            handler_module.lambda_handler(valid_event, lambda_context)

        assert "Unauthorized" in str(exc_info.value)


def test_lambda_handler_cognito_invalid_parameter(
    handler_module, valid_event, lambda_context
):
    """Test exception when Cognito receives invalid parameters."""
    # Arrange
    mock_cognito_client = MagicMock()
    mock_cognito_client.admin_initiate_auth.side_effect = ClientError(
        error_response={
            "Error": {
                "Code": "InvalidParameterException",
                "Message": "Invalid parameter",
            }
        },
        operation_name="AdminInitiateAuth",
    )

    with (
        patch.object(
            handler_module,
            "get_cognito_client",
            return_value=mock_cognito_client,
        ),
        patch.object(
            handler_module, "USER_POOL_ID", "test-pool-id"
        ),
        patch.object(
            handler_module,
            "USER_POOL_CLIENT_ID",
            "test-client-id",
        ),
    ):
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            handler_module.lambda_handler(valid_event, lambda_context)

        assert "Unauthorized" in str(exc_info.value)


def test_lambda_handler_cognito_other_client_error(
    handler_module, valid_event, lambda_context
):
    """Test exception for other Cognito client errors."""
    # Arrange
    mock_cognito_client = MagicMock()
    mock_cognito_client.admin_initiate_auth.side_effect = ClientError(
        error_response={
            "Error": {"Code": "SomeOtherError", "Message": "Some other error"}
        },
        operation_name="AdminInitiateAuth",
    )

    with (
        patch.object(
            handler_module,
            "get_cognito_client",
            return_value=mock_cognito_client,
        ),
        patch.object(
            handler_module, "USER_POOL_ID", "test-pool-id"
        ),
        patch.object(
            handler_module,
            "USER_POOL_CLIENT_ID",
            "test-client-id",
        ),
    ):
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            handler_module.lambda_handler(valid_event, lambda_context)

        assert "Unauthorized" in str(exc_info.value)


def test_lambda_handler_unexpected_exception(
    handler_module, valid_event, lambda_context
):
    """Test exception for unexpected errors during token validation."""
    # Arrange
    mock_cognito_client = MagicMock()
    mock_cognito_client.admin_initiate_auth.side_effect = ValueError(
        "Unexpected error"
    )

    with (
        patch.object(
            handler_module,
            "get_cognito_client",
            return_value=mock_cognito_client,
        ),
        patch.object(
            handler_module, "USER_POOL_ID", "test-pool-id"
        ),
        patch.object(
            handler_module,
            "USER_POOL_CLIENT_ID",
            "test-client-id",
        ),
    ):
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            handler_module.lambda_handler(valid_event, lambda_context)

        assert "Unauthorized" in str(exc_info.value)


@pytest.mark.parametrize(
    "username,password",
    [
        ("user", "pass"),
        ("test@example.com", "Password123!"),
        ("user123", "mypassword"),
        ("admin", "admin123"),
    ],
)
def test_lambda_handler_various_credentials(
    handler_module, lambda_context, username, password
):
    """Test handler with various username/password combinations."""
    # Arrange
    credentials = f"{username}:{password}"
    encoded_token = base64.b64encode(credentials.encode("utf-8")).decode(
        "utf-8"
    )

    event = {
        "authorizationToken": encoded_token,
        "methodArn": "arn:aws:execute-api:us-east-1:123456789012:abcdef123/test/GET/users",
    }

    mock_cognito_client = MagicMock()
    mock_cognito_client.admin_initiate_auth.return_value = {
        "AuthenticationResult": {"AccessToken": "mock-access-token"}
    }

    mock_policy = {
        "principalId": username,
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": "Allow",
                    "Resource": event["methodArn"],
                }
            ],
        },
    }

    with (
        patch.object(
            handler_module,
            "get_cognito_client",
            return_value=mock_cognito_client,
        ),
        patch.object(
            handler_module,
            "generate_policy",
            return_value=mock_policy,
        ),
        patch.object(
            handler_module, "USER_POOL_ID", "test-pool-id"
        ),
        patch.object(
            handler_module,
            "USER_POOL_CLIENT_ID",
            "test-client-id",
        ),
    ):
        # Act
        result = handler_module.lambda_handler(event, lambda_context)

        # Assert
        assert result == mock_policy
        mock_cognito_client.admin_initiate_auth.assert_called_once_with(
            UserPoolId="test-pool-id",
            ClientId="test-client-id",
            AuthFlow="ADMIN_NO_SRP_AUTH",
            AuthParameters={"USERNAME": username, "PASSWORD": password},
        )
