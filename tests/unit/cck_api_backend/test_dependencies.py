"""Unit tests for the dependencies module."""

# Standard Library
import os
from unittest.mock import Mock, patch

# Third Party
import pytest
from fastapi import HTTPException, status, Request
from botocore.exceptions import ClientError

# Local Modules
from api_backend.dependencies.dependencies import (
    get_ssm_client,
    get_allowed_ip_from_ssm,
    verify_source_ip,
    HOME_IP_SSM_PARAMETER_NAME,
    CACHE_TTL_SECONDS,
)


class TestGetSsmClient:
    """Test cases for the get_ssm_client function."""

    def setup_method(self):
        """Reset the global ssm_client before each test."""
        # Reset the global ssm_client to None before each test
        # Local Modules
        import api_backend.dependencies.dependencies as deps_module

        deps_module.ssm_client = None

    @patch("api_backend.dependencies.dependencies.boto3.client")
    def test_get_ssm_client_success_first_call(self, mock_boto3_client):
        """Test successful SSM client creation on first call."""
        # Arrange
        mock_ssm_client = Mock()
        mock_boto3_client.return_value = mock_ssm_client

        # Act
        result = get_ssm_client()

        # Assert
        assert result == mock_ssm_client
        mock_boto3_client.assert_called_once_with("ssm")

    @patch("api_backend.dependencies.dependencies.boto3.client")
    def test_get_ssm_client_singleton_behavior(self, mock_boto3_client):
        """Test that subsequent calls return the same client instance."""
        # Arrange
        mock_ssm_client = Mock()
        mock_boto3_client.return_value = mock_ssm_client

        # Act
        result1 = get_ssm_client()
        result2 = get_ssm_client()

        # Assert
        assert result1 == result2 == mock_ssm_client
        mock_boto3_client.assert_called_once_with("ssm")

    @patch("api_backend.dependencies.dependencies.boto3.client")
    @patch("api_backend.dependencies.dependencies.logger")
    def test_get_ssm_client_exception_handling(
        self, mock_logger, mock_boto3_client
    ):
        """Test exception handling during SSM client initialization."""
        # Arrange
        test_exception = Exception("Failed to create SSM client")
        mock_boto3_client.side_effect = test_exception

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            get_ssm_client()

        assert exc_info.value == test_exception
        mock_logger.exception.assert_called_once_with(
            f"Failed to initialize Boto3 SSM client: {test_exception}"
        )


