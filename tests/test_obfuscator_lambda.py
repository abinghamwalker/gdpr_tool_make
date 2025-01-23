import pytest
import aioboto3
import json
import io
import polars as pl
from unittest.mock import Mock, patch, AsyncMock
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError
import os
import sys
import asyncio

# Add src directory to Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from src.obfuscator_lambda import MultiFormatObfuscator, async_lambda_handler, lambda_handler

@pytest.fixture
def aws_credentials():
    credentials = {
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "AWS_DEFAULT_REGION": "eu-west-2"
    }
    with patch.dict(os.environ, credentials):
        yield credentials

@pytest.fixture
def sample_csv():
    return (
        "student_id,name,email_address,course\n"
        "1,John Smith,j.smith@email.com,Software\n"
        "2,Jane Doe,jane@email.com,Data\n"
    )

@pytest.fixture
def sample_parquet():
    df = pl.DataFrame({
        'student_id': ['1', '2'],
        'name': ['John Smith', 'Jane Doe'],
        'email': ['j.smith@email.com', 'j.doe@email.com'],
        'course': ['Data', 'Software']
    })
    buf = io.BytesIO()
    df.write_parquet(buf)
    return buf.getvalue()

class TestAsyncMultiFormatObfuscator:
    @pytest.mark.asyncio
    async def test_init_success(self, aws_credentials):
        obfuscator = MultiFormatObfuscator()
        assert obfuscator.session is not None

    @pytest.mark.asyncio
    async def test_init_no_credentials(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(NoCredentialsError):
                MultiFormatObfuscator()

 
    @pytest.mark.asyncio
    async def test_get_file_from_s3_success(self, aws_credentials):
        obfuscator = MultiFormatObfuscator()
        mock_response = {'Body': AsyncMock()}
        mock_response['Body'].read = AsyncMock(return_value=b"test content")

        async def async_cm():
            mock_client = AsyncMock()
            mock_client.get_object = AsyncMock(return_value=mock_response)
            return mock_client

        with patch.object(obfuscator.session, 'client', return_value=AsyncMock(
            __aenter__=AsyncMock(side_effect=async_cm),
            __aexit__=AsyncMock(),
        )):
            result = await obfuscator._get_file_from_s3("bucket", "key")
            assert result == b"test content"

    @pytest.mark.asyncio
    async def test_get_file_from_s3_client_error(self, aws_credentials):
        obfuscator = MultiFormatObfuscator()
        mock_client = AsyncMock()
        mock_client.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Not found"}},
            "GetObject"
        )
        
        with patch('aioboto3.Session', return_value=AsyncMock(
            client=Mock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_client)))
        )):
            with pytest.raises(ClientError):
                await obfuscator._get_file_from_s3("bucket", "key")
    @pytest.mark.asyncio
    async def test_put_file_to_s3_success(self, aws_credentials):
        obfuscator = MultiFormatObfuscator()
        mock_client = AsyncMock()
        mock_client.put_object = AsyncMock()

        async def async_cm():
            return mock_client

        with patch.object(obfuscator.session, 'client', return_value=AsyncMock(
            __aenter__=AsyncMock(side_effect=async_cm),
            __aexit__=AsyncMock()
        )):
            await obfuscator._put_file_to_s3("test-bucket", "test-key", "content", "text/plain")
            mock_client.put_object.assert_called_once_with(
                Bucket="test-bucket",
                Key="test-key", 
                Body=b"content",  # Note: content is encoded to bytes
                ContentType="text/plain"
            )
            
    def test_obfuscate_csv_success(self, aws_credentials, sample_csv):
        obfuscator = MultiFormatObfuscator()
        pii_fields = ['name', 'email_address']
        result, content_type = obfuscator._obfuscate_csv(sample_csv.encode("utf-8"), pii_fields)
        assert content_type == "text/csv"
        assert "****" in result

    def test_obfuscate_csv_missing_fields(self, aws_credentials, sample_csv):
        obfuscator = MultiFormatObfuscator()
        with pytest.raises(ValueError, match="Fields not found in CSV"):
            obfuscator._obfuscate_csv(sample_csv.encode("utf-8"), ["nonexistent_field"])

    def test_obfuscate_parquet_success(self, aws_credentials, sample_parquet):
        obfuscator = MultiFormatObfuscator()
        pii_fields = ['name', 'email']
        result, content_type = obfuscator._obfuscate_parquet(sample_parquet, pii_fields)
        assert content_type == "application/parquet"
        
        # Verify obfuscation
        result_df = pl.read_parquet(io.BytesIO(result))
        assert all(result_df['name'] == "****")
        assert all(result_df['email'] == "****")

    @pytest.mark.asyncio
    async def test_process_file_success(self, aws_credentials):
        obfuscator = MultiFormatObfuscator()
        with patch.object(obfuscator, '_get_file_from_s3', return_value=b"test,data\n1,2"):
            with patch.object(obfuscator, '_put_file_to_s3'):
                result = await obfuscator.process_file("bucket", "test.csv", ["data"])
                assert result["statusCode"] == 200

