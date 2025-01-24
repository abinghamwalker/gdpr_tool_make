# GDPR Obfuscator Project

A robust data anonymization tool designed to help organizations comply with GDPR requirements by automatically obfuscating personally identifiable information (PII) in AWS S3 data storage. The tool supports multiple file formats (CSV, JSON, and Parquet) and can be deployed either locally or as an AWS Lambda function for automated processing.

## Key Features

- Process multiple file formats (CSV, JSON, Parquet)
- AWS S3 and Lambda integration
- Infrastructure as Code deployment using Terraform
- Configurable field-level obfuscation
- Comprehensive test coverage
- In-place data anonymization

## Prerequisites

- Python 3.x
- Terraform
- AWS CLI (configured with appropriate credentials)
- One S3 buckets:
  - Terraform state bucket.

## Installation

1. Clone the repository:

```bash
git clone https://github.com/your-repo/gdpr-obfuscator.git
cd gdpr-obfuscator
```

2. Set up the environment and run checks:

```bash
make install
make quality-checks
make test
```

## Local Usage

The tool can be run locally using `run_locally.py`:

```bash
python run_locally.py <input_file> <pii_fields>
```

### Parameters:

- `input_file`: Path to your data file (CSV, JSON, or Parquet)
- `pii_fields`: JSON array of field names to obfuscate (e.g., `'["name", "email"]'`)

### Examples:

```bash
# Obfuscate CSV
python run_locally.py data.csv '["name", "email"]'

# Obfuscate JSON
python run_locally.py data.json '["name", "email"]'

# Obfuscate Parquet
python run_locally.py data.parquet '["name", "email"]'
```

### Sample Input/Output

CSV Example:

```csv
# Input (data.csv)
name,email,phone
John Doe,john.doe@example.com,123-456-7890

# Output
name,email,phone
****,****,123-456-7890
```

JSON Example:

```json
// Input
{
  "name": "John Doe",
  "email": "john.doe@example.com",
  "phone": "123-456-7890"
}

// Output
{
  "name": "****",
  "email": "****",
  "phone": "123-456-7890"
}
```

## AWS Lambda Deployment

The tool can be deployed as an AWS Lambda function for automated processing. Note that a specialized version (`obfuscator_lambda.py`) is used due to AWS Lambda layer size limitations.

### Deployment Steps

1. Create a Terraform state bucket (if not exists):

```bash
aws s3api create-bucket \
  --bucket gdpr-state-bucket \
  --region eu-west-2 \
  --create-bucket-configuration LocationConstraint=eu-west-2
```

2. Update the state bucket name in `main.tf` (line 13)

3. Deploy using Make commands:

```bash
make clean install
make quality-checks
make package create-layers
make init  # First-time only
make plan-and-apply
```

### Testing the Lambda Function

Send a test event with the following JSON structure:

```json
{
  "file_to_obfuscate": "s3://your-bucket/file.csv",
  "pii_fields": ["name", "email"]
}
```

### Cleanup

To remove all AWS resources:

1. Empty all S3 buckets (except the state bucket)
2. Run: `make clean-all`

## Future Enhancements

1. Automatic processing of new files added to S3 by the tool when sat on Lambda
2. Email notifications for completed processes from above.
3. Increased test coverage for `obfuscator_lambda.py`
4. Unified codebase between local and Lambda versions to harmonise imports between obfuscators.

## Error Handling

The tool provides clear error messages for common issues:

- Missing input files
- Invalid JSON format for PII fields
- Processing errors with detailed messages

For more detailed error information, check the logs generated during execution.
