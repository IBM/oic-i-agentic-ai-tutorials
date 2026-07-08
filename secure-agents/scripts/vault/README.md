# Vault Setup Scripts

This directory contains scripts for configuring HashiCorp Vault with MongoDB integration and JWT authentication.

## Overview

The setup configures Vault with:
- **Database Secrets Engine**: Dynamic MongoDB credentials
- **JWT Authentication**: Integration with IBM Verify OIDC
- **Identity Groups**: Role-based access control (readonly, readwrite)
- **ACL Policies**: Fine-grained permissions
- **Audit Logging**: Security compliance and monitoring

## Quick Start

### 1. Prerequisites

Ensure you have the following installed:
- HashiCorp Vault CLI
- `jq` (JSON processor)
- MongoDB running and accessible
- IBM Verify tenant configured

### 2. Configure Environment Variables

```bash
# Copy the example environment file
cp .env.vault.example .env.vault

# Edit with your values
vim .env.vault
```

Required variables:
- `VAULT_ADDR`: Your Vault server address
- `VAULT_TOKEN`: Vault authentication token
- `OIDC_DISCOVERY_URL`: IBM Verify OIDC discovery URL
- `BOUND_AUDIENCES`: Client ID from IBM Verify
- `MONGO_HOST`, `MONGO_PORT`, `MONGO_USERNAME`, `MONGO_PASSWORD`: MongoDB connection details

### 3. Run the Setup Script

```bash
# Source the environment file
source .env.vault

# Run the setup
./scripts/vault-setup.sh
```

### 4. Verify the Setup

The script automatically verifies all components. You can also manually test:

```bash
# Test JWT authentication (requires a valid JWT token)
vault write auth/jwt/login role=default jwt=$JWT_TOKEN

# Test credential generation
vault read database/creds/readonly
vault read database/creds/readwrite

# View audit logs
# For pod/container deployments, inspect container stdout instead of a file.
kubectl logs <vault-pod-name>
```

## Script Options

```bash
# Show help
./scripts/vault-setup.sh --help

# Skip verification step
./scripts/vault-setup.sh --skip-verification

# Dry run (show what would be done)
./scripts/vault-setup.sh --dry-run
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     MCP with user JWT Token                 │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Vault JWT Auth (jwt/)                     │
│  • Validates JWT with IBM Verify OIDC                        │
│  • Extracts groups claim                                     │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              Identity Groups (External)                      │
│  • readonly  → readonly policy                               │
│  • readwrite → readwrite policy                              │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    ACL Policies                              │
│  • readonly:  database/creds/readonly                        │
│  • readwrite: database/creds/readwrite                       │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              Database Secrets Engine                         │
│  • Generates dynamic MongoDB credentials                     │
│  • TTL: 1h (default), Max: 24h                              │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      MongoDB                                 │
│  • Database: test                                            │
│  • Roles: read, readWrite                                    │
└─────────────────────────────────────────────────────────────┘
```

## Components

### Database Secrets Engine

Manages dynamic MongoDB credentials with automatic rotation.

**Configuration:**
- Connection name: `docdb` (configurable via `VAULT_DB_CONNECTION_NAME`)
- Database: `test` (configurable via `MONGO_DATABASE`)
- Roles: `readonly`, `readwrite`

### JWT Authentication

Integrates with IBM Verify for OIDC-based authentication.

**Configuration:**
- Auth path: `jwt/`
- Role: `default`
- User claim: `preferred_username`
- Groups claim: `groups`

### Identity Groups

Maps JWT groups to Vault policies.

**Groups:**
- `readonly`: Read-only access to database credentials
- `readwrite`: Read-write access to database credentials

### ACL Policies

Define permissions for each group.

**Policies:**
- `readonly`: Can read `database/creds/readonly`
- `readwrite`: Can read `database/creds/readwrite`

### Audit Logging

Records all Vault operations for security compliance.

**Configuration:**
- Log sink: `stdout` for pod/container deployments (configurable via `VAULT_AUDIT_LOG_PATH`)
- Format: JSON

## Troubleshooting

### Common Issues

**1. "VAULT_ADDR not set"**
```bash
export VAULT_ADDR="http://localhost:8200"
```

**2. "Not authenticated to Vault"**
```bash
vault login
# Or set VAULT_TOKEN
export VAULT_TOKEN="your-token"
```

**3. "Cannot connect to MongoDB"**
- Verify MongoDB is running: `docker ps | grep mongodb`
- Check connection details in `.env.vault`
- Test connection: `mongosh mongodb://admin:secret@localhost:27017/admin`

**4. "JWT authentication failed"**
- Verify OIDC_DISCOVERY_URL is correct
- Check BOUND_AUDIENCES matches your client ID
- Ensure JWT token is valid and not expired

**5. "Database role creation failed"**
- Ensure database secrets engine is enabled
- Verify MongoDB connection is configured
- Check MongoDB admin credentials are correct

### Debug Mode

Enable verbose logging:
```bash
export VAULT_VERBOSE_OIDC_LOGGING=true
./scripts/vault-setup.sh
```

View audit logs:
```bash
kubectl logs <vault-pod-name> | jq
```

## Security Best Practices

1. **Never commit `.env.vault`** to version control
2. **Use strong passwords** for MongoDB
3. **Rotate credentials regularly**
4. **Monitor audit logs** for suspicious activity
5. **Use appropriate TTL values** for your security requirements
6. **Restrict Vault token permissions** to minimum required
7. **Enable TLS** for production Vault deployments
8. **Backup Vault data** regularly

## Integration with Python Code

The setup is designed to work with the `vault_client.py` module:

```python
from vault_client import get_mongodb_credentials

# Get readonly credentials
creds = get_mongodb_credentials(jwt_token, x_correlation_id, operation="read")

# Get readwrite credentials
creds = get_mongodb_credentials(jwt_token, x_correlation_id, operation="write")
```

## Files

- `vault-setup.sh`: Main setup script
- `.env.vault.example`: Environment variable template
- `view-vault-logs.sh`: Helper script to view audit logs
- `README.md`: This file

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review Vault logs: `vault audit list`
3. Check MongoDB logs: `docker logs mongodb`
4. Review the audit log stream: `kubectl logs <vault-pod-name>`

## References

- [HashiCorp Vault Documentation](https://www.vaultproject.io/docs)
- [MongoDB Database Plugin](https://www.vaultproject.io/docs/secrets/databases/mongodb)
- [JWT Auth Method](https://www.vaultproject.io/docs/auth/jwt)
- [IBM Verify Documentation](https://www.ibm.com/docs/en/security-verify)