class TestGetAllowedIpFromSsm:
    """Test cases for the get_allowed_ip_from_ssm function."""

    def setup_method(self):
        """Reset the global ssm_client before each test."""
        # Local Modules
        import api_backend.dependencies.dependencies as deps_module

        deps_module.ssm_client = None

    @patch("api_backend.dependencies.dependencies.get_ssm_client")
    def test_get_allowed_ip_from_ssm_success(self, mock_get_ssm_client):
        """Test successful IP retrieval from SSM."""
        # Arrange
        mock_ssm_client = Mock()
        mock_get_ssm_client.return_value = mock_ssm_client
        mock_ssm_client.get_parameter.return_value = {
            "Parameter": {"Value": "192.168.1.100"}
        }

        # Act
        result = get_allowed_ip_from_ssm()

        # Assert
        assert result == "192.168.1.100"
        mock_ssm_client.get_parameter.assert_called_once_with(
            Name=HOME_IP_SSM_PARAMETER_NAME
        )

    @patch("api_backend.dependencies.dependencies.get_ssm_client")
    @patch("api_backend.dependencies.dependencies.logger")
    def test_get_allowed_ip_from_ssm_empty_value(
        self, mock_logger, mock_get_ssm_client
    ):
        """Test handling of empty SSM parameter value."""
        # Arrange
        mock_ssm_client = Mock()
        mock_get_ssm_client.return_value = mock_ssm_client
        mock_ssm_client.get_parameter.return_value = {
            "Parameter": {"Value": ""}
        }

        # Act
        result = get_allowed_ip_from_ssm()

        # Assert
        assert result is None
        mock_logger.error.assert_called_once_with(
            "SSM parameter value is empty or not found."
        )

    @patch("api_backend.dependencies.dependencies.get_ssm_client")
    @patch("api_backend.dependencies.dependencies.logger")
    def test_get_allowed_ip_from_ssm_no_parameter_key(
        self, mock_logger, mock_get_ssm_client
    ):
        """Test handling of missing Parameter key in SSM response."""
        # Arrange
        mock_ssm_client = Mock()
        mock_get_ssm_client.return_value = mock_ssm_client
        mock_ssm_client.get_parameter.return_value = {}

        # Act
        result = get_allowed_ip_from_ssm()

        # Assert
        assert result is None
        mock_logger.error.assert_called_once_with(
            "SSM parameter value is empty or not found."
        )

    @patch("api_backend.dependencies.dependencies.get_ssm_client")
    @patch("api_backend.dependencies.dependencies.logger")
    def test_get_allowed_ip_from_ssm_no_value_key(
        self, mock_logger, mock_get_ssm_client
    ):
        """Test handling of missing Value key in SSM parameter."""
        # Arrange
        mock_ssm_client = Mock()
        mock_get_ssm_client.return_value = mock_ssm_client
        mock_ssm_client.get_parameter.return_value = {"Parameter": {}}

        # Act
        result = get_allowed_ip_from_ssm()

        # Assert
        assert result is None
        mock_logger.error.assert_called_once_with(
            "SSM parameter value is empty or not found."
        )

    @patch("api_backend.dependencies.dependencies.get_ssm_client")
    @patch("api_backend.dependencies.dependencies.logger")
    def test_get_allowed_ip_from_ssm_client_error(
        self, mock_logger, mock_get_ssm_client
    ):
        """Test handling of ClientError from SSM."""
        # Arrange
        mock_ssm_client = Mock()
        mock_get_ssm_client.return_value = mock_ssm_client
        client_error = ClientError(
            error_response={"Error": {"Code": "ParameterNotFound"}},
            operation_name="GetParameter",
        )
        mock_ssm_client.get_parameter.side_effect = client_error

        # Act
        result = get_allowed_ip_from_ssm()  # Assert
        assert result is None
        mock_logger.exception.assert_called_once_with(
            f"Error fetching IP from SSM parameter '{HOME_IP_SSM_PARAMETER_NAME}': {client_error}"
        )

    @patch("api_backend.dependencies.dependencies.get_ssm_client")
    def test_get_allowed_ip_from_ssm_general_exception(
        self, mock_get_ssm_client
    ):
        """Test handling of general exception during IP retrieval."""
        # Arrange
        mock_ssm_client = Mock()
        mock_get_ssm_client.return_value = mock_ssm_client
        general_error = Exception("Network error")
        mock_ssm_client.get_parameter.side_effect = general_error

        # Act & Assert
        # General exceptions should propagate up, not be caught
        with pytest.raises(Exception) as exc_info:
            get_allowed_ip_from_ssm()

        assert exc_info.value == general_error


