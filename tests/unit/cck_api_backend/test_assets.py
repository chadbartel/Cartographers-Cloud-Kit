"""Unit tests for the assets router module."""

# Standard Library
import os
import uuid
import datetime
from unittest.mock import Mock, patch, MagicMock
from typing import Any, Dict, List

# Third Party
import pytest
import boto3
from fastapi import HTTPException, status
from fastapi.testclient import TestClient
from moto import mock_aws
from boto3.dynamodb.conditions import Attr, Key

# Local Modules
from api_backend.routers.assets import (
    initiate_asset_upload,
    list_assets,
    get_asset_details,
    update_asset_metadata,
    delete_asset,
    S3_BUCKET_NAME,
    DYNAMODB_TABLE_NAME,
)
from api_backend.models import (
    AssetCreateRequest,
    AssetUpdateRequest,
    AssetMetadataResponse,
    PresignedUrlResponse,
    PaginatedAssetResponse,
)
from api_backend.utils import AssetType


class TestInitiateAssetUpload:
    """Test cases for the initiate_asset_upload endpoint."""

    @pytest.fixture
    def mock_dependencies(self):
        """Mock all external dependencies."""
        with (
            patch(
                "api_backend.routers.assets.extract_username_from_basic_auth"
            ) as mock_auth,
            patch("api_backend.routers.assets.S3Client") as mock_s3_client,
            patch("api_backend.routers.assets.DynamoDb") as mock_dynamo_client,
            patch("api_backend.routers.assets.uuid.uuid4") as mock_uuid,
        ):

            # Configure mock returns
            mock_auth.return_value = "testuser"
            mock_uuid.return_value = uuid.UUID(
                "12345678-1234-5678-9abc-123456789abc"
            )

            # Mock S3 client
            mock_s3_instance = Mock()
            mock_s3_instance.generate_presigned_upload_url.return_value = (
                "https://test-upload-url.com"
            )
            mock_s3_client.return_value = mock_s3_instance

            # Mock DynamoDB client
            mock_dynamo_instance = Mock()
            mock_dynamo_client.return_value = mock_dynamo_instance

            yield {
                "auth": mock_auth,
                "s3_client": mock_s3_client,
                "s3_instance": mock_s3_instance,
                "dynamo_client": mock_dynamo_client,
                "dynamo_instance": mock_dynamo_instance,
                "uuid": mock_uuid,
            }

    @pytest.fixture
    def asset_create_request(self):
        """Sample asset create request."""
        return AssetCreateRequest(
            file_name="test_image.jpg",
            description="Test asset description",
            tags=["test", "image"],
            asset_type=AssetType.item,
        )

    async def test_initiate_asset_upload_success(
        self, mock_dependencies, asset_create_request
    ):
        """Test successful asset upload initiation."""
        # Act
        result = await initiate_asset_upload(
            x_cck_username_password="dGVzdDp0ZXN0",  # base64 for "test:test"
            asset_data=asset_create_request,
        )

        # Assert
        assert isinstance(result, PresignedUrlResponse)
        assert result.asset_id == uuid.UUID(
            "12345678-1234-5678-9abc-123456789abc"
        )
        assert (
            result.s3_key
            == "testuser/12345678-1234-5678-9abc-123456789abc/test_image.jpg"
        )
        assert str(result.upload_url) == "https://test-upload-url.com/"

        # Verify S3 client was called correctly
        mock_dependencies["s3_client"].assert_called_once_with(
            bucket_name=S3_BUCKET_NAME
        )
        mock_dependencies[
            "s3_instance"
        ].generate_presigned_upload_url.assert_called_once_with(
            object_key="testuser/12345678-1234-5678-9abc-123456789abc/test_image.jpg"
        )

        # Verify DynamoDB client was called correctly
        mock_dependencies["dynamo_client"].assert_called_once_with(
            table_name=DYNAMODB_TABLE_NAME
        )
        mock_dependencies["dynamo_instance"].put_item.assert_called_once()

        # Verify the metadata structure
        put_item_args = mock_dependencies[
            "dynamo_instance"
        ].put_item.call_args[1]["item"]
        assert put_item_args["owner_id"] == "testuser"
        assert (
            put_item_args["asset_id"] == "12345678-1234-5678-9abc-123456789abc"
        )
        assert put_item_args["description"] == "Test asset description"
        assert put_item_args["tags"] == ["test", "image"]
        assert put_item_args["asset_type"] == "Item"
        assert (
            put_item_args["s3_key"]
            == "testuser/12345678-1234-5678-9abc-123456789abc/test_image.jpg"
        )
        assert put_item_args["original_file_name"] == "test_image.jpg"
        assert "upload_timestamp" in put_item_args
        assert "last_modified" in put_item_args

    async def test_initiate_asset_upload_minimal_request(
        self, mock_dependencies
    ):
        """Test asset upload initiation with minimal required fields."""
        # Arrange
        minimal_request = AssetCreateRequest(file_name="minimal.txt")

        # Act
        result = await initiate_asset_upload(
            x_cck_username_password="dGVzdDp0ZXN0",
            asset_data=minimal_request,
        )

        # Assert
        assert isinstance(result, PresignedUrlResponse)
        assert (
            result.s3_key
            == "testuser/12345678-1234-5678-9abc-123456789abc/minimal.txt"
        )

        # Verify metadata with None values for optional fields
        put_item_args = mock_dependencies[
            "dynamo_instance"
        ].put_item.call_args[1]["item"]
        assert put_item_args["description"] is None
        assert put_item_args["tags"] == []
        assert put_item_args["asset_type"] is None


