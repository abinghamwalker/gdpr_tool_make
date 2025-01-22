import pytest
import boto3
import json
import io
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from moto import mock_aws
from unittest.mock import Mock, patch
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError
import logging
import os
import sys

# Add src directory to Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from src.obfuscator import MultiFormatObfuscator, lambda_handler

# Fixtures
@pytest.fixture
def aws_credentials():
    """Mocked AWS Credentials for environment."""
    credentials = {
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "AWS_DEFAULT_REGION": "eu-west-2"
    }
    with patch.dict(os.environ, credentials):
        yield credentials

@pytest.fixture
def mock_aws_env(monkeypatch):
    """Mock AWS environment variables."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-2")

@pytest.fixture
def sample_csv():
    """Sample CSV content for testing."""
    return (
        "student_id,name,email_address,course\n"
        "1,John Smith,j.smith@email.com,Software\n"
        "2,Jane Doe,jane@email.com,Data\n"
    )

@pytest.fixture
def sample_json():
    """Sample JSON content for testing."""
    return """[
        {"student_id": "1", "name": "John Smith", "email": "j.smith@email.com", "course": "Data"},
        {"student_id": "2", "name": "Jane Doe", "email": "j.doe@email.com", "course": "Software"}
    ]"""

@pytest.fixture
def sample_parquet():
    """Sample Parquet content for testing."""
    df = pd.DataFrame({
        'student_id': ['1', '2'],
        'name': ['John Smith', 'Jane Doe'],
        'email': ['j.smith@email.com', 'j.doe@email.com'],
        'course': ['Data', 'Software']
    })
    table = pa.Table.from_pandas(df)
    buf = io.BytesIO()
    pq.write_table(table, buf)
    return buf.getvalue()

@pytest.fixture
def setup_s3(sample_csv):
    """Setup mock S3."""
    with mock_aws():
        s3_client = boto3.client("s3", region_name="eu-west-2")
        bucket_name = "test-bucket"
        file_key = "test-data/file1.csv"

        # Create bucket and upload file
        s3_client.create_bucket(
            Bucket=bucket_name,
            CreateBucketConfiguration={"LocationConstraint": "eu-west-2"},
        )
        s3_client.put_object(
            Bucket=bucket_name, Key=file_key, Body=sample_csv.encode("utf-8")
        )

        yield {"client": s3_client, "bucket": bucket_name, "key": file_key}

@pytest.fixture
def mock_s3_client():
    """Create a mock S3 client fixture."""
    with patch('boto3.Session') as mock_session:
        mock_client = Mock()
        mock_session.return_value.client.return_value = mock_client
        yield mock_client

@pytest.fixture
def obfuscator(mock_s3_client):
    """Create a MultiFormatObfuscator instance with mock S3 client."""
    return MultiFormatObfuscator()

# Tests
class TestMultiFormatObfuscator:
    """Test suite for MultiFormatObfuscator class."""

    def test_init_success(self, aws_credentials):
        """Test successful initialization of MultiFormatObfuscator."""
        obfuscator = MultiFormatObfuscator()
        assert obfuscator.s3_client is not None

    def test_init_no_credentials(self):
        """Test initialization with missing AWS credentials."""
        with patch.dict(os.environ, {}, clear=True):
            with patch('boto3.Session', side_effect=NoCredentialsError):
                with pytest.raises(NoCredentialsError):
                    MultiFormatObfuscator()

    def test_init_partial_credentials(self):
        """Test initialization with partial AWS credentials."""
        with patch.dict(os.environ, {"AWS_ACCESS_KEY_ID": "testing"}, clear=True):
            # Mock boto3.Session to raise PartialCredentialsError when the client is accessed
            with patch('boto3.Session') as mock_session:
                mock_session.return_value.client.side_effect = PartialCredentialsError(
                    provider="aws",
                    cred_var="AWS_SECRET_ACCESS_KEY"
                )
                with pytest.raises(PartialCredentialsError):
                    obfuscator = MultiFormatObfuscator()
                    # Trigger an S3 operation to force credential check
                    obfuscator._get_file_from_s3("test-bucket", "test-key")

    def test_parse_s3_uri_valid(self, aws_credentials):
        """Test parsing valid S3 URI."""
        obfuscator = MultiFormatObfuscator()
        uri = "s3://test-bucket/path/to/file.csv"
        result = obfuscator._parse_s3_uri(uri)
        assert result["bucket"] == "test-bucket"
        assert result["key"] == "path/to/file.csv"

    def test_parse_s3_uri_invalid(self, aws_credentials):
        """Test parsing invalid S3 URI."""
        obfuscator = MultiFormatObfuscator()
        invalid_uri = "invalid-uri"
        with pytest.raises(ValueError, match="Invalid S3 URI format"):
            obfuscator._parse_s3_uri(invalid_uri)

    @mock_aws
    def test_get_file_from_s3_success(self, setup_s3, aws_credentials):
        """Test successful file retrieval from S3."""
        obfuscator = MultiFormatObfuscator()
        content = obfuscator._get_file_from_s3(setup_s3["bucket"], setup_s3["key"])
        assert isinstance(content, bytes)

    @mock_aws
    def test_get_file_from_s3_not_found(self, setup_s3, aws_credentials):
        """Test retrieval of non-existent file."""
        obfuscator = MultiFormatObfuscator()
        non_existent_key = "nonexistent-file.csv"
        with pytest.raises(ClientError):
            obfuscator._get_file_from_s3(setup_s3["bucket"], non_existent_key)

    @mock_aws
    def test_put_file_to_s3_success(self, setup_s3, aws_credentials):
        """Test successful file upload to S3."""
        obfuscator = MultiFormatObfuscator()
        content = "test content"
        obfuscator._put_file_to_s3(setup_s3["bucket"], setup_s3["key"], content, "text/plain")

    @mock_aws
    def test_put_file_to_s3_failure(self, setup_s3, aws_credentials):
        """Test failed file upload to S3."""
        obfuscator = MultiFormatObfuscator()
        invalid_bucket = "invalid-bucket"
        content = "test content"
        with pytest.raises(ClientError):
            obfuscator._put_file_to_s3(invalid_bucket, setup_s3["key"], content, "text/plain")

    def test_obfuscate_csv_success(self, aws_credentials, sample_csv):
        """Test successful CSV obfuscation."""
        obfuscator = MultiFormatObfuscator()
        pii_fields = ['name', 'email_address']
        result, content_type = obfuscator._obfuscate_csv(sample_csv.encode("utf-8"), pii_fields)
        assert content_type == "text/csv"
        assert "****" in result

    def test_obfuscate_csv_empty(self, aws_credentials):
        """Test obfuscation of empty CSV content."""
        obfuscator = MultiFormatObfuscator()
        empty_csv = b""
        pii_fields = ['name']
        with pytest.raises(ValueError, match="CSV file appears to be empty"):
            obfuscator._obfuscate_csv(empty_csv, pii_fields)

    def test_obfuscate_json_success(self, aws_credentials, sample_json):
        """Test successful JSON obfuscation."""
        obfuscator = MultiFormatObfuscator()
        pii_fields = ['name', 'email']
        result, content_type = obfuscator._obfuscate_json(sample_json.encode("utf-8"), pii_fields)
        assert content_type == "application/json"
        assert "****" in result

    def test_obfuscate_json_invalid(self, aws_credentials):
        """Test obfuscation of invalid JSON content."""
        obfuscator = MultiFormatObfuscator()
        invalid_json = b"invalid json"
        pii_fields = ['name']
        with pytest.raises(ValueError, match="Invalid JSON format"):
            obfuscator._obfuscate_json(invalid_json, pii_fields)

    def test_obfuscate_parquet_success(self, aws_credentials, sample_parquet):
        """Test successful Parquet obfuscation."""
        obfuscator = MultiFormatObfuscator()
        pii_fields = ['name', 'email']
        result, content_type = obfuscator._obfuscate_parquet(sample_parquet, pii_fields)
        assert content_type == "application/parquet"
        assert isinstance(result, bytes)

    def test_obfuscate_parquet_empty(self, aws_credentials):
        """Test obfuscation of empty Parquet content."""
        obfuscator = MultiFormatObfuscator()
        empty_df = pd.DataFrame()
        empty_table = pa.Table.from_pandas(empty_df)
        buffer = io.BytesIO()
        pq.write_table(empty_table, buffer)
        pii_fields = ['name']
        with pytest.raises(ValueError, match="Parquet file appears to be empty"):
            obfuscator._obfuscate_parquet(buffer.getvalue(), pii_fields)

    @mock_aws
    def test_process_file_success(self, setup_s3, aws_credentials):
        """Test successful file processing."""
        obfuscator = MultiFormatObfuscator()
        pii_fields = ['name', 'email_address']
        result = obfuscator.process_file(setup_s3["bucket"], setup_s3["key"], pii_fields)
        assert result["statusCode"] == 200

    @mock_aws
    def test_process_file_unsupported_format(self, setup_s3, aws_credentials):
        """Test processing unsupported file format."""
        obfuscator = MultiFormatObfuscator()
        unsupported_key = "test-data/file1.txt"
        pii_fields = ['name']
        result = obfuscator.process_file(setup_s3["bucket"], unsupported_key, pii_fields)
        assert result["statusCode"] == 500
        assert "Unsupported file format" in result["body"]

    @mock_aws
    def test_process_request_success(self, setup_s3, aws_credentials):
        """Test successful request processing."""
        obfuscator = MultiFormatObfuscator()
        event = {
            "file_to_obfuscate": f"s3://{setup_s3['bucket']}/{setup_s3['key']}",
            "pii_fields": ["name", "email_address"],
        }
        result = obfuscator.process_request(event)
        assert result["statusCode"] == 200

    @mock_aws
    def test_process_request_s3_event(self, setup_s3, aws_credentials):
        """Test processing S3 event."""
        obfuscator = MultiFormatObfuscator()
        event = {
            "Records": [
                {
                    "eventName": "ObjectCreated:Put",
                    "s3": {
                        "bucket": {"name": setup_s3["bucket"]},
                        "object": {"key": setup_s3["key"]}
                    }
                }
            ],
            "pii_fields": ["name"]
        }
        result = obfuscator.process_request(event)
        assert result["statusCode"] == 200

    def test_process_request_missing_file_parameter(self, aws_credentials):
        """Test request processing with missing file_to_obfuscate parameter."""
        obfuscator = MultiFormatObfuscator()
        event = {"pii_fields": ["name"]}
        result = obfuscator.process_request(event)
        assert result["statusCode"] == 500

    def test_process_request_missing_pii_fields(self, aws_credentials):
        """Test request processing with missing pii_fields parameter."""
        obfuscator = MultiFormatObfuscator()
        event = {"file_to_obfuscate": "s3://bucket/file.csv"}
        result = obfuscator.process_request(event)
        assert result["statusCode"] == 500

class TestLambdaHandler:
    """Test suite for Lambda handler."""

    @mock_aws
    def test_lambda_handler_success(self, setup_s3, mock_aws_env):
        """Test successful Lambda execution."""
        event = {
            "file_to_obfuscate": f"s3://{setup_s3['bucket']}/{setup_s3['key']}",
            "pii_fields": ["name", "email_address"],
        }
        result = lambda_handler(event, None)
        assert result["statusCode"] == 200

    def test_lambda_handler_invalid_json(self):
        """Test Lambda with invalid JSON input."""
        event = "invalid json"
        result = lambda_handler(event, None)
        assert result["statusCode"] == 400

    def test_lambda_handler_unexpected_error(self):
        """Test Lambda handler with unexpected error."""
        with patch('src.obfuscator.MultiFormatObfuscator', side_effect=Exception("Unexpected error")):
            result = lambda_handler({}, None)
            assert result["statusCode"] == 500
