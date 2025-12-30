# Dependabot Setup Guide

## What's Been Configured

### 1. Dependabot Configuration ([dependabot.yml](dependabot.yml))
- ✅ Monitors Python, npm, and Docker dependencies
- ✅ Weekly checks for most projects
- ✅ **Daily** checks for `siri-watsonx-orchestrate` (has critical vulnerabilities)
- ✅ Groups minor/patch updates to reduce PR noise
- ✅ Security updates prioritized

### 2. Auto-Merge Workflow ([workflows/dependabot-auto-merge.yml](workflows/dependabot-auto-merge.yml))
- ✅ Automatically approves and merges security patch updates
- ✅ Only runs for Dependabot PRs
- ✅ Requires passing CI checks before merge

## Next Steps - Action Required

### Immediate (Fix Current Vulnerabilities)

Your existing security alerts **won't be automatically fixed** by this configuration. You need to manually address them:

#### Critical Priority 🔴
1. **LangChain serialization injection** - `siri-watsonx-orchestrate/requirements.txt`
   ```bash
   cd siri-watsonx-orchestrate
   pip install --upgrade langchain-core
   ```

#### High Priority 🟠
2. **urllib3** vulnerabilities (2 issues) - `siri-watsonx-orchestrate/requirements.txt`
3. **nbconvert** code execution - `siri-watsonx-orchestrate/requirements.txt`
4. **FastMCP** vulnerabilities (3 issues) - `confluent-agents/requirements.txt`
5. **Starlette DoS** - `siri-watsonx-orchestrate/requirements.txt`

#### Moderate Priority 🟡
6. **requests** credential leak (2 instances)
7. **marshmallow** DoS
8. **mdast-util-to-hast** XSS - `i-oic-integrate-headless-ai-agent/frontend_code/package-lock.json`

### Commands to Fix

#### Option 1: Manual Fix (Recommended for understanding what changes)
```bash
# For siri-watsonx-orchestrate
cd siri-watsonx-orchestrate
pip install --upgrade langchain-core urllib3 nbconvert starlette marshmallow
pip freeze > requirements.txt

# For confluent-agents
cd ../confluent-agents
pip install --upgrade fastmcp requests
pip freeze > requirements.txt

# For i-oic-confluent
cd ../i-oic-confluent
pip install --upgrade requests
pip freeze > requirements.txt

# For frontend
cd ../i-oic-integrate-headless-ai-agent/frontend_code
npm audit fix
```

#### Option 2: Let Dependabot Create PRs
1. Commit and push these configuration files
2. Wait 1-2 hours for Dependabot to scan
3. Review and merge the PRs it creates
4. Security patches will auto-merge (if CI passes)

### After Pushing This Config

1. **Push to GitHub**:
   ```bash
   git add .github/
   git commit -m "Configure Dependabot with auto-merge for security updates"
   git push
   ```

2. **Enable Auto-Merge** (if not enabled):
   - Go to Settings > Code and automation > Pull Requests
   - Check "Allow auto-merge"

3. **Monitor**:
   - Check Security tab for alerts
   - Review Dependabot PRs in the Pull Requests tab
   - Security patches will merge automatically after CI passes

## What This Covers

### ✅ Covered Now
- All Python projects with `requirements.txt`
- Frontend npm dependencies
- Docker base images
- Future security vulnerabilities (auto-PRs)

### ⚠️ Not Covered (Manual Management)
- Nested/deep subdirectories (e.g., `_temp/`)
- Git submodules (if any)
- Binary dependencies
- System packages

## Manual Trigger Options

### Option 1: GitHub Web UI (Easiest) ⭐
1. Go to your repo on GitHub
2. Click **Insights** → **Dependency graph** → **Dependabot**
3. Click **"Check for updates"** button
4. This triggers an immediate scan

### Option 2: GitHub Actions Workflow
1. Go to **Actions** tab
2. Select **"Trigger Dependabot"** workflow
3. Click **"Run workflow"**
4. This shows you where to manually trigger updates

### Option 3: Command Line Script
```bash
# First, create a GitHub token at: https://github.com/settings/tokens
# Required scopes: repo, security_events

.github/scripts/trigger-dependabot.sh YOUR_GITHUB_TOKEN
```

### Option 4: Direct URL
Visit: `https://github.com/YOUR_USERNAME/oic-i-agentic-ai-tutorials/network/updates`

## Troubleshooting

### Dependabot Not Running?
- Ensure the config is in `.github/dependabot.yml`
- Check you have admin access to the repo
- Verify the YAML syntax is valid
- Try manually triggering (see above)

### PRs Not Auto-Merging?
- Enable auto-merge in repo settings
- Ensure required checks are passing
- Check workflow permissions in Settings > Actions

### Too Many PRs?
- Adjust `open-pull-requests-limit` in config
- Change schedule from `daily` to `weekly`
- Add more specific `ignore` rules

## Customization

### Ignore Specific Dependencies
```yaml
ignore:
  - dependency-name: "package-name"
    versions: ["1.x", "2.x"]
```

### Change Schedule
```yaml
schedule:
  interval: "monthly"  # Options: daily, weekly, monthly
  day: "monday"
  time: "09:00"
  timezone: "America/New_York"
```

### Disable Auto-Merge
Remove or comment out the workflow file at:
`.github/workflows/dependabot-auto-merge.yml`

## Resources

- [Dependabot Documentation](https://docs.github.com/en/code-security/dependabot)
- [Configuration Options](https://docs.github.com/en/code-security/dependabot/dependabot-version-updates/configuration-options-for-the-dependabot.yml-file)
- [Security Alerts](https://docs.github.com/en/code-security/dependabot/dependabot-alerts/about-dependabot-alerts)
