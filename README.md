# Cartographers-Cloud-Kit

A web application allowing Game Masters (GMs) to upload, tag, search, and manage small digital assets like map icons, NPC portraits, location images, art snippets, or short pieces of read-aloud text.

## Features

- **Asset Upload**: Upload and store digital assets (images, text snippets) for your tabletop RPG campaigns
- **Tagging System**: Organize assets with custom tags for easy categorization
- **Search & Filter**: Quickly find assets using tags, keywords, or metadata
- **Asset Management**: Edit, update, or delete assets as your campaign evolves
- **Cloud-Native**: Built on AWS infrastructure for scalability and reliability

## Prerequisites

Before setting up the project, ensure you have the following:

### Required Software

- Python 3.12+ (see [.python-version](.python-version))
- [Poetry](https://python-poetry.org/) for dependency management
- [AWS CLI](https://aws.amazon.com/cli/) configured with appropriate credentials
- [Node.js](https://nodejs.org/) (for AWS CDK)
- [AWS CDK](https://aws.amazon.com/cdk/) v2

### Required AWS Infrastructure

- AWS Account with appropriate permissions
- Route53 hosted zone (for custom domain, optional)
- AWS credentials configured locally

## Installation

1. Clone the repository:

    ```bash
    git clone <repository-url>
    cd Cartographers-Cloud-Kit
    ```

1. Install dependencies using Poetry:

    ```bash
    poetry install
    ```

1. Activate the virtual environment.

1. Install CDK dependencies:

    ```bash
    npm install -g aws-cdk
    ```

## Configuration

1. Update the [cdk.context.json](cdk.context.json) file with your specific settings:

    ```json
    {
      "stack_name_prefix": "your-cool-stack",
      "api_prefix": "/api/v1",
      "domain_name": "your-domain.com",
      "subdomain_name": "your-subdomain",
      "auth_header_name": "x-your-auth-header"
    }
    ```

1. Ensure your AWS credentials are configured:

    ```bash
    aws configure
    ```

## Deployment

The project uses AWS CDK for infrastructure as code. This will create:

- S3 bucket for asset storage
- DynamoDB table for metadata
- Lambda functions for API endpoints
- API Gateway for HTTP endpoints
- CloudFront distribution (if domain configured)
- IAM roles and policies

Deploy the stack:

1. Bootstrap CDK (first time only):

    ```bash
    cdk bootstrap
    ```

1. Deploy the infrastructure:

    ```bash
    cdk deploy
    ```

1. Note the outputs from the deployment, including:

   - Frontend URL
   - API Gateway URL
   - Cognito User Pool ID
   - Cognito User Pool Client ID

## Authentication Setup

This project uses AWS Cognito for user authentication. You need to manually create users in the Cognito User Pool after deployment.

### Finding Your Cognito Configuration

After deployment, you can find your Cognito details in several ways:

#### Option 1: AWS Console
1. Go to the AWS Console → Cognito
2. Find your User Pool (named something like `CartographersUserPool`)
3. Note the **User Pool ID** and **User Pool Client ID**

#### Option 2: CDK Outputs
The CDK deployment will output the Cognito configuration. Look for:
- `CognitoUserPoolId`
- `CognitoUserPoolClientId`

#### Option 3: AWS CLI
```bash
# List all user pools
aws cognito-idp list-user-pools --max-results 10

# Get user pool details
aws cognito-idp describe-user-pool --user-pool-id <USER_POOL_ID>

# List user pool clients
aws cognito-idp list-user-pool-clients --user-pool-id <USER_POOL_ID>
```

### Creating Users Manually

#### Method 1: Using AWS Console

1. **Navigate to Cognito**:

   - Go to AWS Console → Cognito → User Pools
   - Select your `CartographersUserPool` (or the name you specified)

1. **Create a User**:

   - Click "Users" in the left sidebar
   - Click "Create user"
   - Fill in the details:
     - **Username**: `your-username`
     - **Email**: `your-email@example.com`
     - **Temporary password**: Create a secure temporary password
     - **Phone number**: (optional)
   - Uncheck "Send an invitation to this new user?" if you don't want to send an email
   - Click "Create user"

1. **Set Permanent Password**:

   - Select the created user
   - Click "Actions" → "Reset password"
   - Set a permanent password
   - The user status should change to "Confirmed"

#### Method 2: Using AWS CLI

1. **Create the user**:

    ```bash
    aws cognito-idp admin-create-user \
        --user-pool-id <USER_POOL_ID> \
        --username "your-username" \
        --user-attributes Name=email,Value=your-email@example.com \
        --temporary-password "TempPassword123!" \
        --message-action SUPPRESS
    ```

1. **Set permanent password**:

    ```bash
    aws cognito-idp admin-set-user-password \
        --user-pool-id <USER_POOL_ID> \
        --username "your-username" \
        --password "YourPermanentPassword123!" \
        --permanent
    ```

1. **Confirm the user** (if needed):

    ```bash
    aws cognito-idp admin-confirm-sign-up \
        --user-pool-id <USER_POOL_ID> \
        --username "your-username"
    ```

#### Method 3: Using Python Script

Create a script to automate user creation:

```python
import boto3
import json
import os
from typing import Dict, Any


def create_cognito_user(
    user_pool_id: str,
    username: str,
    email: str,
    temporary_password: str,
    permanent_password: str
) -> Dict[str, Any]:
    """
    Create a Cognito user with permanent password.
    
    Args:
        user_pool_id: The Cognito User Pool ID
        username: Username for the new user
        email: Email address for the user
        temporary_password: Temporary password for initial creation
        permanent_password: Permanent password to set
        
    Returns:
        Dictionary containing user creation results
    """
    client = boto3.client("cognito-idp")
    
    try:
        # Create user
        create_response = client.admin_create_user(
            UserPoolId=user_pool_id,
            Username=username,
            UserAttributes=[
                {"Name": "email", "Value": email},
                {"Name": "email_verified", "Value": "true"}
            ],
            TemporaryPassword=temporary_password,
            MessageAction="SUPPRESS"
        )
        
        # Set permanent password
        client.admin_set_user_password(
            UserPoolId=user_pool_id,
            Username=username,
            Password=permanent_password,
            Permanent=True
        )
        
        # Confirm user
        client.admin_confirm_sign_up(
            UserPoolId=user_pool_id,
            Username=username
        )
        
        return {
            "success": True,
            "username": username,
            "user_status": "CONFIRMED"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


if __name__ == "__main__":
    # Replace with your actual User Pool ID
    USER_POOL_ID = "us-east-1_XXXXXXXXX"
    
    result = create_cognito_user(
        user_pool_id=USER_POOL_ID,
        username="testuser",
        email="test@example.com",
        temporary_password="TempPass123!",
        permanent_password="MySecurePassword123!"
    )
    
    print(json.dumps(result, indent=2))
```

### Testing Authentication

Once you have created a user, you can test authentication:

#### Using AWS CLI

```bash
aws cognito-idp initiate-auth \
    --auth-flow USER_PASSWORD_AUTH \
    --client-id <USER_POOL_CLIENT_ID> \
    --auth-parameters USERNAME=your-username,PASSWORD=your-password
```

#### Using Python

```python
import boto3

def authenticate_user(
    client_id: str, 
    username: str, 
    password: str
) -> Dict[str, Any]:
    """
    Authenticate a user with Cognito.
    
    Args:
        client_id: Cognito User Pool Client ID
        username: Username to authenticate
        password: User's password
        
    Returns:
        Authentication result containing tokens
    """
    client = boto3.client("cognito-idp")
    
    try:
        response = client.initiate_auth(
            AuthFlow="USER_PASSWORD_AUTH",
            ClientId=client_id,
            AuthParameters={
                "USERNAME": username,
                "PASSWORD": password
            }
        )
        
        return {
            "success": True,
            "access_token": response["AuthenticationResult"]["AccessToken"],
            "id_token": response["AuthenticationResult"]["IdToken"],
            "refresh_token": response["AuthenticationResult"]["RefreshToken"]
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

# Test authentication
result = authenticate_user(
    client_id="your-client-id",
    username="testuser", 
    password="MySecurePassword123!"
)
```

### Using Tokens in API Calls

Your API `access_token` will be a base64-encoded string consisting of your username and password concatenated with a colon, like this:

```bash
echo -n "your-username:your-password" | base64
```

Once authenticated, use the `access_token` in your API calls:

```bash
curl -X GET "https://your-subdomain.your-domain.com/assets" \
     -H "x-your-auth-header: YOUR_ACCESS_TOKEN"
```

Or in Python:

```python
import requests

headers = {
    "x-your-auth-header": access_token,  # Replace with your actual access token
    "Content-Type": "application/json"
}

response = requests.get(
    "https://your-subdomain.your-domain.com/assets",
    headers=headers
)
```

### Running Tests

```bash
# Run all tests
poetry run pytest

# Run tests with coverage
poetry run pytest --cov=src

# Run linting and formatting
nox
```

### Code Quality

The project uses several tools for code quality:

- `black` for code formatting
- `isort` for import sorting
- `flake8` for linting

Run all quality checks:

```bash
nox -s test_and_lint
```

## Architecture

The application follows a serverless architecture:

- **Frontend**: (Currently not implemented, but could be a React/Vue app hosted on S3)
- **Backend**: Python FastAPI application running on AWS Lambda
- **Storage**: S3 for asset files, DynamoDB for metadata
- **API**: API Gateway for HTTP endpoints
- **Infrastructure**: AWS CDK for deployment automation

## API Endpoints

Once deployed, the API provides the following endpoints:

- `POST /assets/initiate-upload`
  - Initiates the upload process for a new asset by generating a presigned S3 URL and storing initial metadata in DynamoDB.
- `GET /assets`
  - Lists assets owned by the authenticated user with optional filtering by tags and asset types, supporting pagination.
- `GET /assets/{asset_id}`
  - Retrieves detailed metadata and a presigned download URL for a specific asset by its UUID.
- `PUT /assets/{asset_id}`
  - Updates metadata (description, tags, asset type) for an existing asset owned by the authenticated user.
- `DELETE /assets/{asset_id}`
  - Permanently deletes an asset and its associated file from both DynamoDB and S3 storage.

All endpoints require authentication via the `x-cck-username-password` header containing base64-encoded credentials and are protected by source IP verification.

## License

This project is licensed under the terms specified in [LICENSE](LICENSE).

## Cleanup

To remove all AWS resources:

```bash
cdk destroy
```

**Warning**: This will permanently delete all stored assets and metadata.
