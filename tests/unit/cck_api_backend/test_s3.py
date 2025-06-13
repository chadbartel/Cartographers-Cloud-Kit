# Standard Library
import os
import tempfile

# Third Party
import boto3
import pytest
from moto import mock_aws

# Local Modules
from api_backend.aws.s3 import S3Client


@pytest.fixture
def s3_setup():
    """Setup S3 mock with bucket and test data."""
    with mock_aws():
        # Create S3 client and bucket
        s3_client = boto3.client("s3", region_name="us-east-1")
        bucket_name = "test-bucket"
        s3_client.create_bucket(Bucket=bucket_name)

        # Create some test objects
        s3_client.put_object(
            Bucket=bucket_name,
            Key="test/file1.txt",
            Body=b"Test content 1",
        )
        s3_client.put_object(
            Bucket=bucket_name,
            Key="test/file2.txt",
            Body=b"Test content 2",
        )
        s3_client.put_object(
            Bucket=bucket_name,
            Key="uploads/image.jpg",
            Body=b"Binary image data",
        )

        yield {
            "bucket_name": bucket_name,
            "s3_client": s3_client,
        }


class TestS3ClientInit:
    """Test cases for S3Client initialization."""

    @mock_aws
    def test_s3_client_init_success_with_region(self):
        """Test successful S3Client initialization with region."""
        # Arrange
        bucket_name = "test-bucket"
        region_name = "us-west-2"

        # Act
        s3_client = S3Client(bucket_name=bucket_name, region_name=region_name)

        # Assert
        assert s3_client.bucket_name == bucket_name
        assert s3_client._client is not None

    @mock_aws
    def test_s3_client_init_success_without_region(self):
        """Test successful S3Client initialization without region."""
        # Arrange
        bucket_name = "test-bucket"

        # Act
        s3_client = S3Client(bucket_name=bucket_name)

        # Assert
        assert s3_client.bucket_name == bucket_name
        assert s3_client._client is not None

    def test_s3_client_init_exception(self, monkeypatch):
        """Test S3Client initialization exception handling."""
        # Arrange
        bucket_name = "test-bucket"

        def mock_boto3_client(*args, **kwargs):
            raise Exception("Failed to create client")

        monkeypatch.setattr(
            "api_backend.aws.s3.boto3.client", mock_boto3_client
        )

        # Act & Assert
        with pytest.raises(Exception, match="Failed to create client"):
            S3Client(bucket_name=bucket_name)


class TestS3ClientUploadFile:
    """Test cases for upload_file method."""

    def test_upload_file_success_default_bucket(self, s3_setup):
        """Test successful file upload using default bucket."""
        # Arrange
        bucket_name = s3_setup["bucket_name"]
        s3_client = S3Client(bucket_name=bucket_name)

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_file:
            temp_file.write("Test file content")
            temp_file_path = temp_file.name

        object_key = "uploads/test_upload.txt"

        try:
            # Act
            result = s3_client.upload_file(temp_file_path, object_key)

            # Assert
            assert result is True

            # Verify file was uploaded
            s3_boto_client = s3_setup["s3_client"]
            response = s3_boto_client.get_object(
                Bucket=bucket_name, Key=object_key
            )
            assert response["Body"].read().decode() == "Test file content"
        finally:
            # Cleanup
            os.unlink(temp_file_path)

    def test_upload_file_success_custom_bucket(self, s3_setup):
        """Test successful file upload using custom bucket."""
        # Arrange
        s3_client = S3Client(bucket_name="original-bucket")
        s3_boto_client = s3_setup["s3_client"]
        custom_bucket = "custom-bucket"
        s3_boto_client.create_bucket(Bucket=custom_bucket)

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_file:
            temp_file.write("Custom bucket content")
            temp_file_path = temp_file.name

        object_key = "uploads/custom_upload.txt"
        extra_args = {"ServerSideEncryption": "AES256"}

        try:
            # Act
            result = s3_client.upload_file(
                temp_file_path,
                object_key,
                bucket_name=custom_bucket,
                extra_args=extra_args,
            )

            # Assert
            assert result is True

            # Verify file was uploaded to custom bucket
            response = s3_boto_client.get_object(
                Bucket=custom_bucket, Key=object_key
            )
            assert response["Body"].read().decode() == "Custom bucket content"
        finally:
            # Cleanup
            os.unlink(temp_file_path)

    def test_upload_file_nonexistent_file(self, s3_setup):
        """Test file upload with non-existent file."""
        # Arrange
        bucket_name = s3_setup["bucket_name"]
        s3_client = S3Client(bucket_name=bucket_name)
        file_path = "/nonexistent/file.txt"
        object_key = "uploads/nonexistent.txt"

        # Act
        result = s3_client.upload_file(file_path, object_key)

        # Assert
        assert result is False

    def test_upload_file_nonexistent_bucket(self, s3_setup):
        """Test file upload to non-existent bucket."""
        # Arrange
        s3_client = S3Client(bucket_name="nonexistent-bucket")

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_file:
            temp_file.write("Test content")
            temp_file_path = temp_file.name

        object_key = "test.txt"

        try:
            # Act
            result = s3_client.upload_file(temp_file_path, object_key)

            # Assert
            assert result is False
        finally:
            # Cleanup
            os.unlink(temp_file_path)


