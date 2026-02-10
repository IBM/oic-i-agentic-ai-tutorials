.PHONY: help deploy-dev deploy-test deploy-prod check-env clean lint

# Default target
help:
	@echo "Retail Application Deployment - Makefile"
	@echo ""
	@echo "Available targets:"
	@echo "  deploy-dev      - Deploy to development environment"
	@echo "  deploy-test     - Deploy to test environment"
	@echo "  deploy-prod     - Deploy to production environment"
	@echo "  check-env       - Verify environment variables are set"
	@echo "  lint            - Run ansible-lint on playbooks"
	@echo "  clean           - Clean up temporary files"
	@echo "  list-roles      - List all available roles"
	@echo "  verify-dev      - Verify development deployment"
	@echo "  verify-test     - Verify test deployment"
	@echo "  verify-prod     - Verify production deployment"
	@echo ""
	@echo "Usage examples:"
	@echo "  make deploy-dev"
	@echo "  make check-env"
	@echo "  make verify-dev"

# Check if required environment variables are set
check-env:
	@echo "Checking environment variables..."
	@test -n "$$OC_TOKEN" || (echo "ERROR: OC_TOKEN is not set" && exit 1)
	@test -n "$$DOCKER_USERNAME" || (echo "ERROR: DOCKER_USERNAME is not set" && exit 1)
	@test -n "$$DOCKER_PASSWORD" || (echo "ERROR: DOCKER_PASSWORD is not set" && exit 1)
	@echo "✓ All required environment variables are set"

# Deploy to development
deploy-dev: check-env
	@echo "Deploying to development environment..."
	ansible-playbook playbooks/deploy-development.yml

# Deploy to test
deploy-test: check-env
	@echo "Deploying to test environment..."
	ansible-playbook -i inventories/test/hosts playbooks/deploy-test.yml

# Deploy to production
deploy-prod: check-env
	@echo "Deploying to production environment..."
	@test -n "$$JWT_SECRET" || (echo "WARNING: JWT_SECRET is not set for production" && exit 1)
	@test -n "$$DB_PASSWORD" || (echo "WARNING: DB_PASSWORD is not set for production" && exit 1)
	ansible-playbook -i inventories/production/hosts playbooks/deploy-production.yml

# Verify development deployment
verify-dev:
	@echo "Verifying development deployment..."
	@oc get pods -n retail-dev
	@oc get routes -n retail-dev

# Verify test deployment
verify-test:
	@echo "Verifying test deployment..."
	@oc get pods -n retail-test
	@oc get routes -n retail-test

# Verify production deployment
verify-prod:
	@echo "Verifying production deployment..."
	@oc get pods -n retail-prod
	@oc get routes -n retail-prod

# List all roles
list-roles:
	@echo "Available Ansible roles:"
	@ls -1 roles/

# Run ansible-lint
lint:
	@echo "Running ansible-lint..."
	@command -v ansible-lint >/dev/null 2>&1 || (echo "ansible-lint not found. Install with: pip install ansible-lint" && exit 1)
	ansible-lint playbooks/*.yml

# Clean temporary files
clean:
	@echo "Cleaning temporary files..."
	@find . -name "*.retry" -delete
	@find . -name "*.log" -delete
	@rm -f deployment-info-*.txt
	@echo "✓ Cleanup complete"

# Dry run for development
dry-run-dev: check-env
	@echo "Performing dry run for development..."
	ansible-playbook playbooks/deploy-development.yml --check

# Show deployment info
info:
	@echo "Ansible Retail Deployment Information"
	@echo "======================================"
	@echo "Ansible version: $$(ansible --version | head -n1)"
	@echo "Python version: $$(python3 --version)"
	@echo "Current directory: $$(pwd)"
	@echo "Available environments: development, test, production"