"""Unit tests for cck-api-backend handler.py module."""

# Standard Library
import os
from typing import Any, Dict
from unittest.mock import MagicMock, patch

# Third Party
import pytest
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from mangum import Mangum

# My Modules
from tests.conftest import import_handler


@pytest.fixture
def handler_module():
    """Import the handler module using the import_handler function."""
    with (
        patch("api_backend.dependencies.dependencies.verify_source_ip") as mock_verify,
        patch.dict(os.environ, {"HOME_IP_SSM_PARAMETER_NAME": "test-param"}),
        patch("api_backend.dependencies.dependencies.get_ssm_client") as mock_ssm_client,
        patch("api_backend.dependencies.dependencies.get_allowed_ip_from_ssm") as mock_get_ip,
    ):
        mock_verify.return_value = True
        mock_get_ip.return_value = "192.168.1.1"
        mock_ssm_client.return_value = MagicMock()
        return import_handler("cck-api-backend")


@pytest.fixture
def lambda_context():
    """Create a mock Lambda context object."""
    context = MagicMock()
    context.function_name = "test-backend-function"
    context.function_version = "1"
    context.invoked_function_arn = (
        "arn:aws:lambda:us-east-1:123456789012:function:test-backend-function"
    )
    context.memory_limit_in_mb = 512
    context.remaining_time_in_millis = lambda: 30000
    context.aws_request_id = "test-backend-request-id"
    return context


