# Standard Library
from typing import Optional, List

# Third Party
from aws_cdk import aws_s3 as s3, RemovalPolicy, Duration
from constructs import Construct


class CustomS3Bucket(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        name: str,
        stack_suffix: Optional[str] = "",
        versioned: Optional[bool] = False,
        cors_rules: Optional[List[s3.CorsRule]] = None,
        lifecycle_rules: Optional[List[s3.LifecycleRule]] = None,
        block_public_access: s3.BlockPublicAccess = s3.BlockPublicAccess.BLOCK_ALL,
        event_bridge_enabled: Optional[bool] = False,
        **kwargs,
    ) -> None:
        """Custom S3 Bucket Construct for AWS CDK.

        Parameters
        ----------
        scope : Construct
            The scope in which this construct is defined.
        id : str
            The ID of the construct.
        name : str
            The name of the S3 bucket.
        stack_suffix : Optional[str], optional
            Suffix to append to the S3 bucket name, by default ""
        versioned : Optional[bool], optional
            Whether the S3 bucket should be versioned, by default False
        cors_rules : Optional[List[s3.CorsRule]], optional
            CORS rules for the S3 bucket, by default None
        lifecycle_rules : Optional[List[s3.LifecycleRule]], optional
            Lifecycle rules for the S3 bucket, by default None
        block_public_access : s3.BlockPublicAccess, optional
            Block public access settings for the S3 bucket, by default s3.BlockPublicAccess.BLOCK_ALL
        event_bridge_enabled : Optional[bool], optional
            Whether to enable EventBridge for the S3 bucket, by default False
        """
        super().__init__(scope, id, **kwargs)

        # Append stack suffix to name if provided
        if stack_suffix:
            name = f"{name}{stack_suffix}"

        # Truncate name to 63 characters if it exceeds the limit
        if len(name) > 63:
            name = name[:63]

        # Set default lifecycle rules if not provided
        if lifecycle_rules is None:
            lifecycle_rules = [
                # Intelligent Tiering rule
                s3.LifecycleRule(
                    id="DefaultIntelligentTiering",
                    enabled=True,
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.INTELLIGENT_TIERING,
                            transition_after=Duration.days(0),
                        )
                    ],
                ),
                # Abort incomplete multipart uploads rule
                s3.LifecycleRule(
                    id="AbortIncompleteMultipartUploads",
                    enabled=True,
                    abort_incomplete_multipart_upload_after=Duration.days(7),
                ),
            ]

        # Create the S3 bucket
        self.bucket = s3.Bucket(
            self,
            "DefaultBucket",
            bucket_name=name,
            cors=cors_rules,
            versioned=versioned,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=block_public_access,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            lifecycle_rules=lifecycle_rules,
            event_bridge_enabled=event_bridge_enabled,
        )
