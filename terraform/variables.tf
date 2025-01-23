variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
}

variable "pii_fields" {
  description = "List of PII fields to obfuscate"
  type        = list(string)
}