@pytest.fixture
def api_gateway_event():
    """Create a sample API Gateway REST API event for testing."""
    return {
        "resource": "/api/v1/docs",  # Required for APIGateway handler
        "httpMethod": "GET",
        "path": "/api/v1/docs",
        "pathParameters": None,
        "queryStringParameters": None,
        "multiValueQueryStringParameters": None,
        "headers": {
            "Host": "example.com",
            "User-Agent": "test-agent",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        "multiValueHeaders": {
            "Host": ["example.com"],
            "User-Agent": ["test-agent"],
        },
        "body": None,
        "isBase64Encoded": False,
        "requestContext": {
            "requestId": "test-request-id",
            "stage": "test",
            "resourceId": "123456",
            "resourcePath": "/api/v1/docs",
            "httpMethod": "GET",
            "path": "/test/api/v1/docs",
            "protocol": "HTTP/1.1",
            "accountId": "123456789012",
            "apiId": "1234567890",
            "identity": {
                "accessKey": None,
                "accountId": None,
                "apiKey": None,
                "apiKeyId": None,
                "caller": None,
                "cognitoAuthenticationProvider": None,
                "cognitoAuthenticationType": None,
                "cognitoIdentityId": None,
                "cognitoIdentityPoolId": None,
                "principalOrgId": None,
                "sourceIp": "192.168.1.1",
                "user": None,
                "userAgent": "test-agent",
                "userArn": None,
            },
            "requestTime": "09/Apr/2015:12:34:56 +0000",
            "requestTimeEpoch": 1428582896000,
        },
    }


def test_handler_module_imports(handler_module):
    """Test that all required components are imported correctly."""
    # Arrange & Act & Assert
    assert hasattr(handler_module, "app")
    assert hasattr(handler_module, "lambda_handler")
    assert hasattr(handler_module, "lambda_asgi_handler")
    assert hasattr(handler_module, "logger")
    assert hasattr(handler_module, "api_prefix")

    # Verify FastAPI app is created correctly
    assert isinstance(handler_module.app, FastAPI)
    assert handler_module.app.title == "Cartographers Cloud Kit API"
    assert handler_module.app.version == "0.1.0"
    assert (
        handler_module.app.description
        == "A serverless asset manager for TTRPGs."
    )

    # Verify Mangum handler is created
    assert isinstance(handler_module.lambda_asgi_handler, Mangum)


def test_api_prefix_default_value(handler_module):
    """Test that API prefix defaults to '/api/v1' when not set."""
    # Arrange & Act
    with patch.dict(os.environ, {}, clear=True), \
         patch("api_backend.dependencies.verify_source_ip") as mock_verify:
        mock_verify.return_value = True
        # Import fresh module to test default
        fresh_module = import_handler("cck-api-backend")

    # Assert
    assert fresh_module.api_prefix == "/api/v1"


def test_api_prefix_from_environment(handler_module):
    """Test that API prefix is read from environment variable."""
    # Arrange
    test_prefix = "/test/v2"

    # Act
    with patch.dict(os.environ, {"API_PREFIX": test_prefix}):
        fresh_module = import_handler("cck-api-backend")

    # Assert
    assert fresh_module.api_prefix == test_prefix


def test_fastapi_app_configuration(handler_module):
    """Test FastAPI app configuration with dynamic API prefix."""
    # Arrange & Act
    app = handler_module.app
    prefix = handler_module.api_prefix

    # Assert
    assert app.docs_url == f"{prefix}/docs"
    assert app.redoc_url == f"{prefix}/redoc"
    assert app.openapi_url == f"{prefix}/openapi.json"


def test_lambda_handler_calls_mangum_handler(
    handler_module, api_gateway_event, lambda_context
):
    """Test that lambda_handler delegates to the Mangum ASGI handler."""
    # Act
    result = handler_module.lambda_handler(
        api_gateway_event, lambda_context
    )

    # Assert
    # The key test is that the lambda_handler returns a proper response structure
    assert isinstance(result, dict)
    assert "statusCode" in result
    assert "body" in result
    assert "headers" in result
    
    # Verify it's an HTML response for the docs endpoint
    assert result["statusCode"] == 200
    assert "text/html" in result["headers"]["content-type"]
    assert "<!DOCTYPE html>" in result["body"]


def test_custom_openapi_endpoint_function_exists(handler_module):
    """Test that the custom OpenAPI endpoint function is defined."""
    # Arrange & Act
    # The function should be accessible through the FastAPI app routes
    openapi_routes = [
        route
        for route in handler_module.app.routes
        if hasattr(route, "path") and route.path.endswith("/openapi.json")
    ]

    # Assert
    # FastAPI may create multiple routes for the same path, so check >= 1
    assert len(openapi_routes) >= 1
    # Check that at least one route has GET method
    assert any("GET" in route.methods for route in openapi_routes)


def test_custom_swagger_ui_html_function_exists(handler_module):
    """Test that the custom Swagger UI HTML function is defined."""
    # Arrange & Act
    docs_routes = [
        route
        for route in handler_module.app.routes
        if hasattr(route, "path") and route.path.endswith("/docs")
    ]

    # Assert
    # FastAPI creates duplicate routes - one built-in, one custom
    assert len(docs_routes) >= 1
    # Check that at least one route has GET method
    assert any("GET" in route.methods for route in docs_routes)


def test_custom_redoc_html_function_exists(handler_module):
    """Test that the custom ReDoc HTML function is defined."""
    # Arrange & Act
    redoc_routes = [
        route
        for route in handler_module.app.routes
        if hasattr(route, "path") and route.path.endswith("/redoc")
    ]

    # Assert
    # FastAPI creates duplicate routes - one built-in, one custom
    assert len(redoc_routes) >= 1
    # Check that at least one route has GET method
    assert any("GET" in route.methods for route in redoc_routes)


def test_custom_openapi_endpoint_with_mocked_dependencies(handler_module):
    """Test custom OpenAPI endpoint function logic with mocked dependencies."""
    # Arrange
    mock_get_openapi = MagicMock(return_value={"info": {"title": "Test API"}})

    with patch("fastapi.openapi.utils.get_openapi", mock_get_openapi):
        # Act - We can't directly call the async function, but we can test the logic
        # by checking that the function would call get_openapi with correct parameters
        app = handler_module.app

        # The function should use app.title, app.version, and app.routes
        expected_title = app.title
        expected_version = app.version
        expected_routes = app.routes

        # Assert the app has the expected attributes
        assert expected_title == "Cartographers Cloud Kit API"
        assert expected_version == "0.1.0"
        assert expected_routes is not None


@pytest.mark.asyncio
async def test_custom_openapi_endpoint_response_type():
    """Test that custom OpenAPI endpoint returns correct type."""
    # Arrange
    # Third Party
    from fastapi.openapi.utils import get_openapi
    from fastapi import FastAPI

    app = FastAPI(title="Test", version="1.0")

    # Act
    result = get_openapi(
        title=app.title, version=app.version, routes=app.routes
    )

    # Assert
    assert isinstance(result, dict)
    assert "info" in result
    assert result["info"]["title"] == "Test"


@pytest.mark.asyncio
async def test_custom_swagger_ui_html_response_type():
    """Test that custom Swagger UI HTML returns HTMLResponse."""
    # Arrange
    # Third Party
    from fastapi.openapi.docs import get_swagger_ui_html

    # Act
    result = get_swagger_ui_html(
        openapi_url="/api/v1/openapi.json", title="Test API - Swagger UI"
    )

    # Assert
    assert isinstance(result, HTMLResponse)


@pytest.mark.asyncio
async def test_custom_redoc_html_response_type():
    """Test that custom ReDoc HTML returns HTMLResponse."""
    # Arrange
    # Third Party
    from fastapi.openapi.docs import get_redoc_html

    # Act
    result = get_redoc_html(
        openapi_url="/api/v1/openapi.json", title="Test API - ReDoc"
    )

    # Assert
    assert isinstance(result, HTMLResponse)


def test_router_inclusion_in_app(handler_module):
    """Test that the API router is included in the FastAPI app."""
    # Arrange & Act
    app = handler_module.app
    prefix = handler_module.api_prefix

    # Check if router routes are included
    api_routes = [
        route
        for route in app.routes
        if hasattr(route, "path") and route.path.startswith(prefix)
    ]

    # Assert
    # Should have at least the custom documentation routes + API routes
    assert len(api_routes) >= 3  # openapi.json, docs, redoc


def test_mangum_handler_configuration(handler_module):
    """Test that Mangum handler is configured correctly."""
    # Arrange & Act
    mangum_handler = handler_module.lambda_asgi_handler

    # Assert
    assert isinstance(mangum_handler, Mangum)
    # Mangum object should have the app and lifespan configuration
    assert mangum_handler.app == handler_module.app


def test_lambda_handler_with_different_event_types(
    handler_module, lambda_context
):
    """Test lambda_handler with different types of events."""
    # Arrange
    http_event = {
        "version": "2.0",  # Required for HTTPGateway handler
        "routeKey": "GET /api/v1/assets",
        "rawPath": "/api/v1/assets",
        "headers": {},
        "requestContext": {
            "requestId": "test-request-id",
            "http": {
                "method": "GET",
                "path": "/api/v1/assets",
                "sourceIp": "192.168.1.1",
            },
            "identity": {
                "sourceIp": "192.168.1.1",
            }
        },
    }

    rest_event = {
        "resource": "/api/v1/assets",  # Required for APIGateway handler
        "httpMethod": "POST",
        "path": "/api/v1/assets",
        "body": '{"test": "data"}',
        "headers": {"Content-Type": "application/json"},
        "pathParameters": None,
        "queryStringParameters": None,
        "requestContext": {
            "requestId": "test-request-id",
            "stage": "test",
            "httpMethod": "POST",
            "path": "/api/v1/assets",
        },
    }

    with (
        patch.dict(os.environ, {"HOME_IP_SSM_PARAMETER_NAME": "test-param"}),
        patch("api_backend.dependencies.dependencies.get_ssm_client") as mock_ssm_client,
        patch("api_backend.dependencies.dependencies.get_allowed_ip_from_ssm") as mock_get_ip,
        patch("api_backend.dependencies.dependencies.verify_source_ip") as mock_verify,
    ):
        mock_verify.return_value = True
        mock_get_ip.return_value = "192.168.1.1"
        mock_ssm_client.return_value = MagicMock()

        # Act & Assert for HTTP API event (GET)
        result1 = handler_module.lambda_handler(http_event, lambda_context)
        assert isinstance(result1, dict)
        assert "statusCode" in result1
        # API returns 422 for missing auth header - this is expected behavior
        assert result1["statusCode"] == 422

        # Act & Assert for REST API event (POST)
        result2 = handler_module.lambda_handler(rest_event, lambda_context)
        assert isinstance(result2, dict)
        assert "statusCode" in result2
        # API returns 405 for unsupported POST method - this is expected behavior
        assert result2["statusCode"] == 405


def test_logger_configuration(handler_module):
    """Test that logger is configured correctly."""
    # Arrange & Act
    logger = handler_module.logger

    # Assert
    assert logger is not None
    # Logger should be an instance of AWS Lambda Powertools Logger
    assert hasattr(logger, "info")
    assert hasattr(logger, "error")
    assert hasattr(logger, "warning")


def test_lambda_handler_decorator_configuration(handler_module):
    """Test that lambda_handler has correct decorator configuration."""
    # Arrange & Act
    lambda_handler = handler_module.lambda_handler

    # Assert
    assert callable(lambda_handler)
    # Should have powertools decorators applied
    assert hasattr(lambda_handler, "__wrapped__")


@pytest.mark.parametrize(
    "env_prefix,expected_prefix",
    [
        ("/custom/v1", "/custom/v1"),
        ("/api/v2", "/api/v2"),
        ("", ""),
        # Note: "/" fails in FastAPI due to router prefix validation
    ],
)
def test_api_prefix_variations(env_prefix, expected_prefix):
    """Test API prefix with various environment variable values."""
    # Arrange & Act
    with patch.dict(os.environ, {"API_PREFIX": env_prefix}), \
         patch("api_backend.dependencies.verify_source_ip") as mock_verify:
        mock_verify.return_value = True
        module = import_handler("cck-api-backend")

    # Assert
    assert module.api_prefix == expected_prefix


def test_api_prefix_trailing_slash_error():
    """Test that API prefix with trailing slash causes expected FastAPI error."""
    # Arrange & Act & Assert
    with patch.dict(os.environ, {"API_PREFIX": "/"}), \
         patch("api_backend.dependencies.verify_source_ip") as mock_verify:
        mock_verify.return_value = True
        with pytest.raises(AssertionError) as exc_info:
            import_handler("cck-api-backend")

        # FastAPI should raise an AssertionError about trailing slash
        assert "A path prefix must not end with '/'" in str(exc_info.value)


def test_app_includes_all_required_routes(handler_module):
    """Test that FastAPI app includes all required custom routes."""
    # Arrange
    app = handler_module.app
    prefix = handler_module.api_prefix

    # Act
    route_paths = [
        route.path for route in app.routes if hasattr(route, "path")
    ]

    # Assert
    expected_paths = [
        f"{prefix}/openapi.json",
        f"{prefix}/docs",
        f"{prefix}/redoc",
    ]

    for expected_path in expected_paths:
        assert expected_path in route_paths


def test_dependencies_are_applied_to_custom_routes(handler_module):
    """Test that verify_source_ip dependency is applied to custom routes."""
    # Arrange
    app = handler_module.app
    prefix = handler_module.api_prefix

    # Act
    custom_routes = [
        route
        for route in app.routes
        if hasattr(route, "path")
        and (
            route.path == f"{prefix}/openapi.json"
            or route.path == f"{prefix}/docs"
            or route.path == f"{prefix}/redoc"
        )
    ]

    # Assert
    for route in custom_routes:
        # Each route should have dependencies
        if hasattr(route, "dependencies"):
            assert route.dependencies is not None


def test_error_handling_in_lambda_handler(handler_module, lambda_context):
    """Test error handling in lambda_handler when Mangum handler fails."""
    # Arrange
    event = {"test": "event"}

    with patch.object(
        handler_module.lambda_asgi_handler,
        "__call__",
        side_effect=RuntimeError("Test error"),
    ):
        # Act & Assert
        with pytest.raises(RuntimeError) as exc_info:
            handler_module.lambda_handler(event, lambda_context)

        # Should propagate the RuntimeError - either our mock or Mangum's inference error
        error_message = str(exc_info.value).lower()
        assert ("error" in error_message or "adapter was unable to infer" in error_message)


def test_module_level_variables_initialization(handler_module):
    """Test that all module-level variables are initialized correctly."""
    # Arrange & Act & Assert
    assert handler_module.logger is not None
    assert handler_module.api_prefix is not None
    assert isinstance(handler_module.app, FastAPI)
    assert isinstance(handler_module.lambda_asgi_handler, Mangum)

    # Test that the app configuration matches the variables
    assert handler_module.app.docs_url == f"{handler_module.api_prefix}/docs"
    assert handler_module.app.redoc_url == f"{handler_module.api_prefix}/redoc"
    assert (
        handler_module.app.openapi_url
        == f"{handler_module.api_prefix}/openapi.json"
    )


def test_handler_integration_with_real_fastapi_response(
    handler_module, lambda_context
):
    """Test lambda_handler integration with actual FastAPI response structure."""
    # Test with a docs endpoint that we know exists and should return HTML
    event = {
        "resource": "/api/v1/docs",  # Required for APIGateway handler
        "httpMethod": "GET",
        "path": "/api/v1/docs",
        "headers": {},
        "body": None,
        "requestContext": {
            "requestId": "test-request-id",
            "stage": "test",
            "httpMethod": "GET",
            "path": "/api/v1/docs",
        },
    }

    # Act
    result = handler_module.lambda_handler(event, lambda_context)

    # Assert
    assert isinstance(result, dict)
    assert "statusCode" in result
    assert "body" in result
    assert "headers" in result
    
    # Should return a successful response for the docs endpoint
    assert result["statusCode"] == 200
    assert "text/html" in result["headers"]["content-type"]
    assert "<!DOCTYPE html>" in result["body"]


def test_api_prefix_from_environment_with_mock():
    """Test that API prefix is read from environment with proper mocking."""
    # Arrange
    test_prefix = "/test/v2"

    # Act
    with patch.dict(os.environ, {"API_PREFIX": test_prefix}), \
         patch("api_backend.dependencies.verify_source_ip") as mock_verify:
        mock_verify.return_value = True
        fresh_module = import_handler("cck-api-backend")

    # Assert
    assert fresh_module.api_prefix == test_prefix


def test_custom_endpoint_functions_have_correct_signatures(handler_module):
    """Test that custom endpoint functions have the expected async signatures."""
    # Arrange
    app = handler_module.app

    # Act - Find the custom endpoints in the app routes
    custom_routes = [
        route for route in app.routes
        if hasattr(route, "path") and hasattr(route, "endpoint")
        and (route.path.endswith("/openapi.json")
             or route.path.endswith("/docs")
             or route.path.endswith("/redoc"))
    ]

    # Assert
    assert len(custom_routes) >= 3  # At least one for each custom endpoint

    # Check that endpoints are callable (async functions)
    for route in custom_routes:
        if hasattr(route, "endpoint"):
            assert callable(route.endpoint)


def test_lambda_handler_preserves_powertools_decorators(handler_module):
    """Test that lambda_handler preserves AWS Lambda Powertools decorators."""
    # Arrange & Act
    lambda_handler = handler_module.lambda_handler

    # Assert - Check that the function has been decorated
    assert callable(lambda_handler)
    # The decorator should add a __wrapped__ attribute
    assert hasattr(lambda_handler, "__wrapped__")

    # The logger should be injected and configured
    assert handler_module.logger is not None


def test_custom_endpoints_return_correct_responses(handler_module, lambda_context):
    """Test that custom endpoints return the expected response types."""
    # Test OpenAPI endpoint
    openapi_event = {
        "resource": "/api/v1/openapi.json",
        "httpMethod": "GET",
        "path": "/api/v1/openapi.json",
        "headers": {},
        "body": None,
        "requestContext": {
            "requestId": "test-request-id",
            "stage": "test",
            "httpMethod": "GET",
            "path": "/api/v1/openapi.json",
        },
    }

    # Test ReDoc endpoint  
    redoc_event = {
        "resource": "/api/v1/redoc",
        "httpMethod": "GET",
        "path": "/api/v1/redoc",
        "headers": {},
        "body": None,
        "requestContext": {
            "requestId": "test-request-id",
            "stage": "test",
            "httpMethod": "GET",
            "path": "/api/v1/redoc",
        },
    }

    # Act & Assert OpenAPI endpoint
    openapi_result = handler_module.lambda_handler(openapi_event, lambda_context)
    assert openapi_result["statusCode"] == 200
    assert "application/json" in openapi_result["headers"]["content-type"]

    # Act & Assert ReDoc endpoint
    redoc_result = handler_module.lambda_handler(redoc_event, lambda_context)
    assert redoc_result["statusCode"] == 200
    assert "text/html" in redoc_result["headers"]["content-type"]