class TestListAssets:
    """Test cases for the list_assets endpoint."""

    @pytest.fixture
    def mock_dependencies(self):
        """Mock all external dependencies."""
        with (
            patch(
                "api_backend.routers.assets.extract_username_from_basic_auth"
            ) as mock_auth,
            patch("api_backend.routers.assets.DynamoDb") as mock_dynamo_client,
        ):

            mock_auth.return_value = "testuser"

            # Mock DynamoDB client
            mock_dynamo_instance = Mock()
            mock_dynamo_client.return_value = mock_dynamo_instance

            yield {
                "auth": mock_auth,
                "dynamo_client": mock_dynamo_client,
                "dynamo_instance": mock_dynamo_instance,
            }

    @pytest.fixture
    def sample_dynamo_response(self):
        """Sample DynamoDB response for list assets."""
        return {
            "Items": [
                {
                    "owner_id": "testuser",
                    "asset_id": "12345678-1234-5678-9abc-123456789ab1",
                    "description": "Test asset 1",
                    "tags": ["test", "python"],
                    "asset_type": "Item",
                    "s3_key": "testuser/12345678-1234-5678-9abc-123456789ab1/file1.jpg",
                    "original_file_name": "file1.jpg",
                    "upload_timestamp": "2025-01-01T00:00:00Z",
                    "last_modified": "2025-01-01T00:00:00Z",
                },
                {
                    "owner_id": "testuser",
                    "asset_id": "12345678-1234-5678-9abc-123456789ab2",
                    "description": "Test asset 2",
                    "tags": ["test", "javascript"],
                    "asset_type": "NPC",
                    "s3_key": "testuser/12345678-1234-5678-9abc-123456789ab2/file2.png",
                    "original_file_name": "file2.png",
                    "upload_timestamp": "2025-01-02T00:00:00Z",
                    "last_modified": "2025-01-02T00:00:00Z",
                },
            ],
            "Count": 2,
        }

    async def test_list_assets_no_filters(
        self, mock_dependencies, sample_dynamo_response
    ):
        """Test listing assets without any filters."""
        # Arrange
        mock_dependencies["dynamo_instance"].query.return_value = (
            sample_dynamo_response
        )

        # Act
        result = await list_assets(
            x_cck_username_password="dGVzdDp0ZXN0",
            tags=[],
            match_all_tags=False,
            asset_types=[],
            match_all_types=False,
            limit=20,
            next_token=None,
        )

        # Assert
        assert isinstance(result, PaginatedAssetResponse)
        assert len(result.assets) == 2
        assert result.total_count == 2
        assert result.next_token is None

        # Verify DynamoDB query was called correctly
        mock_dependencies["dynamo_instance"].query.assert_called_once_with(
            key_condition_expression=Key("owner_id").eq("testuser"),
            filter_expression=None,
            limit=20,
            exclusive_start_key=None,
        )

    async def test_list_assets_with_tag_filter_any(
        self, mock_dependencies, sample_dynamo_response
    ):
        """Test listing assets with tag filter (match any)."""
        # Arrange
        mock_dependencies["dynamo_instance"].query.return_value = (
            sample_dynamo_response
        )

        # Act
        result = await list_assets(
            x_cck_username_password="dGVzdDp0ZXN0",
            tags=["python", "javascript"],
            match_all_tags=False,
            asset_types=[],
            match_all_types=False,
            limit=20,
            next_token=None,
        )

        # Assert
        assert isinstance(result, PaginatedAssetResponse)
        assert len(result.assets) == 2

        # Verify filter expression was created for OR logic
        call_args = mock_dependencies["dynamo_instance"].query.call_args[1]
        assert call_args["filter_expression"] is not None

    async def test_list_assets_with_tag_filter_all(
        self, mock_dependencies, sample_dynamo_response
    ):
        """Test listing assets with tag filter (match all)."""
        # Arrange
        mock_dependencies["dynamo_instance"].query.return_value = (
            sample_dynamo_response
        )

        # Act
        result = await list_assets(
            x_cck_username_password="dGVzdDp0ZXN0",
            tags=["test", "python"],
            match_all_tags=True,
            asset_types=[],
            match_all_types=False,
            limit=20,
            next_token=None,
        )

        # Assert
        assert isinstance(result, PaginatedAssetResponse)
        call_args = mock_dependencies["dynamo_instance"].query.call_args[1]
        assert call_args["filter_expression"] is not None

    async def test_list_assets_with_asset_type_filter(
        self, mock_dependencies, sample_dynamo_response
    ):
        """Test listing assets with asset type filter."""
        # Arrange
        mock_dependencies["dynamo_instance"].query.return_value = (
            sample_dynamo_response
        )

        # Act
        result = await list_assets(
            x_cck_username_password="dGVzdDp0ZXN0",
            tags=[],
            match_all_tags=False,
            asset_types=[AssetType.item, AssetType.npc],
            match_all_types=False,
            limit=20,
            next_token=None,
        )

        # Assert
        assert isinstance(result, PaginatedAssetResponse)
        call_args = mock_dependencies["dynamo_instance"].query.call_args[1]
        assert call_args["filter_expression"] is not None

    async def test_list_assets_with_pagination(
        self, mock_dependencies, sample_dynamo_response
    ):
        """Test listing assets with pagination."""
        # Arrange
        sample_dynamo_response["LastEvaluatedKey"] = {"asset_id": "next-token"}
        mock_dependencies["dynamo_instance"].query.return_value = (
            sample_dynamo_response
        )

        # Act
        result = await list_assets(
            x_cck_username_password="dGVzdDp0ZXN0",
            tags=[],
            match_all_tags=False,
            asset_types=[],
            match_all_types=False,
            limit=10,
            next_token="previous-token",
        )

        # Assert
        assert result.next_token == "next-token"

        # Verify pagination was passed correctly
        call_args = mock_dependencies["dynamo_instance"].query.call_args[1]
        assert call_args["exclusive_start_key"] == {
            "asset_id": "previous-token"
        }
        assert call_args["limit"] == 10

    async def test_list_assets_empty_response(self, mock_dependencies):
        """Test listing assets when no assets exist."""
        # Arrange
        mock_dependencies["dynamo_instance"].query.return_value = {
            "Items": [],
            "Count": 0,
        }

        # Act
        result = await list_assets(
            x_cck_username_password="dGVzdDp0ZXN0",
            tags=[],
            match_all_tags=False,
            asset_types=[],
            match_all_types=False,
            limit=20,
            next_token=None,
        )

        # Assert        assert isinstance(result, PaginatedAssetResponse)
        assert len(result.assets) == 0
        assert result.total_count == 0
        assert result.next_token is None

    async def test_list_assets_with_match_all_types_true(
        self, mock_dependencies
    ):
        """Test listing assets with match_all_types=True."""
        # Arrange
        mock_dynamo_instance = mock_dependencies["dynamo_instance"]

        # Mock DynamoDB response
        mock_dynamo_instance.query.return_value = {"Items": [], "Count": 0}

        # Act
        result = await list_assets(
            x_cck_username_password="dGVzdDp0ZXN0",
            tags=[],
            match_all_tags=False,
            asset_types=[AssetType.item, AssetType.npc],
            match_all_types=True,
            limit=20,
            next_token=None,
        )

        # Assert
        assert isinstance(result, PaginatedAssetResponse)
        assert len(result.assets) == 0
        assert result.total_count == 0
        assert result.next_token is None

        # Verify that query was called with the correct filter expression
        # for match_all_types=True (should use & operator)
        mock_dynamo_instance.query.assert_called_once()


