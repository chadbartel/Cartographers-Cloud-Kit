# Standard Library
import os
from typing import Dict, Any

# Third Party
from fastapi import FastAPI, Depends
from fastapi.openapi.utils import get_openapi
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import HTMLResponse
from mangum import Mangum
from aws_lambda_powertools import Logger
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext

# Local Modules
from api_backend import router
from api_backend.dependencies import verify_source_ip

# Initialize a logger
logger = Logger()

# Get the API prefix from environment variables or default to 'api/v1'
api_prefix = os.getenv("API_PREFIX", "/api/v1")

# Create a FastAPI application instance
app = FastAPI(
    title="Cartographers Cloud Kit API",
    version="0.1.0",
    description="A serverless asset manager for TTRPGs.",
    docs_url=f"{api_prefix}/docs",
    redoc_url=f"{api_prefix}/redoc",
    openapi_url=f"{api_prefix}/openapi.json",
)


# region Define custom documentation routes
@app.get(
    f"{api_prefix}/openapi.json",
    include_in_schema=False,
    dependencies=[Depends(verify_source_ip)],
)
async def custom_openapi_endpoint() -> Dict[str, Any]:
    """Custom OpenAPI endpoint to return the OpenAPI schema.

    Returns
    -------
    Dict[str, Any]
        The OpenAPI schema for the FastAPI application.
    """
    return get_openapi(title=app.title, version=app.version, routes=app.routes)


@app.get(
    f"{api_prefix}/docs",
    include_in_schema=False,
    dependencies=[Depends(verify_source_ip)],
)
async def custom_swagger_ui_html() -> HTMLResponse:
    """Custom Swagger UI HTML endpoint.

    Returns
    -------
    HTMLResponse
        The HTML response for the Swagger UI documentation.
    """
    return get_swagger_ui_html(
        openapi_url=f"{api_prefix}/openapi.json",
        title=app.title + " - Swagger UI",
    )


@app.get(
    f"{api_prefix}/redoc",
    include_in_schema=False,
    dependencies=[Depends(verify_source_ip)],
)
async def custom_redoc_html() -> HTMLResponse:
    """Custom ReDoc HTML endpoint.

    Returns
    -------
    HTMLResponse
        The HTML response for the ReDoc documentation.
    """
    return get_redoc_html(
        openapi_url=f"{api_prefix}/openapi.json", title=app.title + " - ReDoc"
    )


# endregion

# Add the API router to the FastAPI app
app.include_router(router, prefix=api_prefix)

# Initialize Mangum handler globally
# This instance will be reused across invocations in a warm Lambda environment.
lambda_asgi_handler = Mangum(app, lifespan="off")


@logger.inject_lambda_context(
    log_event=True, correlation_id_path=correlation_paths.API_GATEWAY_HTTP
)
def lambda_handler(
    event: Dict[str, Any], context: LambdaContext
) -> Dict[str, Any]:
    """Lambda handler function to adapt the FastAPI app for AWS Lambda.

    Parameters
    ----------
    event : Dict[str, Any]
        The event data passed to the Lambda function.
    context : LambdaContext
        The context object containing runtime information.

    Returns
    -------
    Dict[str, Any]
        The response from the FastAPI application.
    """
    # Return the response from the FastAPI application
    return lambda_asgi_handler(event, context)