class TestS3ClientGetFile:
    """Test cases for get_file method."""

    def test_get_file_success_default_bucket(self, s3_setup):
        """Test successful file download using default bucket."""
        # Arrange
        bucket_name = s3_setup["bucket_name"]
        s3_client = S3Client(bucket_name=bucket_name)
        object_key = "test/file1.txt"

        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            download_path = temp_file.name

        try:
            # Act
            result = s3_client.get_file(object_key, download_path)

            # Assert
            assert result is True

            # Verify file was downloaded correctly
            with open(download_path, "rb") as f:
                assert f.read() == b"Test content 1"
        finally:
            # Cleanup
            os.unlink(download_path)

    def test_get_file_success_custom_bucket(self, s3_setup):
        """Test successful file download using custom bucket."""
        # Arrange
        s3_client = S3Client(bucket_name="original-bucket")
        s3_boto_client = s3_setup["s3_client"]
        custom_bucket = "custom-bucket"
        s3_boto_client.create_bucket(Bucket=custom_bucket)

        object_key = "custom/file.txt"
        s3_boto_client.put_object(
            Bucket=custom_bucket,
            Key=object_key,
            Body=b"Custom bucket file content",
        )

        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            download_path = temp_file.name

        try:
            # Act
            result = s3_client.get_file(
                object_key, download_path, bucket_name=custom_bucket
            )

            # Assert
            assert result is True

            # Verify file was downloaded correctly
            with open(download_path, "rb") as f:
                assert f.read() == b"Custom bucket file content"
        finally:
            # Cleanup
            os.unlink(download_path)

    def test_get_file_nonexistent_object(self, s3_setup):
        """Test file download with non-existent object."""
        # Arrange
        bucket_name = s3_setup["bucket_name"]
        s3_client = S3Client(bucket_name=bucket_name)
        object_key = "nonexistent/file.txt"

        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            download_path = temp_file.name

        try:
            # Act
            result = s3_client.get_file(object_key, download_path)

            # Assert
            assert result is False
        finally:
            # Cleanup
            if os.path.exists(download_path):
                os.unlink(download_path)

    def test_get_file_nonexistent_bucket(self, s3_setup):
        """Test file download from non-existent bucket."""
        # Arrange
        s3_client = S3Client(bucket_name="nonexistent-bucket")
        object_key = "test.txt"

        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            download_path = temp_file.name

        try:
            # Act
            result = s3_client.get_file(object_key, download_path)

            # Assert
            assert result is False
        finally:
            # Cleanup
            if os.path.exists(download_path):
                os.unlink(download_path)