class TestGetAssetDetails:
    """Test cases for the get_asset_details endpoint."""

    @pytest.fixture
    def mock_dependencies(self):
        """Mock all external dependencies."""
        with (
            patch(
                "api_backend.routers.assets.extract_username_from_basic_auth"
            ) as mock_auth,
            patch("api_backend.routers.assets.DynamoDb") as mock_dynamo_client,
            patch("api_backend.routers.assets.S3Client") as mock_s3_client,
        ):

            mock_auth.return_value = "testuser"

            # Mock DynamoDB client
            mock_dynamo_instance = Mock()
            mock_dynamo_client.return_value = mock_dynamo_instance

            # Mock S3 client
            mock_s3_instance = Mock()
            mock_s3_instance.generate_presigned_download_url.return_value = (
                "https://test-download-url.com"
            )
            mock_s3_client.return_value = mock_s3_instance

            yield {
                "auth": mock_auth,
                "dynamo_client": mock_dynamo_client,
                "dynamo_instance": mock_dynamo_instance,
                "s3_client": mock_s3_client,
                "s3_instance": mock_s3_instance,
            }

    @pytest.fixture
    def sample_asset_data(self):
        """Sample asset data from DynamoDB."""
        return {
            "Items": [
                {
                    "owner_id": "testuser",
                    "asset_id": "12345678-1234-5678-9abc-123456789abc",
                    "description": "Test asset",
                    "tags": ["test"],
                    "asset_type": "Item",
                    "s3_key": "testuser/12345678-1234-5678-9abc-123456789abc/file.jpg",
                    "original_file_name": "file.jpg",
                    "upload_timestamp": "2025-01-01T00:00:00Z",
                    "last_modified": "2025-01-01T00:00:00Z",
                }
            ]
        }

    async def test_get_asset_details_success(
        self, mock_dependencies, sample_asset_data
    ):
        """Test successful asset details retrieval."""
        # Arrange
        asset_id = uuid.UUID("12345678-1234-5678-9abc-123456789abc")
        mock_dependencies["dynamo_instance"].query.return_value = (
            sample_asset_data
        )

        # Act
        result = await get_asset_details(
            x_cck_username_password="dGVzdDp0ZXN0",
            asset_id=asset_id,
        )

        # Assert
        assert isinstance(result, AssetMetadataResponse)
        assert result.asset_id == asset_id
        assert result.description == "Test asset"
        assert str(result.download_url) == "https://test-download-url.com/"

        # Verify DynamoDB query
        mock_dependencies["dynamo_instance"].query.assert_called_once()
        call_args = mock_dependencies["dynamo_instance"].query.call_args[1]
        assert "key_condition_expression" in call_args
        assert "filter_expression" in call_args

        # Verify S3 download URL generation
        mock_dependencies[
            "s3_instance"
        ].generate_presigned_download_url.assert_called_once_with(
            object_key="testuser/12345678-1234-5678-9abc-123456789abc/file.jpg"
        )

    async def test_get_asset_details_not_found(self, mock_dependencies):
        """Test asset details retrieval when asset doesn't exist."""
        # Arrange
        asset_id = uuid.UUID("12345678-1234-5678-9abc-123456789abc")
        mock_dependencies["dynamo_instance"].query.return_value = {"Items": []}

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_asset_details(
                x_cck_username_password="dGVzdDp0ZXN0",
                asset_id=asset_id,
            )

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert exc_info.value.detail == "Asset not found or access denied"


