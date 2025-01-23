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
          "${aws_s3_bucket.lambda_bucket.arn}/*",
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
      },
      {
        Effect = "Allow"
        Action = [
          "lambda:GetLayerVersion"
        ]
        Resource = [
          "arn:aws:lambda:eu-west-2:770693421928:layer:Klayers-p312-polars:13"  # Allow access to the prebuilt Polars layer
        ]
      }
    ]
  })
}