class TestS3ClientGetObjectContent:
    """Test cases for get_object_content method."""

    def test_get_object_content_success_default_bucket(self, s3_setup):
        """Test successful object content retrieval using default bucket."""
        # Arrange
        bucket_name = s3_setup["bucket_name"]
        s3_client = S3Client(bucket_name=bucket_name)
        object_key = "test/file1.txt"

        # Act
        result = s3_client.get_object_content(object_key)

        # Assert
        assert result == b"Test content 1"

    def test_get_object_content_success_custom_bucket(self, s3_setup):
        """Test successful object content retrieval using custom bucket."""
        # Arrange
        s3_client = S3Client(bucket_name="original-bucket")
        s3_boto_client = s3_setup["s3_client"]
        custom_bucket = "custom-bucket"
        s3_boto_client.create_bucket(Bucket=custom_bucket)

        object_key = "custom/content.txt"
        content = b"Custom bucket content"
        s3_boto_client.put_object(
            Bucket=custom_bucket,
            Key=object_key,
            Body=content,
        )

        # Act
        result = s3_client.get_object_content(
            object_key, bucket_name=custom_bucket
        )

        # Assert
        assert result == content

    def test_get_object_content_nonexistent_object(self, s3_setup):
        """Test object content retrieval with non-existent object."""
        # Arrange
        bucket_name = s3_setup["bucket_name"]
        s3_client = S3Client(bucket_name=bucket_name)
        object_key = "nonexistent/file.txt"

        # Act
        result = s3_client.get_object_content(object_key)

        # Assert
        assert result is None

    def test_get_object_content_nonexistent_bucket(self, s3_setup):
        """Test object content retrieval from non-existent bucket."""
        # Arrange
        s3_client = S3Client(bucket_name="nonexistent-bucket")
        object_key = "test.txt"

        # Act
        result = s3_client.get_object_content(object_key)

        # Assert
        assert result is None


class TestS3ClientListObjects:
    """Test cases for list_objects method."""

    def test_list_objects_success_no_prefix(self, s3_setup):
        """Test successful object listing without prefix."""
        # Arrange
        bucket_name = s3_setup["bucket_name"]
        s3_client = S3Client(bucket_name=bucket_name)

        # Act
        result = s3_client.list_objects()

        # Assert
        assert (
            len(result) == 3
        )  # test/file1.txt, test/file2.txt, uploads/image.jpg
        keys = {obj["Key"] for obj in result}
        assert "test/file1.txt" in keys
        assert "test/file2.txt" in keys
        assert "uploads/image.jpg" in keys

        # Check structure of returned objects
        for obj in result:
            assert "Key" in obj
            assert "Size" in obj
            assert "LastModified" in obj
            assert isinstance(obj["Size"], int)
            assert isinstance(obj["LastModified"], str)

    def test_list_objects_success_with_prefix(self, s3_setup):
        """Test successful object listing with prefix."""
        # Arrange
        bucket_name = s3_setup["bucket_name"]
        s3_client = S3Client(bucket_name=bucket_name)
        prefix = "test/"

        # Act
        result = s3_client.list_objects(prefix=prefix)

        # Assert
        assert len(result) == 2  # Only test/file1.txt and test/file2.txt
        keys = {obj["Key"] for obj in result}
        assert "test/file1.txt" in keys
        assert "test/file2.txt" in keys
        assert "uploads/image.jpg" not in keys

    def test_list_objects_success_with_max_keys(self, s3_setup):
        """Test successful object listing with max_keys limit."""
        # Arrange
        bucket_name = s3_setup["bucket_name"]
        s3_client = S3Client(bucket_name=bucket_name)
        max_keys = 2

        # Act
        result = s3_client.list_objects(max_keys=max_keys)

        # Assert
        assert len(result) <= max_keys

    def test_list_objects_success_custom_bucket(self, s3_setup):
        """Test successful object listing using custom bucket."""
        # Arrange
        s3_client = S3Client(bucket_name="original-bucket")
        s3_boto_client = s3_setup["s3_client"]
        custom_bucket = "custom-bucket"
        s3_boto_client.create_bucket(Bucket=custom_bucket)

        # Add objects to custom bucket
        s3_boto_client.put_object(
            Bucket=custom_bucket,
            Key="custom/file1.txt",
            Body=b"Custom content 1",
        )
        s3_boto_client.put_object(
            Bucket=custom_bucket,
            Key="custom/file2.txt",
            Body=b"Custom content 2",
        )

        # Act
        result = s3_client.list_objects(bucket_name=custom_bucket)

        # Assert
        assert len(result) == 2
        keys = {obj["Key"] for obj in result}
        assert "custom/file1.txt" in keys
        assert "custom/file2.txt" in keys

    def test_list_objects_no_contents(self, s3_setup):
        """Test object listing when no objects are found."""
        # Arrange
        s3_boto_client = s3_setup["s3_client"]
        empty_bucket = "empty-bucket"
        s3_boto_client.create_bucket(Bucket=empty_bucket)
        s3_client = S3Client(bucket_name=empty_bucket)

        # Act
        result = s3_client.list_objects()

        # Assert
        assert result == []

    def test_list_objects_nonexistent_bucket(self, s3_setup):
        """Test object listing with non-existent bucket."""
        # Arrange
        s3_client = S3Client(bucket_name="nonexistent-bucket")

        # Act
        result = s3_client.list_objects()

        # Assert
        assert result == []

    def test_list_objects_empty_prefix_vs_none(self, s3_setup):
        """Test difference between empty string prefix and None prefix."""
        # Arrange
        bucket_name = s3_setup["bucket_name"]
        s3_client = S3Client(bucket_name=bucket_name)

        # Act
        result_empty_prefix = s3_client.list_objects(prefix="")
        result_none_prefix = s3_client.list_objects(prefix=None)

        # Assert
        # Both should return the same results since empty string is falsy
        assert len(result_empty_prefix) == len(result_none_prefix)
        assert len(result_empty_prefix) == 3