class TestUpdateAssetMetadata:
    """Test cases for the update_asset_metadata endpoint."""

    @pytest.fixture
    def mock_dependencies(self):
        """Mock all external dependencies."""
        with (
            patch(
                "api_backend.routers.assets.extract_username_from_basic_auth"
            ) as mock_auth,
            patch("api_backend.routers.assets.DynamoDb") as mock_dynamo_client,
            patch("api_backend.routers.assets.datetime") as mock_datetime,
        ):

            mock_auth.return_value = "testuser"

            # Mock datetime
            mock_datetime.datetime.now.return_value.isoformat.return_value = (
                "2025-01-01T12:00:00Z"
            )
            mock_datetime.timezone.utc = datetime.timezone.utc

            # Mock DynamoDB client
            mock_dynamo_instance = Mock()
            mock_dynamo_client.return_value = mock_dynamo_instance

            yield {
                "auth": mock_auth,
                "dynamo_client": mock_dynamo_client,
                "dynamo_instance": mock_dynamo_instance,
                "datetime": mock_datetime,
            }

    @pytest.fixture
    def sample_updated_asset(self):
        """Sample updated asset data."""
        return {
            "Attributes": {
                "owner_id": "testuser",
                "asset_id": "12345678-1234-5678-9abc-123456789abc",
                "description": "Updated description",
                "tags": ["updated", "test"],
                "asset_type": "NPC",
                "s3_key": "testuser/12345678-1234-5678-9abc-123456789abc/file.jpg",
                "original_file_name": "file.jpg",
                "upload_timestamp": "2025-01-01T00:00:00Z",
                "last_modified": "2025-01-01T12:00:00Z",
            }
        }

    async def test_update_asset_metadata_success(
        self, mock_dependencies, sample_updated_asset
    ):
        """Test successful asset metadata update."""
        # Arrange
        asset_id = uuid.UUID("12345678-1234-5678-9abc-123456789abc")
        update_data = AssetUpdateRequest(
            description="Updated description",
            tags=["updated", "test"],
            asset_type=AssetType.npc,
        )
        mock_dependencies["dynamo_instance"].update_item.return_value = (
            sample_updated_asset
        )

        # Act
        result = await update_asset_metadata(
            x_cck_username_password="dGVzdDp0ZXN0",
            asset_id=asset_id,
            update_data=update_data,
        )

        # Assert
        assert isinstance(result, AssetMetadataResponse)
        assert result.description == "Updated description"
        assert result.tags == ["updated", "test"]
        assert result.asset_type == AssetType.npc

        # Verify DynamoDB update was called correctly
        mock_dependencies["dynamo_instance"].update_item.assert_called_once()
        call_args = mock_dependencies["dynamo_instance"].update_item.call_args[
            1
        ]
        assert call_args["key"] == {
            "owner_id": "testuser",
            "asset_id": str(asset_id),
        }
        assert "update_expression" in call_args
        assert "expression_attribute_values" in call_args

    async def test_update_asset_metadata_partial(
        self, mock_dependencies, sample_updated_asset
    ):
        """Test partial asset metadata update."""
        # Arrange
        asset_id = uuid.UUID("12345678-1234-5678-9abc-123456789abc")
        update_data = AssetUpdateRequest(
            description="Only description updated"
        )

        # Modify the sample response to match partial update
        sample_updated_asset["Attributes"][
            "description"
        ] = "Only description updated"
        mock_dependencies["dynamo_instance"].update_item.return_value = (
            sample_updated_asset
        )

        # Act
        result = await update_asset_metadata(
            x_cck_username_password="dGVzdDp0ZXN0",
            asset_id=asset_id,
            update_data=update_data,
        )

        # Assert
        assert isinstance(result, AssetMetadataResponse)
        assert result.description == "Only description updated"

        # Verify only description and last_modified were included in update
        call_args = mock_dependencies["dynamo_instance"].update_item.call_args[
            1
        ]
        expression_values = call_args["expression_attribute_values"]
        assert ":description" in expression_values
        assert ":last_modified" in expression_values
        # Should not include tags or asset_type since they weren't provided
        assert (
            len(
                [
                    k
                    for k in expression_values.keys()
                    if not k.endswith("last_modified")
                ]
            )
            == 1
        )


