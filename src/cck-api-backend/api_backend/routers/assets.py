# Standard Library
import os
import uuid
import datetime
from typing import Optional, Dict, Any, Annotated, List

# Third Party
from aws_lambda_powertools import Logger
from fastapi import (
    APIRouter,
    HTTPException,
    Depends,
    Query,
    Body,
    status,
    Header,
    Path,
)
from boto3.dynamodb.conditions import Attr, Key

# Local Modules
from api_backend.dependencies import verify_source_ip
from api_backend.models import (
    AssetCreateRequest,
    AssetUpdateRequest,
    AssetMetadataResponse,
    PresignedUrlResponse,
    PaginatedAssetResponse,
)
from api_backend.utils import extract_username_from_basic_auth, AssetType
from api_backend.aws import DynamoDb, S3Client

# Initialize logger
logger = Logger(service="assets")

# Initialize router for asset management
router = APIRouter(
    prefix="/assets",
    tags=["Assets"],
    dependencies=[Depends(verify_source_ip)],
)

# Get environment variables for S3 and DynamoDB
S3_BUCKET_NAME = os.environ.get(
    "S3_BUCKET_NAME", "cartographers-cloud-kit-assets"
)
DYNAMO_TABLE_NAME = os.environ.get(
    "DYNAMO_TABLE_NAME", "cartographers-cloud-kit-metadata"
)


@router.post(
    "/initiate-upload",
    response_model=PresignedUrlResponse,
    status_code=status.HTTP_201_CREATED,
)
async def initiate_asset_upload(
    x_cck_username_password: Annotated[str, Header(...)],
    asset_data: AssetCreateRequest = Body(...),
) -> PresignedUrlResponse:
    """Initiates the upload process for a new asset by generating a

    Parameters
    ----------
    **x_cck_username_password** : str
        Basic Auth header containing base64 encoded username and password.
    **asset_data** : AssetCreateRequest
        Data required to create a new asset, including file name, content type,
        description, tags, and asset type.

    Returns
    -------
    PresignedUrlResponse
        Contains the asset ID, S3 key, and a presigned URL for uploading the
        asset file to S3.
    """
    # Generate a unique asset ID
    asset_id = uuid.uuid4()

    # Extract username from Basic Auth header
    owner_id = extract_username_from_basic_auth(x_cck_username_password)

    # Construct S3 key
    s3_key = f"{owner_id}/{str(asset_id)}/{asset_data.file_name}"

    # Create S3 client instance
    s3_client = S3Client(bucket_name=S3_BUCKET_NAME)

    # Generate a presigned URL for uploading the asset
    upload_url = s3_client.generate_presigned_upload_url(
        object_key=s3_key,
        content_type=asset_data.content_type,
    )

    # Store initial metadata of the asset
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    asset_metadata = {
        "asset_id": str(asset_id),
        "description": asset_data.description,
        "tags": asset_data.tags,
        "asset_type": (
            asset_data.asset_type.value if asset_data.asset_type else None
        ),
        "s3_key": s3_key,
        "original_file_name": asset_data.file_name,
        "content_type": asset_data.content_type,
        "upload_timestamp": timestamp,
        "last_modified": timestamp,
        "owner_id": owner_id,
    }

    # Create a DynamoDB client instance
    dynamo_client = DynamoDb(table_name=DYNAMO_TABLE_NAME)

    # Store the asset metadata in DynamoDB
    dynamo_client.put_item(item=asset_metadata)

    return PresignedUrlResponse(
        asset_id=asset_id, s3_key=s3_key, upload_url=upload_url
    )