class TestS3ClientDeleteObject:
    """Test cases for delete_object method."""

    def test_delete_object_success_default_bucket(self, s3_setup):
        """Test successful object deletion using default bucket."""
        # Arrange
        bucket_name = s3_setup["bucket_name"]
        s3_client = S3Client(bucket_name=bucket_name)
        object_key = "test/file1.txt"

        # Verify object exists before deletion
        assert s3_client.object_exists(object_key) is True

        # Act
        result = s3_client.delete_object(object_key)

        # Assert
        assert result is True
        assert s3_client.object_exists(object_key) is False

    def test_delete_object_success_custom_bucket(self, s3_setup):
        """Test successful object deletion using custom bucket."""
        # Arrange
        s3_client = S3Client(bucket_name="original-bucket")
        s3_boto_client = s3_setup["s3_client"]
        custom_bucket = "custom-bucket"
        s3_boto_client.create_bucket(Bucket=custom_bucket)

        object_key = "custom/delete_me.txt"
        s3_boto_client.put_object(
            Bucket=custom_bucket,
            Key=object_key,
            Body=b"Content to be deleted",
        )

        # Verify object exists before deletion
        assert (
            s3_client.object_exists(object_key, bucket_name=custom_bucket)
            is True
        )

        # Act
        result = s3_client.delete_object(object_key, bucket_name=custom_bucket)

        # Assert
        assert result is True
        assert (
            s3_client.object_exists(object_key, bucket_name=custom_bucket)
            is False
        )

    def test_delete_object_nonexistent_object(self, s3_setup):
        """Test object deletion with non-existent object."""
        # Arrange
        bucket_name = s3_setup["bucket_name"]
        s3_client = S3Client(bucket_name=bucket_name)
        object_key = "nonexistent/file.txt"

        # Act
        result = s3_client.delete_object(object_key)

        # Assert
        # S3 delete operations are idempotent, so deleting non-existent object succeeds
        assert result is True

    def test_delete_object_nonexistent_bucket(self, s3_setup):
        """Test object deletion from non-existent bucket."""
        # Arrange
        s3_client = S3Client(bucket_name="nonexistent-bucket")
        object_key = "test.txt"

        # Act
        result = s3_client.delete_object(object_key)

        # Assert
        assert result is False


