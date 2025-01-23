provider "aws" {
  region = var.aws_region
}

# Random suffix for bucket names
resource "random_id" "bucket_suffix" {
  byte_length = 4
}

# Terraform backend configuration
terraform {
  backend "s3" {
    bucket         = "gdpr-state-bucket"  # Manually created bucket name
    key            = "terraform.tfstate"
    region         = "eu-west-2"         # Manually specified region
    encrypt        = true
  }
}

# Automatically create the S3 bucket for Lambda deployment package
resource "aws_s3_bucket" "lambda_bucket" {
  bucket = "gdpr-lambda-bucket-${var.environment}-${random_id.bucket_suffix.hex}"
}

resource "null_resource" "check_files" {
  triggers = {
    # Trigger recreation if any of the files are missing
    aioboto3_layer_exists  = fileexists("../src/aioboto3_layer.zip") ? "true" : "false"
    lambda_package_exists  = fileexists("../src/lambda_package.zip") ? "true" : "false"
  }

  # Ensure this resource is created before the S3 objects
  provisioner "local-exec" {
    command = "echo 'Checking for required files...'"
  }
}

# Upload the aioboto3 Lambda Layer to S3
resource "aws_s3_object" "aioboto3_layer" {
  bucket      = aws_s3_bucket.lambda_bucket.bucket
  key         = "aioboto3_layer.zip"
  source      = "../src/aioboto3_layer.zip"
  source_hash = filebase64sha256("../src/aioboto3_layer.zip")

  depends_on = [null_resource.check_files]

  lifecycle {
    ignore_changes = [source_hash]
  }
}

# Upload the Lambda deployment package to S3
resource "aws_s3_object" "lambda_package" {
  bucket = aws_s3_bucket.lambda_bucket.bucket
  key    = "lambda_package.zip"
  source = "../src/lambda_package.zip"
  etag   = filemd5("../src/lambda_package.zip")

  depends_on = [null_resource.check_files]

  lifecycle {
    ignore_changes = [etag]
  }
}

# Data S3 bucket (single bucket for in-place modifications)
resource "aws_s3_bucket" "data_bucket" {
  bucket = "gdpr-data-${var.environment}-${random_id.bucket_suffix.hex}"
}

resource "aws_s3_bucket_versioning" "data_versioning" {
  bucket = aws_s3_bucket.data_bucket.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data_encryption" {
  bucket = aws_s3_bucket.data_bucket.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "data_access" {
  bucket = aws_s3_bucket.data_bucket.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}


# aioboto3 Lambda Layer
resource "aws_lambda_layer_version" "aioboto3_layer" {
  layer_name          = "aioboto3-layer-${var.environment}"
  description         = "Lambda Layer for aioboto3"
  compatible_runtimes = ["python3.9"]
  s3_bucket           = aws_s3_bucket.lambda_bucket.bucket  # Reference the S3 bucket
  s3_key              = aws_s3_object.aioboto3_layer.key   # Reference the S3 object key
}

# Lambda function
resource "aws_lambda_function" "obfuscator" {
  s3_bucket     = aws_s3_bucket.lambda_bucket.bucket
  s3_key        = aws_s3_object.lambda_package.key
  function_name = "data-obfuscator-${var.environment}"
  role          = aws_iam_role.lambda_role.arn
  handler       = "obfuscator_lambda.lambda_handler"
  runtime       = "python3.9"
  timeout       = 300
  memory_size   = 512
  layers        = [
    "arn:aws:lambda:eu-west-2:770693421928:layer:Klayers-p312-polars:13",  # Correct ARN for prebuilt Polars layer
    aws_lambda_layer_version.aioboto3_layer.arn,  # Local aioboto3 layer
  ]

  environment {
    variables = {
      PII_FIELDS = join(",", var.pii_fields)
    }
  }

  depends_on = [aws_iam_role_policy.lambda_policy]
}



# S3 trigger for Lambda
resource "aws_s3_bucket_notification" "bucket_notification" {
  bucket = aws_s3_bucket.data_bucket.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.obfuscator.arn
    events              = ["s3:ObjectCreated:*"]
  }

  depends_on = [aws_lambda_permission.allow_s3]
}

# Lambda permissions
resource "aws_lambda_permission" "allow_s3" {
  statement_id  = "AllowS3Invoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.obfuscator.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.data_bucket.arn
}

# CloudWatch Log Group with retention
resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${aws_lambda_function.obfuscator.function_name}"
  retention_in_days = 30
}