class TestVerifySourceIp:
    """Test cases for the verify_source_ip function."""

    def create_mock_request(
        self, client_host=None, aws_event=None, source_ip_from_event=None
    ):
        """Helper method to create mock Request objects."""
        mock_request = Mock(spec=Request)

        # Set up client attribute
        if client_host:
            mock_request.client = Mock()
            mock_request.client.host = client_host
        else:
            mock_request.client = None

        # Set up scope with aws.event
        scope = {}
        if aws_event or source_ip_from_event:
            if source_ip_from_event:
                scope["aws.event"] = {
                    "requestContext": {
                        "identity": {"sourceIp": source_ip_from_event}
                    }
                }
            else:
                scope["aws.event"] = aws_event

        mock_request.scope = scope
        return mock_request

    @patch("api_backend.dependencies.dependencies.get_allowed_ip_from_ssm")
    @patch("api_backend.dependencies.dependencies.logger")
    def test_verify_source_ip_success_api_gateway(
        self, mock_logger, mock_get_allowed_ip
    ):
        """Test successful IP verification with API Gateway source IP."""
        # Arrange
        test_ip = "192.168.1.100"
        mock_get_allowed_ip.return_value = test_ip
        mock_request = self.create_mock_request(source_ip_from_event=test_ip)

        # Act
        verify_source_ip(mock_request)

        # Assert
        mock_logger.append_keys.assert_called_once_with(source_ip=test_ip)
        mock_logger.info.assert_any_call("Executing IP whitelist check.")
        mock_logger.info.assert_any_call(
            f"IP address {test_ip} successfully verified against whitelist."
        )

    @patch("api_backend.dependencies.dependencies.get_allowed_ip_from_ssm")
    @patch("api_backend.dependencies.dependencies.logger")
    def test_verify_source_ip_success_local_client(
        self, mock_logger, mock_get_allowed_ip
    ):
        """Test successful IP verification with local client IP."""
        # Arrange
        test_ip = "127.0.0.1"
        mock_get_allowed_ip.return_value = test_ip
        mock_request = self.create_mock_request(client_host=test_ip)

        # Act
        verify_source_ip(mock_request)

        # Assert
        mock_logger.append_keys.assert_called_once_with(source_ip=test_ip)
        mock_logger.info.assert_any_call("Executing IP whitelist check.")
        mock_logger.info.assert_any_call(
            f"IP address {test_ip} successfully verified against whitelist."
        )

    @patch("api_backend.dependencies.dependencies.logger")
    def test_verify_source_ip_no_source_ip(self, mock_logger):
        """Test error when source IP cannot be determined."""
        # Arrange
        mock_request = self.create_mock_request()

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            verify_source_ip(mock_request)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert (
            exc_info.value.detail == "Could not determine client IP address."
        )
        mock_logger.warning.assert_called_once_with(
            "Source IP could not be determined from the request."
        )

    @patch("api_backend.dependencies.dependencies.get_allowed_ip_from_ssm")
    @patch("api_backend.dependencies.dependencies.logger")
    def test_verify_source_ip_no_allowed_ip(
        self, mock_logger, mock_get_allowed_ip
    ):
        """Test error when allowed IP cannot be fetched from SSM."""
        # Arrange
        test_ip = "192.168.1.100"
        mock_get_allowed_ip.return_value = None
        mock_request = self.create_mock_request(client_host=test_ip)

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            verify_source_ip(mock_request)

        assert (
            exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        )
        assert exc_info.value.detail == (
            "Service is temporarily unavailable due to a configuration issue."
        )
        mock_logger.error.assert_called_once_with(
            "Whitelist IP could not be loaded from configuration. Denying access by default."
        )

    @patch("api_backend.dependencies.dependencies.get_allowed_ip_from_ssm")
    @patch("api_backend.dependencies.dependencies.logger")
    def test_verify_source_ip_ip_mismatch(
        self, mock_logger, mock_get_allowed_ip
    ):
        """Test error when source IP doesn't match allowed IP."""
        # Arrange
        source_ip = "192.168.1.100"
        allowed_ip = "192.168.1.200"
        mock_get_allowed_ip.return_value = allowed_ip
        mock_request = self.create_mock_request(client_host=source_ip)

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            verify_source_ip(mock_request)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert (
            exc_info.value.detail
            == "Access from your IP address is not permitted."
        )
        mock_logger.warning.assert_called_once_with(
            f"Forbidden access for IP: {source_ip}. Whitelisted IP is {allowed_ip}."
        )

    @patch("api_backend.dependencies.dependencies.get_allowed_ip_from_ssm")
    @patch("api_backend.dependencies.dependencies.logger")
    def test_verify_source_ip_api_gateway_priority(
        self, mock_logger, mock_get_allowed_ip
    ):
        """Test that API Gateway source IP takes priority over client IP."""
        # Arrange
        api_gateway_ip = "192.168.1.100"
        client_ip = "127.0.0.1"
        mock_get_allowed_ip.return_value = api_gateway_ip

        # Create request with both API Gateway event and client
        mock_request = Mock(spec=Request)
        mock_request.client = Mock()
        mock_request.client.host = client_ip
        mock_request.scope = {
            "aws.event": {
                "requestContext": {"identity": {"sourceIp": api_gateway_ip}}
            }
        }

        # Act
        verify_source_ip(mock_request)

        # Assert - Should use API Gateway IP, not client IP
        mock_logger.append_keys.assert_called_once_with(
            source_ip=api_gateway_ip
        )
        mock_logger.info.assert_any_call(
            f"IP address {api_gateway_ip} successfully verified against whitelist."
        )

    @patch("api_backend.dependencies.dependencies.get_allowed_ip_from_ssm")
    @patch("api_backend.dependencies.dependencies.logger")
    def test_verify_source_ip_empty_aws_event(
        self, mock_logger, mock_get_allowed_ip
    ):
        """Test handling of empty AWS event in request scope."""
        # Arrange
        test_ip = "127.0.0.1"
        mock_get_allowed_ip.return_value = test_ip
        mock_request = Mock(spec=Request)
        mock_request.client = Mock()
        mock_request.client.host = test_ip
        mock_request.scope = {"aws.event": {}}  # Empty AWS event

        # Act
        verify_source_ip(mock_request)

        # Assert - Should fall back to client IP
        mock_logger.append_keys.assert_called_once_with(source_ip=test_ip)
        mock_logger.info.assert_any_call(
            f"IP address {test_ip} successfully verified against whitelist."
        )

    @patch("api_backend.dependencies.dependencies.get_allowed_ip_from_ssm")
    @patch("api_backend.dependencies.dependencies.logger")
    def test_verify_source_ip_missing_request_context(
        self, mock_logger, mock_get_allowed_ip
    ):
        """Test handling of missing requestContext in AWS event."""
        # Arrange
        test_ip = "127.0.0.1"
        mock_get_allowed_ip.return_value = test_ip
        mock_request = Mock(spec=Request)
        mock_request.client = Mock()
        mock_request.client.host = test_ip
        mock_request.scope = {"aws.event": {"otherKey": "otherValue"}}

        # Act
        verify_source_ip(mock_request)

        # Assert - Should fall back to client IP
        mock_logger.append_keys.assert_called_once_with(source_ip=test_ip)


