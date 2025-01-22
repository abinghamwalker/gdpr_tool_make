variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "lambda_bucket" {
  description = "S3 bucket for storing Lambda deployment package"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "eu-west-2"
}

variable "pii_fields" {
  description = "List of PII fields to obfuscate"
  type        = list(string)
  default     = ["email", "phone", "ssn"]
}
