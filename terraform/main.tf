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
    bucket = "var.state_bucket"
    key    = "terraform.tfstate"
    region = "eu-west-2"
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

# Lambda function
resource "aws_lambda_function" "obfuscator" {
  s3_bucket     = var.lambda_bucket
  s3_key        = "lambda_package.zip"
  function_name = "data-obfuscator-${var.environment}"
  role          = aws_iam_role.lambda_role.arn
  handler       = "obfuscator.lambda_handler"
  runtime       = "python3.9"
  timeout       = 300
  memory_size   = 512

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

# IAM role for Lambda
resource "aws_iam_role" "lambda_role" {
  name = "obfuscator_lambda_role_${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

# IAM policy for Lambda
resource "aws_iam_role_policy" "lambda_policy" {
  name = "obfuscator_lambda_policy_${var.environment}"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Resource = [
          "${aws_s3_bucket.data_bucket.arn}/*",
          "arn:aws:s3:::${var.lambda_bucket}/*",
          aws_s3_bucket.data_bucket.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

# CloudWatch Log Group with retention
resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${aws_lambda_function.obfuscator.function_name}"
  retention_in_days = 30
}

# Outputs
output "data_bucket" {
  value = aws_s3_bucket.data_bucket.id
}

output "lambda_function_name" {
  value = aws_lambda_function.obfuscator.function_name
}