class TestDeleteAsset:
    """Test cases for the delete_asset endpoint."""

    @pytest.fixture
    def mock_dependencies(self):
        """Mock all external dependencies."""
        with (
            patch(
                "api_backend.routers.assets.extract_username_from_basic_auth"
            ) as mock_auth,
            patch("api_backend.routers.assets.DynamoDb") as mock_dynamo_client,
            patch("api_backend.routers.assets.S3Client") as mock_s3_client,
        ):

            mock_auth.return_value = "testuser"

            # Mock DynamoDB client
            mock_dynamo_instance = Mock()
            mock_dynamo_client.return_value = mock_dynamo_instance

            # Mock S3 client
            mock_s3_instance = Mock()
            mock_s3_instance.object_exists.return_value = True
            mock_s3_instance.delete_object.return_value = True
            mock_s3_client.return_value = mock_s3_instance

            yield {
                "auth": mock_auth,
                "dynamo_client": mock_dynamo_client,
                "dynamo_instance": mock_dynamo_instance,
                "s3_client": mock_s3_client,
                "s3_instance": mock_s3_instance,
            }

    @pytest.fixture
    def sample_asset_data(self):
        """Sample asset data for deletion."""
        return {
            "Items": [
                {
                    "owner_id": "testuser",
                    "asset_id": "12345678-1234-5678-9abc-123456789abc",
                    "s3_key": "testuser/12345678-1234-5678-9abc-123456789abc/file.jpg",
                }
            ]
        }

    async def test_delete_asset_success(
        self, mock_dependencies, sample_asset_data
    ):
        """Test successful asset deletion."""
        # Arrange
        asset_id = uuid.UUID("12345678-1234-5678-9abc-123456789abc")
        mock_dependencies["dynamo_instance"].query.return_value = (
            sample_asset_data
        )

        # Act
        result = await delete_asset(
            x_cck_username_password="dGVzdDp0ZXN0",
            asset_id=asset_id,
        )

        # Assert
        assert result is None

        # Verify DynamoDB operations
        mock_dependencies["dynamo_instance"].query.assert_called_once()
        mock_dependencies[
            "dynamo_instance"
        ].delete_item.assert_called_once_with(
            key={"owner_id": "testuser", "asset_id": str(asset_id)}
        )

        # Verify S3 operations
        mock_dependencies["s3_instance"].object_exists.assert_called_once_with(
            object_key="testuser/12345678-1234-5678-9abc-123456789abc/file.jpg"
        )
        mock_dependencies["s3_instance"].delete_object.assert_called_once_with(
            object_key="testuser/12345678-1234-5678-9abc-123456789abc/file.jpg"
        )

    async def test_delete_asset_not_found_in_dynamo(self, mock_dependencies):
        """Test asset deletion when asset doesn't exist in DynamoDB."""
        # Arrange
        asset_id = uuid.UUID("12345678-1234-5678-9abc-123456789abc")
        mock_dependencies["dynamo_instance"].query.return_value = {"Items": []}

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await delete_asset(
                x_cck_username_password="dGVzdDp0ZXN0",
                asset_id=asset_id,
            )

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert exc_info.value.detail == "Asset not found or access denied"

        # Verify DynamoDB delete was not called
        mock_dependencies["dynamo_instance"].delete_item.assert_not_called()

    async def test_delete_asset_file_not_found_in_s3(
        self, mock_dependencies, sample_asset_data
    ):
        """Test asset deletion when file doesn't exist in S3."""
        # Arrange
        asset_id = uuid.UUID("12345678-1234-5678-9abc-123456789abc")
        mock_dependencies["dynamo_instance"].query.return_value = (
            sample_asset_data
        )
        mock_dependencies["s3_instance"].object_exists.return_value = False

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await delete_asset(
                x_cck_username_password="dGVzdDp0ZXN0",
                asset_id=asset_id,
            )

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert exc_info.value.detail == "Asset file not found in S3"

        # Verify DynamoDB delete was still called (metadata cleanup)
        mock_dependencies["dynamo_instance"].delete_item.assert_called_once()

        # Verify S3 delete was not called
        mock_dependencies["s3_instance"].delete_object.assert_not_called()


