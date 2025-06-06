"""This module initializes the models for the API backend.

It imports the necessary models for asset management, including creation,
updating, metadata responses, presigned URL responses, and paginated asset
responses.
"""

# Local Modules
from api_backend.models.models import (
    AssetCreateRequest,
    AssetUpdateRequest,
    AssetMetadataResponse,
    PresignedUrlResponse,
    PaginatedAssetResponse,
)

__all__ = [
    "AssetCreateRequest",
    "AssetUpdateRequest",
    "AssetMetadataResponse",
    "PresignedUrlResponse",
    "PaginatedAssetResponse",
]
