# Ansible-Based Retail Application Deployment for OpenShift

This repository contains production-ready Ansible automation for deploying the Retail application on OpenShift clusters. It replaces the previous script-based deployment approach with a robust, maintainable, and reusable Ansible solution.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Usage](#usage)
- [Multi-Environment Support](#multi-environment-support)
- [Roles Description](#roles-description)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

## Overview

This Ansible automation handles the complete deployment lifecycle of the Retail application, including:

- System dependencies installation (Podman, Java 11, OpenShift CLI, JMeter)
- Application source code management
- Container image building and pushing to Docker Hub
- OpenShift cluster authentication and namespace setup
- Kubernetes manifest updates with environment-specific configurations
- Application deployment (PostgreSQL, Backend, Frontend)
- Database seed data loading
- Frontend rebuild with dynamic backend route configuration

## Features

✅ **Multi-Environment Support**: Deploy to Development, Test, or Production with environment-specific configurations  
✅ **Idempotent Operations**: Safe to run multiple times without side effects  
✅ **Modular Design**: Reusable roles for each deployment phase  
✅ **Dynamic Configuration**: Automatic backend route discovery and frontend reconfiguration  
✅ **Comprehensive Logging**: Detailed output and deployment summaries  
✅ **Error Handling**: Robust error checking and validation at each step  
✅ **Resource Management**: Environment-specific resource limits and replica counts  
✅ **Production-Ready**: Includes health checks, HPA, and proper security configurations  

## Prerequisites

### System Requirements

- RHEL/CentOS/Fedora-based system (for package management)
- Root or sudo access
- Internet connectivity for downloading dependencies and images

### Required Software (Installed Automatically)

The automation will install these if not present:
- Podman
- Java 11 (OpenJDK)
- OpenShift CLI (oc)
- Apache JMeter
- Git, curl, wget, unzip

### Required Credentials

You must have:
1. **OpenShift Cluster Access**
   - OpenShift cluster URL
   - Authentication token with appropriate permissions

2. **Docker Hub Account**
   - Docker Hub username
   - Docker Hub password or access token

## Project Structure

```
ansible-retail-bob/
├── ansible.cfg                      # Ansible configuration
├── README.md                        # This file
├── inventories/                     # Environment inventories
│   ├── development/
│   │   └── hosts                    # Development inventory
│   ├── test/
│   │   └── hosts                    # Test inventory
│   └── production/
│       └── hosts                    # Production inventory
├── group_vars/                      # Environment-specific variables
│   ├── development.yml              # Development configuration
│   ├── test.yml                     # Test configuration
│   └── production.yml               # Production configuration
├── playbooks/                       # Ansible playbooks
│   ├── deploy.yml                   # Main deployment playbook
│   ├── deploy-development.yml       # Development deployment
│   ├── deploy-test.yml              # Test deployment
│   └── deploy-production.yml        # Production deployment
└── roles/                           # Ansible roles
    ├── system_dependencies/         # Install system dependencies
    ├── app_source/                  # Clone application source
    ├── container_images/            # Build and push images
    ├── openshift_setup/             # OpenShift authentication
    ├── k8s_manifests/               # Update Kubernetes manifests
    ├── app_deployment/              # Deploy application
    ├── database_seed/               # Load database seed data
    └── frontend_rebuild/            # Rebuild frontend with backend URL
```

## Configuration

### Environment Variables

Set the following environment variables before running the playbook:

```bash
export OC_TOKEN="your-openshift-token"
export DOCKER_USERNAME="your-dockerhub-username"
export DOCKER_PASSWORD="your-dockerhub-password"
```

For production deployments, also set:

```bash
export JWT_SECRET="your-production-jwt-secret"
export DB_PASSWORD="your-production-db-password"
```

### Environment-Specific Configuration

Edit the appropriate file in `group_vars/` to customize your deployment:

- `group_vars/development.yml` - Development environment settings
- `group_vars/test.yml` - Test environment settings
- `group_vars/production.yml` - Production environment settings

Key configuration parameters:

```yaml
# Environment and namespace
environment: development
namespace: retail-dev

# OpenShift cluster
openshift_server: "https://api.your-cluster.example.com:6443"

# Image tags
backend_image_tag: "1.0.0-dev"
frontend_image_tag: "1.0.0-dev"

# Replica counts
backend_replicas: 1
frontend_replicas: 1

# Resource limits
backend_cpu_request: "50m"
backend_memory_request: "64Mi"
backend_cpu_limit: "250m"
backend_memory_limit: "256Mi"
```

## Usage

### Quick Start

1. **Clone this repository:**
   ```bash
   git clone <repository-url>
   cd ansible-retail-bob
   ```

2. **Set environment variables:**
   ```bash
   export OC_TOKEN="your-openshift-token"
   export DOCKER_USERNAME="your-dockerhub-username"
   export DOCKER_PASSWORD="your-dockerhub-password"
   ```

3. **Update configuration:**
   Edit `group_vars/development.yml` with your OpenShift cluster URL and other settings.

4. **Run the deployment:**
   ```bash
   ansible-playbook playbooks/deploy-development.yml
   ```

### Deployment Commands

#### Development Environment
```bash
ansible-playbook playbooks/deploy-development.yml
```

#### Test Environment
```bash
ansible-playbook -i inventories/test/hosts playbooks/deploy-test.yml
```

#### Production Environment
```bash
ansible-playbook -i inventories/production/hosts playbooks/deploy-production.yml
```

### Using Tags

Run specific parts of the deployment:

```bash
# Only install dependencies
ansible-playbook playbooks/deploy-development.yml --tags dependencies

# Only build and push images
ansible-playbook playbooks/deploy-development.yml --tags images

# Only deploy application (skip setup)
ansible-playbook playbooks/deploy-development.yml --tags deploy

# Skip database seeding
ansible-playbook playbooks/deploy-development.yml --skip-tags seed
```

Available tags:
- `dependencies` - System dependencies installation
- `setup` - Setup tasks (dependencies, source, OpenShift)
- `source` - Application source code management
- `images` - Container image building
- `build` - Build-related tasks
- `openshift` - OpenShift authentication and setup
- `manifests` - Kubernetes manifest updates
- `config` - Configuration tasks
- `deploy` - Application deployment
- `application` - Application-specific tasks
- `database` - Database operations
- `seed` - Database seed data loading
- `frontend` - Frontend operations
- `rebuild` - Frontend rebuild

## Multi-Environment Support

This automation supports multiple environments with the same codebase. Differences are managed through:

1. **Inventory Files**: Separate inventory for each environment
2. **Group Variables**: Environment-specific configurations in `group_vars/`
3. **Environment-Specific Playbooks**: Convenience playbooks for each environment

### Environment Differences

| Feature | Development | Test | Production |
|---------|-------------|------|------------|
| Namespace | retail-dev | retail-test | retail-prod |
| Replicas | 1 | 2 | 3 |
| CPU Request | 50m | 100m | 200m |
| Memory Request | 64Mi | 128Mi | 256Mi |
| CPU Limit | 250m | 500m | 1000m |
| Memory Limit | 256Mi | 512Mi | 1Gi |
| Image Tag | 1.0.0-dev | 1.0.0-test | 1.0.0 |

### Adding a New Environment

1. Create inventory file: `inventories/staging/hosts`
2. Create variables file: `group_vars/staging.yml`
3. Create playbook: `playbooks/deploy-staging.yml`
4. Update configurations as needed

## Roles Description

### system_dependencies
Installs all required system dependencies including Podman, Java 11, OpenShift CLI, and Apache JMeter.

### app_source
Clones the Retail application source code from GitHub and verifies the repository structure.

### container_images
Builds container images for backend, frontend, and PostgreSQL, then pushes them to Docker Hub.

### openshift_setup
Authenticates to the OpenShift cluster, creates/verifies the namespace, and sets up Docker Hub image pull secrets.

### k8s_manifests
Updates Kubernetes manifests with environment-specific values including namespace, image references, and resource limits.

### app_deployment
Deploys all application components to OpenShift including PostgreSQL, backend, frontend, services, routes, and HPAs.

### database_seed
Loads the database seed data (full_dump.sql) into the PostgreSQL database.

### frontend_rebuild
Rebuilds the frontend container image with the correct backend route URL and redeploys it.

## Troubleshooting

### Common Issues

#### 1. Authentication Failures

**Problem**: OpenShift login fails
```
Solution: Verify your OC_TOKEN is valid and has not expired
```

#### 2. Image Push Failures

**Problem**: Cannot push images to Docker Hub
```
Solution: 
- Verify DOCKER_USERNAME and DOCKER_PASSWORD are correct
- Check Docker Hub repository exists and you have push permissions
- Ensure you're logged in: podman login docker.io
```

#### 3. Pod Not Starting

**Problem**: Pods remain in Pending or CrashLoopBackOff state
```
Solution:
- Check pod logs: oc logs <pod-name> -n <namespace>
- Check events: oc get events -n <namespace>
- Verify image pull secret: oc get secret dockerhub-secret -n <namespace>
- Check resource quotas: oc describe quota -n <namespace>
```

#### 4. Database Connection Issues

**Problem**: Backend cannot connect to database
```
Solution:
- Verify PostgreSQL pod is running: oc get pods -n <namespace>
- Check PostgreSQL service: oc get svc retail-postgres -n <namespace>
- Verify database credentials in backend deployment
- Check backend logs for connection errors
```

#### 5. Frontend Cannot Reach Backend

**Problem**: Frontend shows API connection errors
```
Solution:
- Verify backend route exists: oc get route retail-backend -n <namespace>
- Check if frontend was rebuilt with correct backend URL
- Verify backend pods are ready and responding
- Check CORS configuration in backend
```

### Debug Mode

Run with verbose output:
```bash
ansible-playbook playbooks/deploy-development.yml -vvv
```

### Checking Deployment Status

```bash
# Check all pods
oc get pods -n retail-dev

# Check services
oc get svc -n retail-dev

# Check routes
oc get routes -n retail-dev

# Check pod logs
oc logs -f deployment/retail-backend -n retail-dev
oc logs -f deployment/retail-frontend -n retail-dev

# Check pod details
oc describe pod <pod-name> -n retail-dev
```

### Cleanup

To remove the deployment:
```bash
# Delete all resources in namespace
oc delete all --all -n retail-dev

# Delete namespace
oc delete namespace retail-dev
```

## Best Practices

1. **Always test in development first** before deploying to production
2. **Use version control** for configuration changes
3. **Keep secrets secure** - never commit credentials to Git
4. **Monitor deployments** - check logs and metrics after deployment
5. **Backup production data** before major updates
6. **Use tags** to run specific parts of the deployment during troubleshooting
7. **Document changes** to environment-specific configurations

## Contributing

Contributions are welcome! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly in development environment
5. Submit a pull request with detailed description

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:
- Create an issue in the GitHub repository
- Contact the DevOps team
- Check the troubleshooting section above

## Acknowledgments

- Original deployment script by the Retail App team
- OpenShift documentation and best practices
- Ansible community for excellent modules and examples