class TestS3ClientObjectExists:
    """Test cases for object_exists method."""

    def test_object_exists_true_default_bucket(self, s3_setup):
        """Test object exists check returns True using default bucket."""
        # Arrange
        bucket_name = s3_setup["bucket_name"]
        s3_client = S3Client(bucket_name=bucket_name)
        object_key = "test/file1.txt"

        # Act
        result = s3_client.object_exists(object_key)

        # Assert
        assert result is True

    def test_object_exists_true_custom_bucket(self, s3_setup):
        """Test object exists check returns True using custom bucket."""
        # Arrange
        s3_client = S3Client(bucket_name="original-bucket")
        s3_boto_client = s3_setup["s3_client"]
        custom_bucket = "custom-bucket"
        s3_boto_client.create_bucket(Bucket=custom_bucket)

        object_key = "custom/exists.txt"
        s3_boto_client.put_object(
            Bucket=custom_bucket,
            Key=object_key,
            Body=b"I exist!",
        )

        # Act
        result = s3_client.object_exists(object_key, bucket_name=custom_bucket)

        # Assert
        assert result is True

    def test_object_exists_false_nonexistent_object(self, s3_setup):
        """Test object exists check returns False for non-existent object."""
        # Arrange
        bucket_name = s3_setup["bucket_name"]
        s3_client = S3Client(bucket_name=bucket_name)
        object_key = "nonexistent/file.txt"

        # Act
        result = s3_client.object_exists(object_key)

        # Assert
        assert result is False

    def test_object_exists_false_nonexistent_bucket(self, s3_setup):
        """Test object exists check returns False for non-existent bucket."""
        # Arrange
        s3_client = S3Client(bucket_name="nonexistent-bucket")
        object_key = "test.txt"

        # Act
        result = s3_client.object_exists(object_key)

        # Assert
        assert result is False


class TestS3ClientGeneratePresignedUploadUrl:
    """Test cases for generate_presigned_upload_url method."""

    def test_generate_presigned_upload_url_success_default_params(
        self, s3_setup
    ):
        """Test successful presigned upload URL generation with default params."""
        # Arrange
        bucket_name = s3_setup["bucket_name"]
        s3_client = S3Client(bucket_name=bucket_name)
        object_key = "uploads/presigned_upload.txt"

        # Act
        result = s3_client.generate_presigned_upload_url(object_key)

        # Assert
        assert result is not None
        assert isinstance(result, str)
        assert bucket_name in result
        assert object_key in result
        assert "https://" in result

    def test_generate_presigned_upload_url_success_custom_params(
        self, s3_setup
    ):
        """Test successful presigned upload URL generation with custom params."""
        # Arrange
        s3_client = S3Client(bucket_name="original-bucket")
        s3_boto_client = s3_setup["s3_client"]
        custom_bucket = "custom-bucket"
        s3_boto_client.create_bucket(Bucket=custom_bucket)

        object_key = "custom/presigned.txt"
        expiration = 7200

        # Act
        result = s3_client.generate_presigned_upload_url(
            object_key, expiration=expiration, bucket_name=custom_bucket
        )

        # Assert
        assert result is not None
        assert isinstance(result, str)
        assert custom_bucket in result
        assert object_key in result

    def test_generate_presigned_upload_url_nonexistent_bucket(self, s3_setup):
        """Test presigned upload URL generation with non-existent bucket."""
        # Arrange
        s3_client = S3Client(bucket_name="nonexistent-bucket")
        object_key = "test.txt"

        # Act
        result = s3_client.generate_presigned_upload_url(object_key)

        # Assert
        # URL generation doesn't validate bucket existence, so it should succeed
        assert result is not None
        assert isinstance(result, str)