@router.get("", response_model=PaginatedAssetResponse)
async def list_assets(
    x_cck_username_password: Annotated[str, Header(...)],
    tags: Optional[List[str]] = Query(
        default_factory=list, description="Filter assets by specific tag(s)"
    ),
    match_all_tags: bool = Query(False, description="Match all tags provided"),
    asset_types: Optional[List[AssetType]] = Query(
        default_factory=list, description="Filter by asset type(s)"
    ),
    match_all_types: bool = Query(
        False, description="Match all asset types provided"
    ),
    limit: int = Query(
        20, ge=1, le=100, description="Number of assets to return"
    ),
    next_token: Optional[str] = Query(
        None, description="Token for pagination"
    ),
) -> PaginatedAssetResponse:
    """Lists assets owned by the authenticated user, with optional filtering by
    tags and asset types.

    Parameters
    ----------
    **x_cck_username_password** : str
        Basic Auth header containing base64 encoded username and password.
    **tags** : Optional[List[str]]
        List of tags to filter assets by. If provided, assets must match these
        tags.
    **match_all_tags** : bool
        If True, assets must match all provided tags. If False, assets can
        match any of the provided tags.
    **asset_types** : Optional[List[AssetType]]
        List of asset types to filter assets by. If provided, assets must match
        these types.
    **match_all_types** : bool
        If True, assets must match all provided asset types. If False, assets
        can match any of the provided types.
    **limit** : int
        Maximum number of assets to return. Defaults to 20, with a maximum of
        100.
    **next_token** : Optional[str]
        Token for pagination to retrieve the next set of results.

    Returns
    -------
    PaginatedAssetResponse
        A paginated response containing the list of assets, total count, and
        next token for pagination.
    """
    # Extract username from Basic Auth header
    owner_id = extract_username_from_basic_auth(x_cck_username_password)

    # Construct a filter expression based on the provided tag(s)
    tag_filter_expression = None
    if tags:
        if match_all_tags:
            # Match all tags provided
            tag_filter_expression = Attr("tags").contains(tags[0])
            for tag in tags[1:]:
                tag_filter_expression &= Attr("tags").contains(tag)
        else:
            # Match any of the tags provided
            tag_filter_expression = Attr("tags").is_in(tags)

    # Construct a filter expression based on the provided asset type
    asset_type_filter_expression = None
    if asset_types:
        if match_all_types:
            # Match all asset types provided
            asset_type_filter_expression = Attr("asset_type").eq(
                asset_types[0].value
            )
            for asset_type in asset_types[1:]:
                asset_type_filter_expression &= Attr("asset_type").eq(
                    asset_type.value
                )
        else:
            # Match any of the asset types provided
            asset_type_filter_expression = Attr("asset_type").is_in(
                [at.value for at in asset_types]
            )

    # Combine all filter expressions
    combined_filter_expression = None
    if tag_filter_expression and asset_type_filter_expression:
        combined_filter_expression = (
            tag_filter_expression & asset_type_filter_expression
        )
    elif tag_filter_expression:
        combined_filter_expression = tag_filter_expression
    elif asset_type_filter_expression:
        combined_filter_expression = asset_type_filter_expression

    # Construct key condition expression to filter by owner_id
    key_condition_expression = Key("owner_id").eq(owner_id)

    # Create a client instance for DynamoDB
    dynamo_client = DynamoDb(table_name=DYNAMO_TABLE_NAME)

    # Query DynamoDB for assets
    response: Dict[str, Any] = dynamo_client.query(
        key_condition_expression=key_condition_expression,
        filter_expression=combined_filter_expression,
        limit=limit,
        exclusive_start_key={"S": next_token} if next_token else None,
    )
    filtered_assets = response.get("Items", [])

    # Get total count
    total_count: int = response.get("Count", 0)

    # Extract next token for pagination
    new_next_token: Optional[str] = filtered_assets.get(
        "LastEvaluatedKey", {}
    ).get("S", None)

    # Convert DynamoDB items to AssetMetadataResponse models
    paginated_assets = [
        AssetMetadataResponse(**filtered_asset)
        for filtered_asset in filtered_assets
    ]

    return PaginatedAssetResponse(
        assets=paginated_assets,
        total_count=total_count,
        next_token=new_next_token,
    )


