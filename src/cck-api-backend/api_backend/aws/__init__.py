"""AWS module for the CCK API Backend.

This module provides AWS-related functionality for the CCK API Backend,
including clients for DynamoDB and S3. It allows for easy access to these
services without needing to import them individually in other parts of the codebase.
"""

# Local Modules
from api_backend.aws.dynamodb import DynamoDb
from api_backend.aws.s3 import S3Client

__all__ = [
    "DynamoDb",
    "S3Client",
]