class TestS3ClientGeneratePresignedDownloadUrl:
    """Test cases for generate_presigned_download_url method."""

    def test_generate_presigned_download_url_success_default_params(
        self, s3_setup
    ):
        """Test successful presigned download URL generation with default params."""
        # Arrange
        bucket_name = s3_setup["bucket_name"]
        s3_client = S3Client(bucket_name=bucket_name)
        object_key = "test/file1.txt"

        # Act
        result = s3_client.generate_presigned_download_url(object_key)

        # Assert
        assert result is not None
        assert isinstance(result, str)
        assert bucket_name in result
        assert object_key in result
        assert "https://" in result

    def test_generate_presigned_download_url_success_custom_params(
        self, s3_setup
    ):
        """Test successful presigned download URL generation with custom params."""
        # Arrange
        s3_client = S3Client(bucket_name="original-bucket")
        s3_boto_client = s3_setup["s3_client"]
        custom_bucket = "custom-bucket"
        s3_boto_client.create_bucket(Bucket=custom_bucket)

        object_key = "custom/download.txt"
        s3_boto_client.put_object(
            Bucket=custom_bucket,
            Key=object_key,
            Body=b"Download me!",
        )
        expiration = 900

        # Act
        result = s3_client.generate_presigned_download_url(
            object_key, expiration=expiration, bucket_name=custom_bucket
        )

        # Assert
        assert result is not None
        assert isinstance(result, str)
        assert custom_bucket in result
        assert object_key in result

    def test_generate_presigned_download_url_nonexistent_object(
        self, s3_setup
    ):
        """Test presigned download URL generation for non-existent object."""
        # Arrange
        bucket_name = s3_setup["bucket_name"]
        s3_client = S3Client(bucket_name=bucket_name)
        object_key = "nonexistent/file.txt"

        # Act
        result = s3_client.generate_presigned_download_url(object_key)

        # Assert
        # URL generation doesn't validate object existence, so it should succeed
        assert result is not None
        assert isinstance(result, str)

    def test_generate_presigned_download_url_nonexistent_bucket(
        self, s3_setup
    ):
        """Test presigned download URL generation with non-existent bucket."""
        # Arrange
        s3_client = S3Client(bucket_name="nonexistent-bucket")
        object_key = "test.txt"

        # Act
        result = s3_client.generate_presigned_download_url(object_key)

        # Assert
        # URL generation doesn't validate bucket existence, so it should succeed
        assert result is not None
        assert isinstance(result, str)


class TestS3ClientErrorHandling:
    """Test cases for error handling with mocked failures."""

    def test_generate_presigned_download_url_client_error(
        self, s3_setup, monkeypatch
    ):
        """Test presigned download URL generation with ClientError."""
        # Arrange
        bucket_name = s3_setup["bucket_name"]
        s3_client = S3Client(bucket_name=bucket_name)
        object_key = "test/file1.txt"

        def mock_generate_presigned_url(*args, **kwargs):
            # Third Party
            from botocore.exceptions import ClientError

            raise ClientError(
                error_response={"Error": {"Code": "InvalidRequest"}},
                operation_name="GeneratePresignedUrl",
            )

        monkeypatch.setattr(
            s3_client._client,
            "generate_presigned_url",
            mock_generate_presigned_url,
        )

        # Act
        result = s3_client.generate_presigned_download_url(object_key)

        # Assert
        assert result is None

    def test_generate_presigned_download_url_general_exception(
        self, s3_setup, monkeypatch
    ):
        """Test presigned download URL generation with general exception."""
        # Arrange
        bucket_name = s3_setup["bucket_name"]
        s3_client = S3Client(bucket_name=bucket_name)
        object_key = "test/file1.txt"

        def mock_generate_presigned_url(*args, **kwargs):
            raise Exception("Configuration error")

        monkeypatch.setattr(
            s3_client._client,
            "generate_presigned_url",
            mock_generate_presigned_url,
        )

        # Act
        result = s3_client.generate_presigned_download_url(object_key)

        # Assert
        assert result is None

    def test_generate_presigned_upload_url_client_error(
        self, s3_setup, monkeypatch
    ):
        """Test presigned upload URL generation with ClientError."""
        # Arrange
        bucket_name = s3_setup["bucket_name"]
        s3_client = S3Client(bucket_name=bucket_name)
        object_key = "uploads/new_file.txt"

        def mock_generate_presigned_url(*args, **kwargs):
            # Third Party
            from botocore.exceptions import ClientError

            raise ClientError(
                error_response={"Error": {"Code": "InvalidRequest"}},
                operation_name="GeneratePresignedUrl",
            )

        monkeypatch.setattr(
            s3_client._client,
            "generate_presigned_url",
            mock_generate_presigned_url,
        )

        # Act
        result = s3_client.generate_presigned_upload_url(object_key)

        # Assert
        assert result is None

    def test_generate_presigned_upload_url_general_exception(
        self, s3_setup, monkeypatch
    ):
        """Test presigned upload URL generation with general exception."""
        # Arrange
        bucket_name = s3_setup["bucket_name"]
        s3_client = S3Client(bucket_name=bucket_name)
        object_key = "uploads/new_file.txt"

        def mock_generate_presigned_url(*args, **kwargs):
            raise Exception("Network error")

        monkeypatch.setattr(
            s3_client._client,
            "generate_presigned_url",
            mock_generate_presigned_url,
        )

        # Act
        result = s3_client.generate_presigned_upload_url(object_key)

        # Assert
        assert result is None


