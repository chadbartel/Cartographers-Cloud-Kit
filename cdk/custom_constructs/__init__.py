"""This module provides custom constructs for AWS CDK applications.

These constructs extend the functionality of AWS CDK by providing reusable
components for common AWS services such as API Gateway, Lambda, DynamoDB, S3,
and IAM. Each construct is designed to simplify the creation and management of
AWS resources with sensible defaults and additional features.

The constructs included in this module are:
- `ApiCustomDomain`: Custom domain for API Gateway.
- `CustomCognitoUserPool`: Custom Cognito User Pool.
- `CustomDynamoDBTable`: Custom DynamoDB Table with additional configurations.
- `CustomHttpApiGateway`: Custom HTTP API Gateway.
- `CustomHttpLambdaAuthorizer`: Custom Lambda authorizer for HTTP APIs.
- `CustomIAMPolicyStatement`: Custom IAM Policy Statement.
- `CustomIamRole`: Custom IAM Role with additional configurations.
- `CustomLambdaFromDockerImage`: Custom Lambda function created from a Docker image.
- `CustomRestApi`: Custom REST API with additional configurations.
- `CustomS3Bucket`: Custom S3 Bucket with additional configurations.
- `CustomCorsRule`: Custom CORS rule for S3 Buckets.
- `CustomTokenAuthorizer`: Custom Token Authorizer for API Gateway.
"""

from .api_custom_domain import ApiCustomDomain
from .cognito_user_pool import CustomCognitoUserPool
from .dynamodb_table import CustomDynamoDBTable
from .http_api import CustomHttpApiGateway
from .http_lambda_authorizer import CustomHttpLambdaAuthorizer
from .iam_policy_statement import CustomIAMPolicyStatement
from .iam_role import CustomIamRole
from .lambda_function import CustomLambdaFromDockerImage
from .rest_api import CustomRestApi
from .s3_bucket import CustomS3Bucket, CustomCorsRule
from .token_authorizer import CustomTokenAuthorizer

__all__ = [
    "ApiCustomDomain",
    "CustomCognitoUserPool",
    "CustomDynamoDBTable",
    "CustomHttpApiGateway",
    "CustomHttpLambdaAuthorizer",
    "CustomIAMPolicyStatement",
    "CustomIamRole",
    "CustomLambdaFromDockerImage",
    "CustomRestApi",
    "CustomS3Bucket",
    "CustomCorsRule",
    "CustomTokenAuthorizer",
]
