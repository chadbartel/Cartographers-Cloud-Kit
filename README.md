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

## Setup Instructions

### 1. Clone and Install Dependencies

```bash
git clone <repository-url>
cd Cartographers-Cloud-Kit
poetry install
```

### 2. Environment Setup

Create a `.env` file in the project root with your configuration:

```bash
# AWS Configuration
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=123456789012
```

### 3. Deploy Infrastructure

The project uses AWS CDK for infrastructure as code. Deploy the stack:

```bash
# Bootstrap CDK (first time only)
cdk bootstrap

# Deploy the infrastructure
cdk deploy
```

This will create:

- S3 bucket for asset storage
- DynamoDB table for metadata
- Lambda functions for API endpoints
- API Gateway for HTTP endpoints
- CloudFront distribution (if domain configured)
- IAM roles and policies

### 4. Configure Domain (Optional)

If you have a Route53 hosted zone, the CDK will automatically:

- Create SSL certificate via ACM
- Configure CloudFront with custom domain
- Set up DNS records

## Development

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

## Configuration

Key configuration options in [cdk.json](cdk.json):

```json
{
  "app": "python app.py",
  "context": {
    "domain_name": "your-domain.com",
    "subdomain_name": "your-subdomain"
  }
}
```

## License

This project is licensed under the terms specified in [LICENSE](LICENSE).

## Cleanup

To remove all AWS resources:

```bash
cdk destroy
```

**Warning**: This will permanently delete all stored assets and metadata.