class TestS3ClientEdgeCases:
    """Test cases for edge cases and boundary conditions."""

    def test_empty_object_key_handling(self, s3_setup):
        """Test handling of empty object keys."""
        # Arrange
        bucket_name = s3_setup["bucket_name"]
        s3_client = S3Client(bucket_name=bucket_name)

        # Empty key is not valid in S3, so test object_exists with empty key
        object_key = ""

        # Act
        result = s3_client.object_exists(object_key)

        # Assert
        # Should return False for empty key since it's invalid
        assert result is False

    def test_unicode_object_key_handling(self, s3_setup):
        """Test handling of Unicode object keys."""
        # Arrange
        bucket_name = s3_setup["bucket_name"]
        s3_client = S3Client(bucket_name=bucket_name)
        s3_boto_client = s3_setup["s3_client"]

        object_key = "files/测试文件.txt"
        content = "Unicode content: 你好世界".encode("utf-8")
        s3_boto_client.put_object(
            Bucket=bucket_name,
            Key=object_key,
            Body=content,
        )

        # Act
        result = s3_client.get_object_content(object_key)
        url_result = s3_client.generate_presigned_upload_url(object_key)

        # Assert
        assert result == content
        assert url_result is not None
        assert isinstance(url_result, str)

    def test_very_long_object_key(self, s3_setup):
        """Test handling of very long object keys."""
        # Arrange
        bucket_name = s3_setup["bucket_name"]
        s3_client = S3Client(bucket_name=bucket_name)
        s3_boto_client = s3_setup["s3_client"]

        # Create a very long key (close to S3's 1024 character limit)
        object_key = "a" * 1000  # Very long key
        s3_boto_client.put_object(
            Bucket=bucket_name,
            Key=object_key,
            Body=b"Long key content",
        )

        # Act
        result = s3_client.delete_object(object_key)

        # Assert
        assert result is True
        assert s3_client.object_exists(object_key) is False

    def test_special_characters_in_bucket_name(self, s3_setup):
        """Test handling of bucket names with special characters."""
        # Arrange
        s3_boto_client = s3_setup["s3_client"]
        special_bucket = "my.bucket-name-123"
        s3_boto_client.create_bucket(Bucket=special_bucket)
        s3_client = S3Client(bucket_name=special_bucket)

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_file:
            temp_file.write("Special bucket content")
            temp_file_path = temp_file.name

        try:
            # Act
            result = s3_client.upload_file(temp_file_path, "test.txt")

            # Assert
            assert result is True

            # Verify file was uploaded
            response = s3_boto_client.get_object(
                Bucket=special_bucket, Key="test.txt"
            )
            assert response["Body"].read().decode() == "Special bucket content"
        finally:
            # Cleanup
            os.unlink(temp_file_path)

    def test_zero_expiration_time(self, s3_setup):
        """Test handling of zero expiration time for presigned URLs."""
        # Arrange
        bucket_name = s3_setup["bucket_name"]
        s3_client = S3Client(bucket_name=bucket_name)
        object_key = "test/file1.txt"
        expiration = 0

        # Act
        result = s3_client.generate_presigned_download_url(
            object_key, expiration=expiration
        )

        # Assert
        # Even with 0 expiration, URL should be generated
        assert result is not None
        assert isinstance(result, str)

    def test_large_max_keys_parameter(self, s3_setup):
        """Test handling of large max_keys parameter in list_objects."""
        # Arrange
        bucket_name = s3_setup["bucket_name"]
        s3_client = S3Client(bucket_name=bucket_name)
        max_keys = 100000

        # Act
        result = s3_client.list_objects(max_keys=max_keys)

        # Assert
        # Should return all objects (3 in our test setup)
        assert len(result) == 3

    def test_negative_max_keys_parameter(self, s3_setup):
        """Test handling of negative max_keys parameter in list_objects."""
        # Arrange
        bucket_name = s3_setup["bucket_name"]
        s3_client = S3Client(bucket_name=bucket_name)
        max_keys = -1

        # Act
        result = s3_client.list_objects(max_keys=max_keys)

        # Assert
        # Moto doesn't enforce negative max_keys validation like real S3,
        # so we expect it to return objects rather than an error
        assert isinstance(result, list)
        # In real S3, this would return an error, but moto allows it

    def test_negative_expiration_time(self, s3_setup):
        """Test handling of negative expiration time for presigned URLs."""
        # Arrange
        bucket_name = s3_setup["bucket_name"]
        s3_client = S3Client(bucket_name=bucket_name)
        object_key = "test/file1.txt"
        expiration = -1

        # Act
        result = s3_client.generate_presigned_download_url(
            object_key, expiration=expiration
        )

        # Assert
        # Should handle negative expiration gracefully (moto might allow this)
        # Result depends on moto's implementation, but shouldn't crash
        assert result is None or isinstance(result, str)


