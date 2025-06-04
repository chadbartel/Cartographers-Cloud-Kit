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


class AutomatedTaskmasterStack(Stack):
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

        # region Lambda Functions
        # Backend Lambda Function
        taskmaster_backend_lambda = self.create_lambda_function(
            construct_id="TaskmasterBackendLambda",
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
        taskmaster_api = CustomHttpApiGateway(
            scope=self,
            id="TaskmasterHttpApi",
            name="automated-taskmaster-api",
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
        taskmaster_api.add_routes(
            path="/".join([self.api_prefix, "{proxy+}"]),
            methods=[apigwv2.HttpMethod.ANY],
            integration=taskmaster_integration,
        )
        # endregion

        # region Custom Domain Setup for API Gateway
        # 1. Look up existing hosted zone for "thatsmidnight.com"
        hosted_zone = route53.HostedZone.from_lookup(
            self, "ArcaneScribeHostedZone", domain_name=self.base_domain_name
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
        default_stage = taskmaster_api.default_stage
        if not default_stage:
            raise ValueError(
                "Default stage could not be found for API mapping. Ensure API has a default stage or specify one."
            )

        _ = apigwv2.ApiMapping(
            self,
            "ApiMapping",
            api=taskmaster_api,
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
        # endregion

        # region Outputs
        CfnOutput(
            self,
            "CustomApiUrlOutput",
            value=f"https://{self.full_domain_name}",
            description="Custom API URL for Cartographers Cloud Kit",
            export_name=(
                f"automated-taskmaster-custom-api-url{self.stack_suffix}"
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
