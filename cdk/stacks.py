# Standard Library
from typing import Optional, List

# Third Party
from aws_cdk import (
    Stack,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_apigatewayv2 as apigwv2,
    aws_apigatewayv2_integrations as apigwv2_integrations,
    aws_apigatewayv2_authorizers as apigwv2_authorizers,
    aws_certificatemanager as acm,
    aws_route53 as route53,
    aws_route53_targets as targets,
    aws_s3 as s3,
    aws_dynamodb as dynamodb,
    Duration,
    CfnOutput,
)
from constructs import Construct

# Local Modules
from cdk.custom_constructs.lambda_function import CustomLambdaFromDockerImage
from cdk.custom_constructs.http_api import CustomHttpApiGateway
from cdk.custom_constructs.http_lambda_authorizer import (
    CustomHttpLambdaAuthorizer,
)
from cdk.custom_constructs.s3_bucket import CustomS3Bucket, CustomCorsRule
from cdk.custom_constructs.dynamodb_table import CustomDynamoDBTable


class CartographersCloudKitStack(Stack):
    def __init__(
        self, scope: Construct, construct_id: str, stack_suffix: str, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # region Stack Suffix and Subdomain Configuration
        self.stack_suffix = (stack_suffix if stack_suffix else "").lower()
        self.base_domain_name = "thatsmidnight.com"
        self.subdomain_part = "cartogphers-cloud-kit"
        self.full_domain_name = (
            f"{self.subdomain_part}{self.stack_suffix}.{self.base_domain_name}"
        )
        self.api_prefix = self.node.try_get_context("api_prefix") or "/api/v1"
        # endregion

        # region S3 Bucket for Static Assets
        # Create CORS rules for the S3 bucket
        asset_bucket_cors_rules = [
            self.create_cors_rule(
                construct_id="AssetBucketCorsRule",
                allowed_methods=[
                    s3.HttpMethods.GET,
                    s3.HttpMethods.PUT,
                    s3.HttpMethods.POST,
                    s3.HttpMethods.HEAD,
                ],
                allowed_origins=["*"],
                allowed_headers=["*"],
                max_age=3000,
            )
        ]

        # Create a custom S3 bucket for static assets
        asset_bucket = self.create_s3_bucket(
            construct_id="CartographersCloudKitAssetBucket",
            name="cartographers-cloud-kit-assets",
            versioned=True,
            cors_rules=asset_bucket_cors_rules,
        )

        # Output asset bucket name
        CfnOutput(
            self,
            "AssetBucketNameOutput",
            value=asset_bucket.bucket_name,
            description=(
                "S3 bucket name for Cartographers Cloud Kit static assets"
            ),
            export_name=(
                f"cartographers-cloud-kit-asset-bucket-name{self.stack_suffix}"
            ),
        )
        # endregion

        # region DynamoDB Table for Metadata
        # Create a DynamoDB table for storing metadata
        metadata_table = self.create_dynamodb_table(
            construct_id="AssetMetadataTable",
            name="cartographers-cloud-kit-metadata",
            partition_key_name="asset_id",
            partition_key_type=dynamodb.AttributeType.STRING,
        )

        # Output metadata table name
        CfnOutput(
            self,
            "MetadataTableNameOutput",
            value=metadata_table.table_name,
            description=(
                "DynamoDB table name for Cartographers Cloud Kit metadata"
            ),
            export_name=(
                f"cartographers-cloud-kit-metadata-table-name{self.stack_suffix}"
            ),
        )
        # endregion

        # region Lambda Functions
        # Backend Lambda Function
        taskmaster_backend_lambda = self.create_lambda_function(
            construct_id="CartographersCloudKitLambda",
            src_folder_path="cck-api-backend",
            environment={
                "API_PREFIX": self.api_prefix,
            },
            memory_size=512,
            timeout=Duration.seconds(30),
            description="Cartographers Cloud Kit backend Lambda function",
        )
        # endregion

        # region HTTP API Gateway
        # Create a custom HTTP API Gateway
        cartographer_cloud_kit_api = CustomHttpApiGateway(
            scope=self,
            id="CartographersCloudKitHttpApi",
            name="cartographers-cloud-kit-api",
            stack_suffix=self.stack_suffix,
            allow_methods=[apigwv2.CorsHttpMethod.ANY],
            allow_headers=["Content-Type", "Authorization", "*"],
            max_age=Duration.days(1),
        ).http_api

        # TODO: Create an authorizer for the HTTP API

        # Create Lambda integration for the API
        taskmaster_integration = apigwv2_integrations.HttpLambdaIntegration(
            "TaskmasterIntegration", handler=taskmaster_backend_lambda
        )

        # Create proxy route for the API
        cartographer_cloud_kit_api.add_routes(
            path="/".join([self.api_prefix, "{proxy+}"]),
            methods=[apigwv2.HttpMethod.ANY],
            integration=taskmaster_integration,
        )
        # endregion

        # region Custom Domain Setup for API Gateway
        # 1. Look up existing hosted zone for "thatsmidnight.com"
        hosted_zone = route53.HostedZone.from_lookup(
            self,
            "CartographersCloudKitHostedZone",
            domain_name=self.base_domain_name,
        )

        # 2. Create an ACM certificate for subdomain with DNS validation
        api_certificate = acm.Certificate(
            self,
            "ApiCertificate",
            domain_name=self.full_domain_name,
            validation=acm.CertificateValidation.from_dns(hosted_zone),
        )

        # 3. Create the API Gateway Custom Domain Name resource
        apigw_custom_domain = apigwv2.DomainName(
            self,
            "ApiCustomDomain",
            domain_name=self.full_domain_name,
            certificate=api_certificate,
        )

        # 4. Map HTTP API to this custom domain
        default_stage = cartographer_cloud_kit_api.default_stage
        if not default_stage:
            raise ValueError(
                "Default stage could not be found for API mapping. Ensure API has a default stage or specify one."
            )

        _ = apigwv2.ApiMapping(
            self,
            "ApiMapping",
            api=cartographer_cloud_kit_api,
            domain_name=apigw_custom_domain,
            stage=default_stage,  # Use the actual default stage object
        )

        # 5. Create the Route 53 Alias Record pointing to the API Gateway custom domain
        route53.ARecord(
            self,
            "ApiAliasRecord",
            zone=hosted_zone,
            record_name=f"{self.subdomain_part}{self.stack_suffix}",  # e.g., "arcane-scribe" or "arcane-scribe-dev"
            target=route53.RecordTarget.from_alias(
                targets.ApiGatewayv2DomainProperties(
                    regional_domain_name=apigw_custom_domain.regional_domain_name,
                    regional_hosted_zone_id=apigw_custom_domain.regional_hosted_zone_id,
                )
            ),
        )

        # 6. Output the custom API URL
        CfnOutput(
            self,
            "CustomApiUrlOutput",
            value=f"https://{self.full_domain_name}",
            description="Custom API URL for Cartographers Cloud Kit",
            export_name=(
                f"cartographers-cloud-kit-custom-api-url{self.stack_suffix}"
            ),
        )
        # endregion

    def create_lambda_function(
        self,
        construct_id: str,
        src_folder_path: str,
        environment: Optional[dict] = None,
        memory_size: Optional[int] = 128,
        timeout: Optional[Duration] = Duration.seconds(10),
        initial_policy: Optional[List[iam.PolicyStatement]] = None,
        role: Optional[iam.IRole] = None,
        description: Optional[str] = None,
    ) -> lambda_.Function:
        """Helper method to create a Lambda function.

        Parameters
        ----------
        construct_id : str
            The ID of the construct.
        src_folder_path : str
            The path to the source folder for the Lambda function code.
        environment : Optional[dict], optional
            Environment variables for the Lambda function, by default None
        memory_size : Optional[int], optional
            Memory size for the Lambda function, by default 128
        timeout : Optional[Duration], optional
            Timeout for the Lambda function, by default Duration.seconds(10)
        initial_policy : Optional[List[iam.PolicyStatement]], optional
            Initial IAM policies to attach to the Lambda function, by default None
        role : Optional[iam.IRole], optional
            IAM role to attach to the Lambda function, by default None
        description : Optional[str], optional
            Description for the Lambda function, by default None

        Returns
        -------
        lambda_.Function
            The created Lambda function instance.
        """
        custom_lambda = CustomLambdaFromDockerImage(
            scope=self,
            id=construct_id,
            src_folder_path=src_folder_path,
            stack_suffix=self.stack_suffix,
            environment=environment,
            memory_size=memory_size,
            timeout=timeout,
            initial_policy=initial_policy or [],
            role=role,
            description=description,
        )
        return custom_lambda.function

    def create_http_lambda_authorizer(
        self,
        construct_id: str,
        name: str,
        authorizer_function: lambda_.IFunction,
        response_types: Optional[
            List[apigwv2_authorizers.HttpLambdaResponseType]
        ] = None,
        identity_source: Optional[List[str]] = None,
        results_cache_ttl: Optional[Duration] = Duration.minutes(60),
    ) -> apigwv2_authorizers.HttpLambdaAuthorizer:
        """Helper method to create an HTTP Lambda Authorizer.

        Parameters
        ----------
        construct_id : str
            The ID of the construct.
        name : str
            The name of the authorizer.
        authorizer_function : lambda_.IFunction
            The Lambda function to be used as the authorizer.
        response_types : Optional[List[apigwv2_authorizers.HttpLambdaResponseType]], optional
            List of response types for the authorizer, by default None
        identity_source : Optional[List[str]], optional
            List of identity sources for the authorizer, by default None
        Returns
        -------
        apigwv2_authorizers.HttpLambdaAuthorizer
            The created HTTP Lambda Authorizer instance.
        """
        custom_http_lambda_authorizer = CustomHttpLambdaAuthorizer(
            scope=self,
            id=construct_id,
            name=name,
            authorizer_function=authorizer_function,
            stack_suffix=self.stack_suffix,
            response_types=response_types,
            identity_source=identity_source,
            results_cache_ttl=results_cache_ttl,
        )
        return custom_http_lambda_authorizer.authorizer

    def create_s3_bucket(
        self,
        construct_id: str,
        name: str,
        versioned: Optional[bool] = False,
        cors_rules: Optional[List[s3.CorsRule]] = None,
    ) -> s3.Bucket:
        """Helper method to create an S3 bucket with a specific name and versioning.

        Parameters
        ----------
        construct_id : str
            The ID of the construct.
        name : str
            The name of the S3 bucket.
        versioned : Optional[bool], optional
            Whether to enable versioning on the bucket, by default False
        cors_rules : Optional[List[s3.CorsRule]], optional
            List of CORS rules for the S3 bucket, by default None

        Returns
        -------
        s3.Bucket
            The created S3 bucket instance.
        """
        custom_s3_bucket = CustomS3Bucket(
            scope=self,
            id=construct_id,
            name=name,
            stack_suffix=self.stack_suffix,
            versioned=versioned,
            cors_rules=cors_rules
        )
        return custom_s3_bucket.bucket

    def create_cors_rule(
        self,
        construct_id: str,
        allowed_origins: List[str],
        allowed_methods: Optional[List[s3.HttpMethods]] = None,
        allowed_headers: Optional[List[str]] = None,
        max_age: Optional[int] = None,
    ) -> s3.CorsRule:
        """Helper method to create a CORS rule for S3 buckets.

        Parameters
        ----------
        construct_id : str
            The ID of the construct.
        allowed_origins : List[str]
            List of allowed origins for CORS.
        allowed_methods : Optional[List[s3.HttpMethods]], optional
            List of allowed HTTP methods, by default None
        allowed_headers : Optional[List[str]], optional
            List of allowed headers, by default None
        max_age : Optional[int], optional
            Maximum age in seconds for the CORS preflight response, by default
            None

        Returns
        -------
        s3.CorsRule
            The created CORS rule instance.
        """
        custom_cors_rule = CustomCorsRule(
            scope=self,
            id=construct_id,
            allowed_origins=allowed_origins,
            allowed_methods=allowed_methods or [s3.HttpMethods.GET],
            allowed_headers=allowed_headers or ["*"],
            max_age=max_age,
        )

        return custom_cors_rule.rule

    def create_dynamodb_table(
        self,
        construct_id: str,
        name: str,
        partition_key_name: str,
        partition_key_type: Optional[dynamodb.AttributeType] = None,
        sort_key_name: Optional[str] = None,
        sort_key_type: Optional[dynamodb.AttributeType] = None,
        time_to_live_attribute: Optional[str] = None,
    ) -> dynamodb.Table:
        """Helper method to create a DynamoDB table with a specific name and partition key.

        Parameters
        ----------
        construct_id : str
            The ID of the construct.
        name : str
            The name of the DynamoDB table.
        partition_key_name : str
            The name of the partition key for the table.
        partition_key_type : Optional[dynamodb.AttributeType], optional
            The type of the partition key, by default dynamodb.AttributeType.STRING
        sort_key_name : Optional[str], optional
            The name of the sort key for the table, by default None
        sort_key_type : Optional[dynamodb.AttributeType], optional
            The type of the sort key, by default None
        time_to_live_attribute : Optional[str], optional
            The attribute name for time to live (TTL) settings, by default None

        Returns
        -------
        dynamodb.Table
            The created DynamoDB table instance.
        """
        custom_dynamodb_table = CustomDynamoDBTable(
            scope=self,
            id=construct_id,
            name=name,
            partition_key=dynamodb.Attribute(
                name=partition_key_name,
                type=partition_key_type or dynamodb.AttributeType.STRING,
            ),
            sort_key=dynamodb.Attribute(
                name=sort_key_name,
                type=sort_key_type or dynamodb.AttributeType.STRING,
            ) if sort_key_name else None,
            stack_suffix=self.stack_suffix,
            time_to_live_attribute=time_to_live_attribute or "ttl",
        )
        return custom_dynamodb_table.table
