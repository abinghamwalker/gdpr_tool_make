# GDPR Obfuscator Project

The GDPR Obfuscator Project is a tool designed to help Northcoders comply with GDPR requirements by anonymizing personally identifiable information (PII) in data stored in AWS S3. It supports CSV, JSON, and Parquet file formats and can be integrated into AWS Lambda for automated processing. The tool replaces sensitive data fields with obfuscated values, ensuring compliance with GDPR regulations.

## Features

The GDPR Obfuscator offers comprehensive functionality for data anonymization:

- **Multi-Format Support**: Works with CSV, JSON, and Parquet files, providing flexibility for different data storage formats.

- **AWS Integration**: Seamlessly integrates with AWS S3 and Lambda for cloud-based processing and automation.

- **Automated Deployment**: Uses Terraform for infrastructure-as-code deployment, ensuring consistent and repeatable deployments.

- **Customizable Obfuscation**: Allows users to specify which fields to obfuscate in the input data, providing control over the anonymization process.

- **Comprehensive Testing**: Includes unit tests, integration tests, and security checks to ensure reliability and security.

## Prerequisites

Before using the GDPR Obfuscator, ensure you have the following prerequisites installed and configured:

- Python 3.x: Verify installation with `python3 --version`
- Terraform: Verify installation with `terraform --version`
- AWS CLI: Configure with your credentials using `aws configure`
- S3 Buckets: Manually create two S3 buckets, the names of these will be required:
  - Lambda Bucket: For storing Lambda deployment packages
  - Terraform State Bucket: For storing Terraform state files

## Installation

1. Clone the Repository:

```bash
git clone https://github.com/your-repo/gdpr-obfuscator.git
cd gdpr-obfuscator
```

2. Set Up the Virtual Environment:

```bash
make install
```

3. Run Quality Checks:

```bash
make lint
make security-checks
```

4. Run Tests:

```bash
make test
```

## Usage

### Running Locally

You can run the GDPR Obfuscator locally using the `run_locally.py` script. This script takes two arguments:

1. The path to the input file
2. A JSON array of fields to obfuscate

#### Usage Syntax

```bash
python run_locally.py <input_file> <pii_fields>
```

- `<input_file>`: Path to the input file (CSV, JSON, or Parquet)
- `<pii_fields>`: A JSON array of field names to obfuscate (e.g., `["name", "email"]`)

#### Examples

Obfuscate a CSV file:

```bash
python run_locally.py data.csv '["name", "email"]'
```

Obfuscate a JSON file:

```bash
python run_locally.py data.json '["name", "email"]'
```

Obfuscate a Parquet file:

```bash
python run_locally.py data.parquet '["name", "email"]'
```

### Input File Examples

#### CSV (data.csv):

```csv
name,email,phone
John Doe,john.doe@example.com,123-456-7890
Jane Smith,jane.smith@example.com,987-654-3210
```

#### JSON (data.json):

```json
[
  {
    "name": "John Doe",
    "email": "john.doe@example.com",
    "phone": "123-456-7890"
  },
  {
    "name": "Jane Smith",
    "email": "jane.smith@example.com",
    "phone": "987-654-3210"
  }
]
```

#### Parquet (data.parquet):

Use a tool like pandas to create a Parquet file:

```python
import pandas as pd
df = pd.DataFrame({
    "name": ["John Doe", "Jane Smith"],
    "email": ["john.doe@example.com", "jane.smith@example.com"],
    "phone": ["123-456-7890", "987-654-3210"]
})
df.to_parquet("data.parquet")
```

### Output

The input file will be overwritten with the obfuscated data.

For example, after running the script on data.csv:

```csv
name,email,phone
****,****,123-456-7890
****,****,987-654-3210
```

The script will print the result to the console:

```json
{
  "statusCode": 200,
  "body": {
    "message": "Successfully processed and overwritten local file: data.csv",
    "format": "csv"
  }
}
```

### Error Handling

- If the input file is not found:

```
Input file not found: <input_file>
```

- If the PII fields are not provided in valid JSON format:

```
Invalid JSON format for PII fields. Please provide a valid JSON array of field names.
```

- If an error occurs during processing:

```
Error processing file: <error details>
```

## AWS Lambda Integration

The GDPR Obfuscator can be deployed as an AWS Lambda function:

1. Package the Lambda Function:

```bash
make package
```

2. Upload the Package to S3:

```bash
make upload-lambda
```

3. Deploy with Terraform:

```bash
make deploy
```

4. Test the Lambda Function using the following JSON input:

```json
{
  "file_to_obfuscate": "s3://your-bucket/file.csv",
  "pii_fields": ["name", "email_address"]
}
```

## Terraform Operations

The project includes Terraform configurations for deploying AWS infrastructure:

- Initialize Terraform: `make init`
- Plan Terraform Changes: `make plan`
- Apply Terraform Changes: `make deploy`
- Destroy Infrastructure: `make destroy`

## Makefile Commands

The project includes a comprehensive Makefile that automates various tasks:

- `make install`: Sets up the virtual environment and installs dependencies
- `make clean`: Cleans up build artifacts, including the virtual environment
- `make lint`: Runs code formatting and style checks
- `make format`: Automatically formats code using black and isort
- `make security-checks`: Runs security checks using bandit and safety
- `make test`: Runs unit tests with coverage reporting
- `make package`: Creates a Lambda deployment package
- `make upload-lambda`: Uploads the Lambda deployment package to S3
- `make deploy`: Deploys infrastructure using Terraform
- `make destroy`: Destroys the deployed infrastructure
- `make validate`: Validates Terraform configuration files
- `make format-terraform`: Formats Terraform files
- `make integration-test`: Runs integration tests
- `make complexity`: Runs code complexity analysis
- `make check-env`: Verifies AWS credentials
- `make help`: Displays a help message with available targets

## Testing

After you have run `make install`:

### Unit Tests

Run unit tests with coverage:

```bash
make test
```

### Integration Tests

Run integration tests:

```bash
make integration-test
```

### Security Checks

Run security checks to ensure code safety:

```bash
make security-checks
```
