# Standard Library
import uuid
import datetime
from typing import List, Optional

# Third Party
from pydantic import BaseModel, Field, HttpUrl, ConfigDict

# Local Modules
from api_backend.utils import ContentType, AssetType


# --- Base Models ---
class AssetBase(BaseModel):
    """Base model for asset metadata, used for both requests and responses."""

    model_config = ConfigDict(populate_by_name=True)

    description: Optional[str] = Field(
        None, description="Description of the asset"
    )
    tags: Optional[List[str]] = Field(
        default_factory=list, description="Tags associated with the asset"
    )
    asset_type: Optional[AssetType] = Field(
        None, description="e.g., NPC, Location, Item, Handout"
    )


# --- Request Models ---
class AssetCreateRequest(AssetBase):
    """Request model for creating a new asset."""

    model_config = ConfigDict(populate_by_name=True)

    file_name: str = Field(
        ..., description="Original name of the file to be uploaded"
    )
    content_type: ContentType = Field(
        ..., description="MIME type of the file, e.g., image/png"
    )


class AssetUpdateRequest(BaseModel):
    """Request model for updating an existing asset's metadata."""

    model_config = ConfigDict(populate_by_name=True)

    description: Optional[str] = Field(
        None, description="Updated description of the asset"
    )
    tags: Optional[List[str]] = Field(
        None, description="Updated list of tags for the asset"
    )
    asset_type: Optional[AssetType] = Field(
        None, description="e.g., NPC, Location, Item, Handout"
    )


# --- Response Models ---
class AssetMetadataResponse(AssetBase):
    """Response model for asset metadata, including S3 details and ownership."""

    model_config = ConfigDict(populate_by_name=True)

    asset_id: uuid.UUID = Field(
        ..., description="Unique identifier for the asset"
    )
    s3_key: str = Field(..., description="S3 object key for the asset file")
    original_file_name: str = Field(
        ..., description="Original uploaded file name"
    )
    content_type: ContentType = Field(..., description="MIME type of the file")
    upload_timestamp: datetime.datetime = Field(
        ..., description="Timestamp of when the asset was uploaded/created"
    )
    last_modified: Optional[datetime.datetime] = Field(
        None, description="Timestamp of the last modification to the asset"
    )
    owner_id: Optional[str] = Field(
        None,
        description=(
            "Identifier of the user who owns the asset (e.g., Cognito sub)"
        ),
    )
    download_url: Optional[HttpUrl] = Field(
        None, description="Temporary presigned URL to download the asset"
    )


class PresignedUrlResponse(BaseModel):
    """Response model for presigned URL generation."""

    model_config = ConfigDict(populate_by_name=True)

    asset_id: uuid.UUID = Field(
        ..., description="Unique identifier for the asset"
    )
    s3_key: str = Field(..., description="S3 object key for the asset file")
    upload_url: HttpUrl = Field(
        ..., description="Presigned URL for uploading the asset file"
    )
    http_method: Optional[str] = Field(
        "PUT", description="HTTP method to use for the presigned URL"
    )


class PaginatedAssetResponse(BaseModel):
    """Response model for paginated asset listing."""

    model_config = ConfigDict(populate_by_name=True)

    assets: List[AssetMetadataResponse] = Field(
        default_factory=list, description="List of assets in the response"
    )
    total_count: int = Field(
        ..., description="Total number of assets available"
    )
    next_token: Optional[str] = Field(
        None, description="Token for the next page of results"
    )
