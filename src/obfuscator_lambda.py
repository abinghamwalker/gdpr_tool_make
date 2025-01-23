import csv
import io
import json
import logging
import os
from typing import Any, Dict, List, Tuple, Union
import asyncio

import polars as pl
import aioboto3
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

class MultiFormatObfuscator:
    def __init__(self):
        try:
            self.session = aioboto3.Session(
                aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
                region_name=os.environ.get("AWS_REGION", "eu-west-2"),
            )
        except (NoCredentialsError, PartialCredentialsError) as er_info:
            logger.error(f"AWS credentials error: {str(er_info)}")
            raise

    def _parse_s3_uri(self, s3_uri: str) -> Dict[str, str]:
        if not s3_uri.startswith("s3://"):
            raise ValueError(f"Invalid S3 URI format: {s3_uri}")
        parts = s3_uri[5:].split("/", 1)
        return {"bucket": parts[0], "key": parts[1] if len(parts) > 1 else ""}

    async def _get_file_from_s3(self, bucket: str, key: str) -> bytes:
        async with self.session.client("s3") as s3_client:
            try:
                response = await s3_client.get_object(Bucket=bucket, Key=key)
                return await response["Body"].read()
            except ClientError as er_info:
                logger.error(f"Error retrieving file from S3: {str(er_info)}")
                raise

    async def _put_file_to_s3(self, bucket: str, key: str, content: Union[str, bytes], content_type: str):
        async with self.session.client("s3") as s3_client:
            try:
                if isinstance(content, str):
                    content = content.encode("utf-8")
                await s3_client.put_object(Bucket=bucket, Key=key, Body=content, ContentType=content_type)
            except ClientError as er_info:
                logger.error(f"Error uploading to S3: {str(er_info)}")
                raise

    def _obfuscate_csv(self, csv_content: bytes, pii_fields: List[str]) -> Tuple[str, str]:
        try:
            df = pl.read_csv(io.BytesIO(csv_content))
            missing_fields = [field for field in pii_fields if field not in df.columns]
            if missing_fields:
                raise ValueError(f"Fields not found in CSV: {', '.join(missing_fields)}")
            
            for field in pii_fields:
                df = df.with_columns(pl.lit("****").alias(field))
            
            output = io.StringIO()
            df.write_csv(output)
            return output.getvalue(), "text/csv"
        except Exception as er_info:
            logger.error(f"Error processing CSV: {str(er_info)}")
            raise

    def _obfuscate_parquet(self, parquet_content: bytes, pii_fields: List[str]) -> Tuple[bytes, str]:
        try:
            df = pl.read_parquet(io.BytesIO(parquet_content))
            missing_fields = [field for field in pii_fields if field not in df.columns]
            if missing_fields:
                raise ValueError(f"Fields not found in Parquet: {', '.join(missing_fields)}")
            
            for field in pii_fields:
                df = df.with_columns(pl.lit("****").alias(field))
            
            output = io.BytesIO()
            df.write_parquet(output)
            return output.getvalue(), "application/parquet"
        except Exception as er_info:
            logger.error(f"Error processing Parquet: {str(er_info)}")
            raise

    async def process_file(self, bucket: str, key: str, pii_fields: List[str]) -> Dict:
        try:
            file_format = key.lower().split(".")[-1]
            content = await self._get_file_from_s3(bucket, key)

            if file_format == "csv":
                output_content, content_type = self._obfuscate_csv(content, pii_fields)
            elif file_format == "json":
                output_content, content_type = self._obfuscate_json(content, pii_fields)
            elif file_format == "parquet":
                output_content, content_type = self._obfuscate_parquet(content, pii_fields)
            else:
                raise ValueError(f"Unsupported file format: {file_format}")

            await self._put_file_to_s3(bucket, key, output_content, content_type)
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "message": f"Successfully processed and overwritten s3://{bucket}/{key}",
                    "format": file_format,
                })
            }
        except Exception as er_info:
            logger.error(f"Error processing file {key}: {str(er_info)}")
            return {"statusCode": 500, "body": json.dumps({"error": str(er_info)})}

async def async_lambda_handler(event: Dict[str, Any], context: Any) -> Dict:
    try:
        if isinstance(event, str):
            event = json.loads(event)

        obfuscator = MultiFormatObfuscator()
        if "Records" in event:
            if not event.get("Records"):
                return {"statusCode": 400, "body": json.dumps({"error": "No records found in S3 event"})}
            
            s3_event = event["Records"][0]["s3"]
            bucket = s3_event["bucket"]["name"]
            key = s3_event["object"]["key"]
            pii_fields = event.get("pii_fields", [])
            
            return await obfuscator.process_file(bucket, key, pii_fields)
        else:
            file_to_obfuscate = event.get("file_to_obfuscate")
            pii_fields = event.get("pii_fields", [])
            
            if not file_to_obfuscate or not pii_fields:
                return {"statusCode": 400, "body": json.dumps({"error": "Missing required parameters"})}
            
            s3_location = obfuscator._parse_s3_uri(file_to_obfuscate)
            return await obfuscator.process_file(s3_location["bucket"], s3_location["key"], pii_fields)

    except Exception as er_info:
        logger.error(f"Unexpected error: {str(er_info)}")
        return {"statusCode": 500, "body": json.dumps({"error": str(er_info)})}

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict:
    return asyncio.run(async_lambda_handler(event, context))