class TestEnvironmentVariables:
    """Test cases for environment variable handling."""

    def test_environment_variables_defaults(self):
        """Test that environment variables have correct default values."""
        # Note: These are imported from the module, so they'll use actual env vars
        # but we can test the defaults are reasonable
        assert S3_BUCKET_NAME is not None
        assert DYNAMODB_TABLE_NAME is not None

    @patch.dict(os.environ, {"S3_BUCKET_NAME": "custom-bucket"})
    def test_custom_s3_bucket_name(self):
        """Test custom S3 bucket name from environment."""
        # Re-import to get updated env var
        # Standard Library
        from importlib import reload

        # Local Modules
        import api_backend.routers.assets

        reload(api_backend.routers.assets)

        assert api_backend.routers.assets.S3_BUCKET_NAME == "custom-bucket"

    @patch.dict(os.environ, {"DYNAMODB_TABLE_NAME": "custom-table"})
    def test_custom_dynamodb_table_name(self):
        """Test custom DynamoDB table name from environment."""
        # Re-import to get updated env var
        # Standard Library
        from importlib import reload

        # Local Modules
        import api_backend.routers.assets

        reload(api_backend.routers.assets)

        assert api_backend.routers.assets.DYNAMODB_TABLE_NAME == "custom-table"


class TestFilterExpressionLogic:
    """Test cases for complex filter expression logic."""

    @pytest.fixture
    def mock_dependencies(self):
        """Mock dependencies for filter testing."""
        with (
            patch(
                "api_backend.routers.assets.extract_username_from_basic_auth"
            ) as mock_auth,
            patch("api_backend.routers.assets.DynamoDb") as mock_dynamo_client,
        ):

            mock_auth.return_value = "testuser"
            mock_dynamo_instance = Mock()
            mock_dynamo_instance.query.return_value = {"Items": [], "Count": 0}
            mock_dynamo_client.return_value = mock_dynamo_instance

            yield {
                "auth": mock_auth,
                "dynamo_client": mock_dynamo_client,
                "dynamo_instance": mock_dynamo_instance,
            }

    async def test_combined_tag_and_asset_type_filters(
        self, mock_dependencies
    ):
        """Test combined tag and asset type filters."""
        # Act
        await list_assets(
            x_cck_username_password="dGVzdDp0ZXN0",
            tags=["python"],
            match_all_tags=False,
            asset_types=[AssetType.item],
            match_all_types=False,
            limit=20,
            next_token=None,
        )

        # Assert
        call_args = mock_dependencies["dynamo_instance"].query.call_args[1]
        assert call_args["filter_expression"] is not None
        # The filter should combine both tag and asset type conditions

    async def test_empty_tag_list_ignored(self, mock_dependencies):
        """Test that empty tag lists are properly ignored."""
        # Act
        await list_assets(
            x_cck_username_password="dGVzdDp0ZXN0",
            tags=[],
            match_all_tags=True,
            asset_types=[AssetType.npc],
            match_all_types=False,
            limit=20,
            next_token=None,
        )

        # Assert
        call_args = mock_dependencies["dynamo_instance"].query.call_args[1]
        # Should only have asset type filter, not tag filter
        assert call_args["filter_expression"] is not None

    async def test_single_tag_filter(self, mock_dependencies):
        """Test filter with single tag."""
        # Act
        await list_assets(
            x_cck_username_password="dGVzdDp0ZXN0",
            tags=["python"],
            match_all_tags=False,
            asset_types=[],
            match_all_types=False,
            limit=20,
            next_token=None,
        )

        # Assert
        call_args = mock_dependencies["dynamo_instance"].query.call_args[1]
        assert call_args["filter_expression"] is not None

    async def test_single_asset_type_filter(self, mock_dependencies):
        """Test filter with single asset type."""
        # Act
        await list_assets(
            x_cck_username_password="dGVzdDp0ZXN0",
            tags=[],
            match_all_tags=False,
            asset_types=[AssetType.item],
            match_all_types=False,
            limit=20,
            next_token=None,
        )

        # Assert
        call_args = mock_dependencies["dynamo_instance"].query.call_args[1]
        assert call_args["filter_expression"] is not None
