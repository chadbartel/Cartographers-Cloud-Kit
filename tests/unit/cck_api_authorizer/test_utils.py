# Standard Library
import os
from unittest.mock import patch

# Third Party
import pytest
from moto import mock_aws

# Local Modules
# Local imports
from api_authorizer.utils import (
    get_cognito_client,
    generate_policy,
    USER_POOL_ID,
    USER_POOL_CLIENT_ID,
)


def test_environment_variables():
    """Test that environment variables are properly loaded."""
    # Arrange & Act & Assert
    assert USER_POOL_ID == os.environ.get("USER_POOL_ID")
    assert USER_POOL_CLIENT_ID == os.environ.get("USER_POOL_CLIENT_ID")


@mock_aws
def test_get_cognito_client_creates_new_client():
    """Test that get_cognito_client creates a new client when none exists."""
    # Arrange
    # Local Modules
    import api_authorizer.utils as utils_module

    utils_module.cognito_client = None

    # Act
    client = get_cognito_client()

    # Assert
    assert client is not None
    assert hasattr(client, "meta")
    assert client.meta.service_model.service_name == "cognito-idp"


@mock_aws
def test_get_cognito_client_reuses_existing_client():
    """Test that get_cognito_client reuses an existing client."""
    # Arrange
    # Local Modules
    import api_authorizer.utils as utils_module

    utils_module.cognito_client = None

    # Act
    client1 = get_cognito_client()
    client2 = get_cognito_client()

    # Assert
    assert client1 is client2


@patch("api_authorizer.utils.boto3.client")
def test_get_cognito_client_handles_exception(mock_boto3_client):
    """Test that get_cognito_client properly handles and re-raises exceptions."""
    # Arrange
    # Local Modules
    import api_authorizer.utils as utils_module

    utils_module.cognito_client = None

    test_exception = Exception("Test exception")
    mock_boto3_client.side_effect = test_exception

    # Act & Assert
    with pytest.raises(Exception) as exc_info:
        get_cognito_client()

    assert exc_info.value is test_exception
    mock_boto3_client.assert_called_once_with("cognito-idp")


def test_generate_policy_basic():
    """Test generate_policy with basic parameters."""
    # Arrange
    principal_id = "test-user-123"
    effect = "Allow"
    resource = "arn:aws:execute-api:us-east-1:123456789012:abcdef123/*"

    # Act
    policy = generate_policy(principal_id, effect, resource)

    # Assert
    expected_policy = {
        "principalId": principal_id,
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": effect,
                    "Resource": resource,
                }
            ],
        },
    }

    assert policy == expected_policy
    assert "context" not in policy


def test_generate_policy_with_context():
    """Test generate_policy with context parameter."""
    # Arrange
    principal_id = "test-user-456"
    effect = "Deny"
    resource = "arn:aws:execute-api:us-west-2:987654321098:xyz789/*"
    context = {
        "userId": "12345",
        "role": "admin",
        "permissions": ["read", "write"],
    }

    # Act
    policy = generate_policy(principal_id, effect, resource, context)

    # Assert
    expected_policy = {
        "principalId": principal_id,
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": effect,
                    "Resource": resource,
                }
            ],
        },
        "context": context,
    }

    assert policy == expected_policy


def test_generate_policy_with_none_context():
    """Test generate_policy with explicitly None context."""
    # Arrange
    principal_id = "test-user-789"
    effect = "Allow"
    resource = "arn:aws:execute-api:eu-west-1:111222333444:api123/*"

    # Act
    policy = generate_policy(principal_id, effect, resource, None)

    # Assert
    expected_policy = {
        "principalId": principal_id,
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": effect,
                    "Resource": resource,
                }
            ],
        },
    }

    assert policy == expected_policy
    assert "context" not in policy


def test_generate_policy_with_empty_context():
    """Test generate_policy with empty dict context."""
    # Arrange
    principal_id = "test-user-000"
    effect = "Allow"
    resource = "arn:aws:execute-api:ap-south-1:555666777888:def456/*"
    context = {}

    # Act
    policy = generate_policy(principal_id, effect, resource, context)

    # Assert
    assert "context" in policy
    assert policy["context"] == {}


@pytest.fixture(autouse=True)
def reset_cognito_client():
    """Reset the global cognito_client before each test."""
    # Local Modules
    import api_authorizer.utils as utils_module

    utils_module.cognito_client = None
    yield
    utils_module.cognito_client = None