class TestModuleGlobals:
    """Test cases for module-level globals and constants."""

    def test_cache_ttl_seconds_constant(self):
        """Test that CACHE_TTL_SECONDS is set correctly."""
        assert CACHE_TTL_SECONDS == 60

    def test_home_ip_ssm_parameter_name_from_env(self):
        """Test that HOME_IP_SSM_PARAMETER_NAME is read from environment."""
        # This tests the module-level variable assignment
        # The actual value depends on the environment
        assert HOME_IP_SSM_PARAMETER_NAME == os.environ.get(
            "HOME_IP_SSM_PARAMETER_NAME"
        )


class TestEnvironmentVariables:
    """Test cases for environment variable handling."""

    @patch.dict(os.environ, {"HOME_IP_SSM_PARAMETER_NAME": "/test/ip"})
    def test_home_ip_ssm_parameter_name_custom_value(self):
        """Test HOME_IP_SSM_PARAMETER_NAME with custom environment value."""
        # We need to reload the module to pick up the new environment variable
        # Standard Library
        import importlib

        # Local Modules
        import api_backend.dependencies.dependencies as deps_module

        importlib.reload(deps_module)

        assert deps_module.HOME_IP_SSM_PARAMETER_NAME == "/test/ip"

    @patch.dict(os.environ, {}, clear=True)
    def test_home_ip_ssm_parameter_name_no_env_var(self):
        """Test HOME_IP_SSM_PARAMETER_NAME when environment variable not set."""
        # We need to reload the module to pick up the cleared environment
        # Standard Library
        import importlib

        # Local Modules
        import api_backend.dependencies.dependencies as deps_module

        importlib.reload(deps_module)

        assert deps_module.HOME_IP_SSM_PARAMETER_NAME is None


class TestEdgeCases:
    """Test cases for edge cases and boundary conditions."""

    @patch("api_backend.dependencies.dependencies.get_allowed_ip_from_ssm")
    @patch("api_backend.dependencies.dependencies.logger")
    def test_verify_source_ip_empty_string_allowed_ip(
        self, mock_logger, mock_get_allowed_ip
    ):
        """Test handling when allowed IP is an empty string."""
        # Arrange
        test_ip = "192.168.1.100"
        mock_get_allowed_ip.return_value = ""  # Empty string
        mock_request = self.create_mock_request(client_host=test_ip)

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            verify_source_ip(mock_request)

        assert (
            exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        )

    def create_mock_request(self, client_host=None):
        """Helper method to create mock Request objects."""
        mock_request = Mock(spec=Request)

        if client_host:
            mock_request.client = Mock()
            mock_request.client.host = client_host
        else:
            mock_request.client = None

        mock_request.scope = {}
        return mock_request

    @patch("api_backend.dependencies.dependencies.get_allowed_ip_from_ssm")
    @patch("api_backend.dependencies.dependencies.logger")
    def test_verify_source_ip_whitespace_only_ips(
        self, mock_logger, mock_get_allowed_ip
    ):
        """Test handling of whitespace-only IP addresses."""
        # Arrange
        source_ip = "   "  # Whitespace only
        allowed_ip = "192.168.1.100"
        mock_get_allowed_ip.return_value = allowed_ip
        mock_request = Mock(spec=Request)
        mock_request.client = Mock()
        mock_request.client.host = source_ip
        mock_request.scope = {}

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            verify_source_ip(mock_request)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert (
            exc_info.value.detail
            == "Access from your IP address is not permitted."
        )
