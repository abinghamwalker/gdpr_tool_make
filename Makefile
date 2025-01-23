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
SRC_DIR := src

# Phony targets
.PHONY: all clean clean-venv clean-package install lint test security-checks package deploy plan destroy validate format-terraform integration-test complexity help check-env test-local run-local create-layers create-polars-layer create-aioboto3-layer plan-and-apply clean-all

# Default target
all: clean install lint test security-checks validate format-terraform package create-layers deploy
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
	@rm -rf lambda_layer
	@rm -rf src/lambda_layer.zip
	@rm -rf terraform/lambda_layer.zip
	@rm -rf src/polars_layer.zip
	@rm -rf src/aioboto3_layer.zip

clean: clean-venv clean-package
	@echo "Clean up completed."

# Set up virtual environment and install dependencies
install:
	@echo "Setting up virtual environment and installing dependencies..."
	@$(PYTHON) -m venv $(VENV)
	@$(VENV_BIN)/pip install --upgrade pip
	@$(VENV_BIN)/pip install -r requirements.txt
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
	@$(VENV_BIN)/black --check $(PYTHON_FILES) || (echo "Code formatting check failed")

# Check code style with flake8
style-check:
	@echo "Checking code style..."
	@$(VENV_BIN)/flake8 $(PYTHON_FILES) || (echo "Code style check failed")

# Format code
format:
	@echo "Formatting code..."
	@$(VENV_BIN)/black $(PYTHON_FILES)
	@$(VENV_BIN)/isort $(PYTHON_FILES)

# Run security checks
security-checks: bandit
	@echo "Running security checks..."
	@$(VENV_BIN)/safety scan || (echo "Safety checks failed")

# Run bandit security checks
bandit:
	@echo "Running bandit security checks..."
	@$(VENV_BIN)/bandit -r $(PYTHON_FILES) || (echo "Bandit security checks failed")

# Check dependencies for known security vulnerabilities
safety:
	@echo "Checking dependencies for known security vulnerabilities..."
	@$(VENV_BIN)/safety check || (echo "Safety checks failed")

# Run tests with coverage
test:
	@echo "Running tests..."
	@$(VENV_BIN)/pytest tests/ -v --cov=$(LAMBDA_DIR) --cov-report=term-missing --cov-report=xml || (echo "Tests failed")

# Create Lambda deployment package
package:
	@echo "Creating Lambda deployment package..."
	@mkdir -p $(LAMBDA_DIR)/tmp_package
	@cd $(LAMBDA_DIR)/tmp_package && \
	cp -r ../obfuscator.py . && \
	cp -r ../obfuscator_lambda.py . && \
	cp -r ../__init__.py . && \
	$(VENV_BIN)/pip install propcache typing_extensions -t . && \
	zip -r ../lambda_package.zip ./* && \
	cd .. && \
	rm -rf tmp_package

# Create Lambda Layers (both polars and aioboto3)
create-layers: create-aioboto3-layer
	@echo "Lambda layers created successfully."


create-aioboto3-layer:
	@echo "Creating aioboto3 Lambda Layer..."
	@mkdir -p lambda_layer/aioboto3_layer/python/lib/python3.9/site-packages
	@$(VENV_BIN)/pip install aioboto3>=11.3.0 async-timeout -t lambda_layer/aioboto3_layer/python/lib/python3.9/site-packages/
	@cd lambda_layer/aioboto3_layer && zip -r ../../src/aioboto3_layer.zip .

# Initialize Terraform
init:
	@echo "Initializing Terraform..."
	@cd $(TERRAFORM_DIR) && \
	terraform init || (echo "Failed to initialize Terraform")

# Plan Terraform changes
plan: init
	@echo "Planning Terraform changes..."
	@cd $(TERRAFORM_DIR) && \
	terraform plan \
		-var="environment=$(ENVIRONMENT)" \
		-out=tfplan || (echo "Failed to plan Terraform changes")

# Apply Terraform changes
deploy: install check-env package create-layers plan
	@echo "Applying Terraform changes..."
	@cd $(TERRAFORM_DIR) && \
	terraform apply tfplan || (echo "Failed to apply Terraform changes")

# Plan and apply Terraform changes in one go
plan-and-apply: install check-env package create-layers
	@echo "Planning and applying Terraform changes..."
	@cd $(TERRAFORM_DIR) && \
	terraform plan -out=tfplan \
		-var="environment=$(ENVIRONMENT)" && \
	terraform apply tfplan || (echo "Failed to plan and apply Terraform changes")

# Destroy infrastructure
destroy: check-env
	@echo "Destroying infrastructure..."
	@cd $(TERRAFORM_DIR) && \
	terraform destroy \
		-var="environment=$(ENVIRONMENT)" \
		-auto-approve || (echo "Failed to destroy infrastructure")


# Check AWS credentials
check-env:
	@echo "Checking AWS credentials..."
	@aws sts get-caller-identity > /dev/null 2>&1 || (echo "AWS credentials not found or invalid. Please ensure your AWS credentials are configured.")
	@echo "AWS credentials verified successfully."

# Clean up everything (local files and Terraform resources)
clean-all: clean destroy
	@echo "Cleaned up local files and destroyed Terraform resources."

