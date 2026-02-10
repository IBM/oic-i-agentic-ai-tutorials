# Quick Start Guide

This guide will help you deploy the Retail application to OpenShift in minutes.

## Prerequisites Checklist

- [ ] RHEL/CentOS/Fedora system with root/sudo access
- [ ] OpenShift cluster access (URL and token)
- [ ] Docker Hub account (username and password)
- [ ] Internet connectivity

## Step-by-Step Deployment

### 1. Get Your OpenShift Token

Login to your OpenShift web console and copy your login token:

```bash
# Click on your username in top-right corner
# Select "Copy login command"
# Click "Display Token"
# Copy the token value
```

### 2. Set Environment Variables

```bash
export OC_TOKEN="sha256~your-token-here"
export DOCKER_USERNAME="your-dockerhub-username"
export DOCKER_PASSWORD="your-dockerhub-password"
```

### 3. Update Configuration

Edit `group_vars/development.yml`:

```yaml
openshift_server: "https://api.your-cluster.example.com:6443"
namespace: retail-dev
```

### 4. Run Deployment

```bash
# Make sure you're in the project directory
cd ansible-retail-bob

# Run the deployment
ansible-playbook playbooks/deploy-development.yml
```

### 5. Access Your Application

After successful deployment, you'll see output like:

```
Frontend URL: https://retail-frontend-retail-dev.apps.your-cluster.example.com
Backend URL: https://retail-backend-retail-dev.apps.your-cluster.example.com
```

Open the Frontend URL in your browser to access the application.

## Verification

Check that everything is running:

```bash
# Check pods
oc get pods -n retail-dev

# Expected output:
# NAME                              READY   STATUS    RESTARTS   AGE
# retail-backend-xxxxx-xxxxx        1/1     Running   0          5m
# retail-frontend-xxxxx-xxxxx       1/1     Running   0          5m
# retail-postgres-xxxxx-xxxxx       1/1     Running   0          5m

# Check routes
oc get routes -n retail-dev
```

## Common First-Time Issues

### Issue: "OC_TOKEN not set"
**Solution**: Make sure you exported the environment variables in your current shell session.

### Issue: "Cannot push to Docker Hub"
**Solution**: 
1. Verify your Docker Hub credentials
2. Make sure the repository exists or you have permission to create it
3. Try logging in manually: `podman login docker.io`

### Issue: "Namespace already exists"
**Solution**: This is normal if you're re-deploying. The playbook will use the existing namespace.

## Next Steps

1. **Explore the Application**: Navigate through the frontend interface
2. **Check Logs**: `oc logs -f deployment/retail-backend -n retail-dev`
3. **Monitor Resources**: Use OpenShift web console to view metrics
4. **Deploy to Test**: Once comfortable, deploy to test environment

## Getting Help

- Check the main [README.md](README.md) for detailed documentation
- Review the [Troubleshooting](README.md#troubleshooting) section
- Check pod logs for specific errors

## Cleanup

To remove the deployment:

```bash
oc delete namespace retail-dev
```

## Deploy to Other Environments

### Test Environment
```bash
ansible-playbook -i inventories/test/hosts playbooks/deploy-test.yml
```

### Production Environment
```bash
# Set production secrets first
export JWT_SECRET="your-production-jwt-secret"
export DB_PASSWORD="your-production-db-password"

# Deploy
ansible-playbook -i inventories/production/hosts playbooks/deploy-production.yml
```

---

**Deployment Time**: Approximately 10-15 minutes for first-time deployment

**Questions?** Check the main README.md or create an issue in the repository.