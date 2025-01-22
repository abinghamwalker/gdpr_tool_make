# Makefile

# Variables with absolute paths
PYTHON := python3
PIP := pip3
VENV := $(shell pwd)/venv
VENV_BIN := $(VENV)/bin
LAMBDA_DIR := $(shell pwd)/src
TERRAFORM_DIR := $(shell pwd)/terraform
ENVIRONMENT ?= dev
PYTHON_FILES := $(LAMBDA_DIR)
LAMBDA_BUCKET ?= my-lambda-bucket

# Phony targets
.PHONY: all clean clean-venv clean-package install lint test security-checks package deploy plan destroy validate format-terraform integration-test complexity help check-env test-local run-local

# Default target
all: clean install lint test security-checks validate format-terraform package deploy
	@echo "Build completed successfully."

# Clean up targets
clean-venv:
	@echo "Cleaning up virtual environment..."
	@rm -rf $(VENV)

clean-package:
	@echo "Cleaning up package artifacts..."
	@rm -rf $(LAMBDA_DIR)/lambda_package.zip
	@rm -rf $(LAMBDA_DIR)/__pycache__
	@rm -rf $(LAMBDA_DIR)/*.dist-info
	@rm -rf $(LAMBDA_DIR)/*.egg-info
	@rm -rf $(LAMBDA_DIR)/tmp_package
	@find . -type f -name "*.pyc" -delete
	@find . -type d -name "__pycache__" -delete
	@rm -f coverage.xml
	@rm -rf .coverage
	@rm -rf .pytest_cache
	@rm -rf .mypy_cache


clean: clean-venv clean-package
	@echo "Clean up completed."

# Set up virtual environment and install dependencies
install:
	@echo "Setting up virtual environment and installing dependencies..."
	@$(PYTHON) -m venv $(VENV)
	@$(VENV_BIN)/pip install --upgrade pip
	@$(VENV_BIN)/pip install -r $(LAMBDA_DIR)/requirements.txt
	@if [ "$(ENVIRONMENT)" = "dev" ]; then \
		$(VENV_BIN)/pip install pytest pytest-cov black flake8 isort bandit safety mypy pylint pre-commit || echo "Optional dev dependencies installation completed with warnings"; \
	fi

# Quality checks
quality-checks: lint test security-checks
	@echo "Running quality checks..."

# Run all linting
lint: format-check style-check
	@echo "Running linting..."

# Optional type checking
type-check:
	@echo "Running static type checking..."
	@$(VENV_BIN)/mypy $(PYTHON_FILES) || echo "Type checking completed with warnings"

# Check code formatting with black
format-check:
	@echo "Checking code formatting..."
	@$(VENV_BIN)/black --check $(PYTHON_FILES) || (echo "Code formatting check failed"; exit 1)

# Check code style with flake8
style-check:
	@echo "Checking code style..."
	@$(VENV_BIN)/flake8 $(PYTHON_FILES) || (echo "Code style check failed"; exit 1)

# Format code
format:
	@echo "Formatting code..."
	@$(VENV_BIN)/black $(PYTHON_FILES)
	@$(VENV_BIN)/isort $(PYTHON_FILES)

# Run security checks
security-checks: bandit
	@echo "Running security checks..."
	@$(VENV_BIN)/safety scan || (echo "Safety checks failed"; exit 1)

# Run bandit security checks
bandit:
	@echo "Running bandit security checks..."
	@$(VENV_BIN)/bandit -r $(PYTHON_FILES) || (echo "Bandit security checks failed"; exit 1)

# Check dependencies for known security vulnerabilities
safety:
	@echo "Checking dependencies for known security vulnerabilities..."
	@$(VENV_BIN)/safety check || (echo "Safety checks failed"; exit 1)

# Run tests with coverage
test:
	@echo "Running tests..."
	@$(VENV_BIN)/pytest tests/ -v --cov=$(LAMBDA_DIR) --cov-report=term-missing --cov-report=xml || (echo "Tests failed"; exit 1)


# Create Lambda deployment package
package:
	@echo "Creating Lambda deployment package..."
	@mkdir -p $(LAMBDA_DIR)/tmp_package
	@cd $(LAMBDA_DIR)/tmp_package && \
	cp -r ../requirements.txt . && \
	cp -r ../*.py . && \
	$(VENV_BIN)/pip install -r requirements.txt -t . && \
	zip -r ../lambda_package.zip ./* && \
	cd .. && \
	rm -rf tmp_package

# Initialize Terraform
init:
	@echo "Initializing Terraform..."
	@cd $(TERRAFORM_DIR) && \
	terraform init || (echo "Failed to initialize Terraform"; exit 1)

# Plan Terraform changes
plan: init
	@echo "Planning Terraform changes..."
	@cd $(TERRAFORM_DIR) && \
	terraform plan \
		-var="environment=$(ENVIRONMENT)" \
		-out=tfplan || (echo "Failed to plan Terraform changes"; exit 1)

# Apply Terraform changes
deploy: install check-env package plan
	@echo "Applying Terraform changes..."
	@cd $(TERRAFORM_DIR) && \
	terraform apply tfplan || (echo "Failed to apply Terraform changes"; exit 1)


# Upload Lambda deployment package to S3
upload-lambda:
	@echo "Uploading Lambda deployment package to S3..."
	@echo "Checking if package exists..."
	@test -f $(LAMBDA_DIR)/lambda_package.zip || (echo "lambda_package.zip not found in $(LAMBDA_DIR)"; exit 1)
	@echo "Uploading to s3://$(LAMBDA_BUCKET)/lambda_package.zip..."
	@aws s3 cp $(LAMBDA_DIR)/lambda_package.zip s3://$(LAMBDA_BUCKET)/lambda_package.zip || (echo "Failed to upload Lambda package"; exit 1)
	@echo "Verifying upload..."
	@aws s3 ls s3://$(LAMBDA_BUCKET)/lambda_package.zip || (echo "Failed to verify Lambda package in S3"; exit 1)


# Destroy infrastructure
destroy: check-env
	@echo "Destroying infrastructure..."
	@cd $(TERRAFORM_DIR) && \
	terraform destroy \
		-var="environment=$(ENVIRONMENT)" \
		-auto-approve || (echo "Failed to destroy infrastructure"; exit 1)

# Validate terraform files
validate:
	@echo "Validating Terraform files..."
	@cd $(TERRAFORM_DIR) && \
	terraform fmt -check && \
	terraform validate || (echo "Terraform validation failed"; exit 1)

# Format terraform files
format-terraform:
	@echo "Formatting Terraform files..."
	@cd $(TERRAFORM_DIR) && \
	terraform fmt -recursive || (echo "Failed to format Terraform files"; exit 1)

# Run integration tests
integration-test:
	@echo "Running integration tests..."
	@$(VENV_BIN)/pytest tests/integration -v || (echo "Integration tests failed"; exit 1)

# Run code complexity analysis
complexity:
	@echo "Running code complexity analysis..."
	@$(VENV_BIN)/radon cc $(PYTHON_FILES) -a || (echo "Code complexity analysis failed"; exit 1)

# Check AWS credentials
check-env:
	@echo "Checking AWS credentials..."
	@aws sts get-caller-identity > /dev/null 2>&1 || (echo "AWS credentials not found or invalid. Please ensure your AWS credentials are configured."; exit 1)
	@echo "AWS credentials verified successfully."

# Display help message
help:
	@echo "Available targets:"
	@echo "  all              - Run all build steps (clean, install, lint, test, security-checks, package, deploy)"
	@echo "  clean            - Clean up build artifacts"
	@echo "  install          - Set up virtual environment and install dependencies"
	@echo "  lint             - Run all linting checks (format, style)"
	@echo "  type-check      - Run optional static type checking"
	@echo "  test             - Run tests with coverage"
	@echo "  security-checks  - Run security checks (bandit, safety)"
	@echo "  package          - Create Lambda deployment package"
	@echo "  deploy           - Apply Terraform changes"
	@echo "  destroy          - Destroy infrastructure"
	@echo "  validate         - Validate Terraform files"
	@echo "  format-terraform - Format Terraform files"
	@echo "  integration-test - Run integration tests"
	@echo "  complexity       - Run code complexity analysis"
	@echo "  check-env        - Check AWS credentials"
	@echo "  help             - Display this help message"