@router.get("/{asset_id}", response_model=AssetMetadataResponse)
async def get_asset_details(
    x_cck_username_password: Annotated[str, Header(...)],
    asset_id: uuid.UUID = Path(
        ..., description="Unique identifier for the asset"
    ),
) -> AssetMetadataResponse:
    """Retrieves metadata and a presigned download URL for an asset.

    Parameters
    ----------
    **x_cck_username_password** : str
        Basic Auth header containing base64 encoded username and password.
    **asset_id** : uuid.UUID
        Unique identifier for the asset to retrieve.

    Returns
    -------
    AssetMetadataResponse
        Contains metadata about the asset, including a presigned URL for
        downloading the asset file from S3.

    Raises
    ------
    HTTPException
        If the asset is not found or access is denied, a 404 Not Found error is
        raised.
    """
    # Extract username from Basic Auth header
    owner_id = extract_username_from_basic_auth(x_cck_username_password)

    # Create a client instance for DynamoDB
    dynamo_client = DynamoDb(table_name=DYNAMO_TABLE_NAME)

    # Fetch asset metadata from DynamoDB
    asset_data = dynamo_client.query(
        key_condition_expression=Key("asset_id").eq(str(asset_id)),
        filter_expression=Attr("owner_id").eq(owner_id),
    ).get("Items", [])

    # If no asset data found, raise 404 Not Found
    if not asset_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found or access denied",
        )

    # Extract the first item from the list (should be unique)
    asset_data = asset_data[0]

    # Generate a presigned URL for downloading the asset file
    s3_client = S3Client(bucket_name=S3_BUCKET_NAME)
    download_url = s3_client.generate_presigned_download_url(
        object_key=asset_data["s3_key"]
    )

    # Add the download URL to the asset metadata response
    asset_data["download_url"] = download_url

    return AssetMetadataResponse(**asset_data)


@router.put("/{asset_id}", response_model=AssetMetadataResponse)
async def update_asset_metadata(
    x_cck_username_password: Annotated[str, Header(...)],
    asset_id: uuid.UUID = Path(
        ..., description="Unique identifier for the asset"
    ),
    update_data: AssetUpdateRequest = Body(...),
) -> AssetMetadataResponse:
    """Updates metadata for an existing asset in DynamoDB.

    Parameters
    ----------
    **x_cck_username_password** : str
        Basic Auth header containing base64 encoded username and password.
    **asset_id** : uuid.UUID
        Unique identifier for the asset to update.
    **update_data** : AssetUpdateRequest
        Data containing fields to update, such as description, tags, and
        asset type.

    Returns
    -------
    AssetMetadataResponse
        Contains the updated metadata of the asset, including the last modified
        timestamp.

    Raises
    ------
    HTTPException
        If the asset is not found or access is denied, a 404 Not Found error is
        raised.
    """
    # Extract username from Basic Auth header
    owner_id = extract_username_from_basic_auth(x_cck_username_password)

    # Create a client instance for DynamoDB
    dynamo_client = DynamoDb(table_name=DYNAMO_TABLE_NAME)

    # Dump the update data to a dictionary, excluding unset fields
    update_dict = update_data.model_dump(exclude_unset=True)

    # Add last modified timestamp to the update dictionary
    update_dict["last_modified"] = datetime.datetime.now(
        datetime.timezone.utc
    ).isoformat()

    # Update the asset metadata in DynamoDB
    updated_asset = dynamo_client.update_item(
        key={"asset_id": str(asset_id)},
        update_expression="SET "
        + ", ".join(f"{k} = :{k}" for k in update_dict.keys()),
        expression_attribute_values={
            f":{k}": v for k, v in update_dict.items()
        },
    ).get("Attributes", {})

    logger.info(f"Updated asset {asset_id} metadata for owner {owner_id}")

    return AssetMetadataResponse(**updated_asset)


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset(
    x_cck_username_password: Annotated[str, Header(...)],
    asset_id: uuid.UUID = Path(
        ..., description="Unique identifier for the asset"
    ),
) -> None:
    # Extract username from Basic Auth header
    owner_id = extract_username_from_basic_auth(x_cck_username_password)

    # Create a client instance for DynamoDB
    dynamo_client = DynamoDb(table_name=DYNAMO_TABLE_NAME)

    # Get the asset metadata to ensure it exists
    asset_data = dynamo_client.query(
        key_condition_expression=Key("asset_id").eq(str(asset_id)),
        filter_expression=Attr("owner_id").eq(owner_id),
    ).get("Items", [])

    # If no asset data found, raise 404 Not Found
    if not asset_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found or access denied",
        )

    # Delete the asset metadata from DynamoDB
    dynamo_client.delete_item(key={"asset_id": str(asset_id)})

    # Create a client instance for S3
    s3_client = S3Client(bucket_name=S3_BUCKET_NAME)

    # Check if the object exists
    if not s3_client.object_exists(object_key=asset_data[0]["s3_key"]):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset file not found in S3",
        )

    # Delete the asset file from S3
    s3_key = asset_data[0]["s3_key"]
    s3_client.delete_object(object_key=s3_key)

    logger.info(
        f"Deleted asset {asset_id} and its file from S3 for owner {owner_id}"
    )

    return None