class TestAsyncLambdaHandler:
    
    @pytest.mark.asyncio
    async def test_async_lambda_handler_success(self, aws_credentials):
        event = {
            "file_to_obfuscate": "s3://bucket/test.csv",
            "pii_fields": ["name"]
        }

        with patch('src.obfuscator_lambda.MultiFormatObfuscator') as mock_obfuscator:
            mock_instance = AsyncMock()
            mock_instance.process_file = AsyncMock(return_value={"statusCode": 200})
            mock_instance._parse_s3_uri.return_value = {"bucket": "bucket", "key": "test.csv"}
            mock_obfuscator.return_value = mock_instance

            result = await async_lambda_handler(event, None)
            assert result["statusCode"] == 200

    @pytest.mark.asyncio
    async def test_async_lambda_handler_s3_event(self, aws_credentials):
        event = {
            "Records": [{
                "s3": {
                    "bucket": {"name": "test-bucket"},
                    "object": {"key": "test.csv"}
                }
            }],
            "pii_fields": ["name"]
        }

        with patch('src.obfuscator_lambda.MultiFormatObfuscator') as mock_obfuscator:
            mock_instance = AsyncMock()
            mock_instance.process_file = AsyncMock(return_value={"statusCode": 200})
            mock_obfuscator.return_value = mock_instance

            result = await async_lambda_handler(event, None)
            assert result["statusCode"] == 200

    @pytest.mark.asyncio
    async def test_async_lambda_handler_success(self, aws_credentials):
        event = {
            "file_to_obfuscate": "s3://bucket/test.csv",
            "pii_fields": ["name"]
        }

        mock_instance = AsyncMock()
        mock_instance.process_file = AsyncMock(return_value={"statusCode": 200, "body": "success"})
        mock_instance._parse_s3_uri = Mock(return_value={"bucket": "bucket", "key": "test.csv"})
        
        with patch('src.obfuscator_lambda.MultiFormatObfuscator', return_value=mock_instance) as mock_class:
            mock_class.side_effect = None
            result = await async_lambda_handler(event, None)
            assert result["statusCode"] == 200
            assert result["body"] == "success"

    def test_lambda_handler_invalid_json(self):
        invalid_event = "{'invalid': json}"  
        result = lambda_handler(invalid_event, None) 
        assert result['statusCode'] == 400
        assert 'Invalid JSON input' in result['body']

    @pytest.mark.asyncio
    async def test_async_lambda_handler_missing_parameters(self, aws_credentials):
        event = {"file_to_obfuscate": "s3://bucket/test.csv"}
        result = await async_lambda_handler(event, None)
        assert result["statusCode"] == 400
        assert "Missing required parameters" in result["body"]

    @pytest.mark.asyncio
    async def test_async_lambda_handler_empty_records(self, aws_credentials):
        event = {"Records": [], "pii_fields": ["name"]}
        result = await async_lambda_handler(event, None)
        assert result["statusCode"] == 400
        assert "No records found in S3 event" in result["body"]