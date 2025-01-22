import csv
import io
import json
import logging
import os
from typing import Any, Dict, List, Tuple, Union

import boto3
import pyarrow as pa
import pyarrow.parquet as pq
from botocore.exceptions import (
    ClientError,
    NoCredentialsError,
    PartialCredentialsError)

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


class MultiFormatObfuscator:
    """Class to implement methods to obfuscate CSV, JSON, Parquet."""

    def __init__(self):
        try:
            self.session = boto3.Session(
                aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
                region_name=os.environ.get("AWS_REGION", "eu-west-2"),
            )
            self.s3_client = self.session.client("s3")
        except (NoCredentialsError, PartialCredentialsError) as er_info:
            logger.error(f"AWS credentials error: {str(er_info)}")
            raise
        except Exception as er_info:
            logger.error(f"Error initializing S3 client: {str(er_info)}")
            raise

    def _parse_s3_uri(self, s3_uri: str) -> Dict[str, str]:
        """Parse S3 URI into bucket and key components."""
        if not s3_uri.startswith("s3://"):
            raise ValueError(f"Invalid S3 URI format: {s3_uri}")

        parts = s3_uri[5:].split("/", 1)
        return {"bucket": parts[0], "key": parts[1] if len(parts) > 1 else ""}

    def _get_file_format(self, file_path: str) -> str:
        """Get file format from file path."""
        parts = file_path.lower().split(".")
        if len(parts) < 2:
            raise ValueError("Unsupported file format: No extension found")

        extension = parts[-1]
        if extension not in ["csv", "parquet", "json"]:
            raise ValueError(f"Unsupported file format: {extension}")
        return extension

    def _get_file_from_s3(self, bucket: str, key: str) -> bytes:
        """Get file content from S3."""
        try:
            response = self.s3_client.get_object(Bucket=bucket, Key=key)
            return response["Body"].read()
        except ClientError as er_info:
            logger.error(f"Error retrieving file from S3: {str(er_info)}")
            raise

    def _put_file_to_s3(
        self, bucket: str, key: str, content: Union[str, bytes], content_type: str
    ):
        """Put file content back to S3 (overwrites the file)."""
        try:
            if isinstance(content, str):
                content = content.encode("utf-8")

            self.s3_client.put_object(
                Bucket=bucket, Key=key, Body=content, ContentType=content_type
            )
        except ClientError as er_info:
            logger.error(f"Error uploading to S3: {str(er_info)}")
            raise

    def _obfuscate_csv(
        self, csv_content: bytes, pii_fields: List[str]
    ) -> Tuple[str, str]:
        """Obfuscate specified fields in CSV content."""
        try:
            csv_str = (
                csv_content.decode("utf-8")
                if isinstance(csv_content, bytes)
                else csv_content
            )
            input_file = io.StringIO(csv_str)
            output_file = io.StringIO()

            reader = csv.DictReader(input_file)
            if not reader.fieldnames:
                raise ValueError("CSV file appears to be empty or malformed")

            missing_fields = [
                field for field in pii_fields if field not in reader.fieldnames
            ]
            if missing_fields:
                raise ValueError(
                    f"Fields not found in CSV: {', '.join(missing_fields)}"
                )

            writer = csv.DictWriter(output_file, fieldnames=reader.fieldnames)
            writer.writeheader()

            for row in reader:
                for field in pii_fields:
                    if field in row:
                        row[field] = "****"
                writer.writerow(row)

            return output_file.getvalue(), "text/csv"

        except Exception as er_info:
            logger.error(f"Error processing CSV: {str(er_info)}")
            raise

    def _obfuscate_json(
        self, json_content: bytes, pii_fields: List[str]
    ) -> Tuple[str, str]:
        """Obfuscate specified fields in JSON content."""
        try:
            json_str = (
                json_content.decode("utf-8")
                if isinstance(json_content, bytes)
                else json_content
            )
            json_data = json.loads(json_str)

            if not isinstance(json_data, list):
                raise ValueError("JSON content must be a list of objects")

            for item in json_data:
                for field in pii_fields:
                    if field in item:
                        item[field] = "****"

            return json.dumps(json_data), "application/json"

        except json.JSONDecodeError as er_info:
            logger.error(f"Invalid JSON format: {str(er_info)}")
            raise ValueError("Invalid JSON format")
        except Exception as er_info:
            logger.error(f"Error processing JSON: {str(er_info)}")
            raise

    def _obfuscate_parquet(
        self, parquet_content: bytes, pii_fields: List[str]
    ) -> Tuple[bytes, str]:
        """Obfuscate specified fields in Parquet content."""
        try:
            buffer = io.BytesIO(parquet_content)
            table = pq.read_table(buffer)
            df = table.to_pandas()

            if df.empty:
                raise ValueError("Parquet file appears to be empty")

            missing_fields = [field for field in pii_fields if field not in df.columns]
            if missing_fields:
                raise ValueError(
                    f"Fields not found in Parquet: {', '.join(missing_fields)}"
                )

            for field in pii_fields:
                if field in df.columns:
                    df[field] = "****"

            table = pa.Table.from_pandas(df)
            output_buffer = io.BytesIO()
            pq.write_table(table, output_buffer)
            return output_buffer.getvalue(), "application/parquet"

        except Exception as er_info:
            logger.error(f"Error processing Parquet: {str(er_info)}")
            raise

    def process_file(self, bucket: str, key: str, pii_fields: List[str]) -> Dict:
        """Process a single file from S3 and overwrite it in place."""
        try:
            file_format = self._get_file_format(key)
            content = self._get_file_from_s3(bucket, key)

            if file_format == "csv":
                output_content, content_type = self._obfuscate_csv(content, pii_fields)
            elif file_format == "json":
                output_content, content_type = self._obfuscate_json(content, pii_fields)
            elif file_format == "parquet":
                output_content, content_type = self._obfuscate_parquet(
                    content, pii_fields
                )
            else:
                raise ValueError(f"Unsupported file format: {file_format}")

            # Overwrite the file in S3
            self._put_file_to_s3(bucket, key, output_content, content_type)

            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "message": f"Successfully processed and overwritten s3://{bucket}/{key}",
                        "format": file_format,
                    }
                ),
            }
        except Exception as er_info:
            logger.error(f"Error processing file {key}: {str(er_info)}")
            return {"statusCode": 500, "body": json.dumps({"error": str(er_info)})}

    def process_request(self, event: Dict) -> List[Dict]:
        """Process an obfuscation request and overwrite the file in place."""
        try:
            file_to_obfuscate = event.get("file_to_obfuscate")
            pii_fields = event.get("pii_fields", [])

            if not file_to_obfuscate:
                raise ValueError("Missing required parameter: file_to_obfuscate")
            if not pii_fields:
                raise ValueError("Missing required parameter: pii_fields")

            if not file_to_obfuscate.startswith("s3://"):
                # Local file processing
                if not os.path.exists(file_to_obfuscate):
                    raise FileNotFoundError(f"File not found: {file_to_obfuscate}")

                with open(file_to_obfuscate, "rb") as f:
                    content = f.read()

                file_format = self._get_file_format(file_to_obfuscate)

                if file_format == "csv":
                    output_content, content_type = self._obfuscate_csv(
                        content, pii_fields
                    )
                elif file_format == "json":
                    output_content, content_type = self._obfuscate_json(
                        content, pii_fields
                    )
                elif file_format == "parquet":
                    output_content, content_type = self._obfuscate_parquet(
                        content, pii_fields
                    )
                else:
                    raise ValueError(f"Unsupported file format: {file_format}")

                # Overwrite the local file in place
                with open(
                    file_to_obfuscate, "w" if isinstance(output_content, str) else "wb"
                ) as f:
                    f.write(output_content)

                return {
                    "statusCode": 200,
                    "body": json.dumps(
                        {
                            "message": f"Successfully processed and overwritten local file: {file_to_obfuscate}",
                            "format": file_format,
                        }
                    ),
                }

            # S3 file processing
            s3_location = self._parse_s3_uri(file_to_obfuscate)
            return self.process_file(
                s3_location["bucket"], s3_location["key"], pii_fields
            )

        except Exception as er_info:
            logger.error(f"Error processing request: {str(er_info)}")
            return {"statusCode": 500, "body": json.dumps({"error": str(er_info)})}


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict:
    """
    AWS Lambda handler that supports both direct invocation and S3 events.
    """
    try:
        if isinstance(event, str):
            event = json.loads(event)

        obfuscator = MultiFormatObfuscator()
        result = obfuscator.process_request(event)
        return result

    except json.JSONDecodeError as er_info:
        logger.error(f"Error parsing JSON input: {str(er_info)}")
        return {"statusCode": 400, "body": json.dumps({"error": "Invalid input"})}

    except Exception as er_info:
        logger.error(f"Unexpected error: {str(er_info)}")
        return {"statusCode": 500, "body": json.dumps({"error": str(er_info)})}