class TestS3ClientIntegration:
    """Integration test cases testing multiple operations together."""

    def test_full_upload_download_cycle(self, s3_setup):
        """Test complete upload-download cycle."""
        # Arrange
        bucket_name = s3_setup["bucket_name"]
        s3_client = S3Client(bucket_name=bucket_name)
        object_key = "integration/test_file.txt"
        test_content = "Integration test content"

        with tempfile.NamedTemporaryFile(
            mode="w", delete=False
        ) as upload_file:
            upload_file.write(test_content)
            upload_path = upload_file.name

        with tempfile.NamedTemporaryFile(delete=False) as download_file:
            download_path = download_file.name

        try:
            # Act - Upload
            upload_result = s3_client.upload_file(upload_path, object_key)
            assert upload_result is True

            # Act - Verify exists
            exists_result = s3_client.object_exists(object_key)
            assert exists_result is True

            # Act - Get content
            content_result = s3_client.get_object_content(object_key)
            assert content_result == test_content.encode()

            # Act - Download
            download_result = s3_client.get_file(object_key, download_path)
            assert download_result is True

            # Act - Verify downloaded content
            with open(download_path, "r") as f:
                downloaded_content = f.read()
            assert downloaded_content == test_content

            # Act - Delete
            delete_result = s3_client.delete_object(object_key)
            assert delete_result is True

            # Act - Verify deletion
            exists_after_delete = s3_client.object_exists(object_key)
            assert exists_after_delete is False

        finally:
            # Cleanup
            os.unlink(upload_path)
            if os.path.exists(download_path):
                os.unlink(download_path)

    def test_presigned_url_functionality(self, s3_setup):
        """Test presigned URL generation for existing and new objects."""
        # Arrange
        bucket_name = s3_setup["bucket_name"]
        s3_client = S3Client(bucket_name=bucket_name)
        existing_key = "test/file1.txt"
        new_key = "presigned/new_file.txt"

        # Act - Generate URLs
        download_url = s3_client.generate_presigned_download_url(existing_key)
        upload_url = s3_client.generate_presigned_upload_url(new_key)

        # Assert
        assert download_url is not None
        assert upload_url is not None
        assert isinstance(download_url, str)
        assert isinstance(upload_url, str)
        assert bucket_name in download_url
        assert bucket_name in upload_url
        assert existing_key in download_url
        assert new_key in upload_url

    def test_list_objects_with_various_prefixes(self, s3_setup):
        """Test listing objects with different prefix scenarios."""
        # Arrange
        bucket_name = s3_setup["bucket_name"]
        s3_client = S3Client(bucket_name=bucket_name)

        # Act - Test various prefix scenarios
        all_objects = s3_client.list_objects()
        test_objects = s3_client.list_objects(prefix="test/")
        uploads_objects = s3_client.list_objects(prefix="uploads/")
        nonexistent_prefix = s3_client.list_objects(prefix="nonexistent/")

        # Assert
        assert len(all_objects) == 3
        assert len(test_objects) == 2
        assert len(uploads_objects) == 1
        assert len(nonexistent_prefix) == 0

        # Verify specific objects
        test_keys = {obj["Key"] for obj in test_objects}
        assert "test/file1.txt" in test_keys
        assert "test/file2.txt" in test_keys

        uploads_keys = {obj["Key"] for obj in uploads_objects}
        assert "uploads/image.jpg" in uploads_keys
