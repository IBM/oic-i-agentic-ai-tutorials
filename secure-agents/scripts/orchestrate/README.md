# Orchestrate Scripts

This directory contains scripts for managing Watson Orchestrate MCP (Model Context Protocol) connections.

## Setup

### Create a Virtual Environment

1. **Create a Python virtual environment:**
   ```bash
   python3.11 -m venv venv
   ```
   
   Note: This project requires Python >=3.11,<3.14

2. **Activate the virtual environment:**
   
   On macOS/Linux:
   ```bash
   source venv/bin/activate
   ```
   
   On Windows:
   ```bash
   venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

### Configure Environment Variables

1. **Copy the example environment file:**
   ```bash
   cp .env.example.sh .env.sh
   ```

2. **Edit `.env.sh` with your credentials:**
   - Replace all placeholder values (e.g., `<your-api-key>`) with your actual credentials
   - Obtain credentials from IBM Cloud Console and IBM Verify
   - Never commit `.env.sh` to version control (it's in `.gitignore`)

3. **Source the environment variables:**
   ```bash
   source .env.sh
   ```

## Available Scripts

### `create_wxo_keys.sh`
Creates a personal RSA public/private keypair and base64 encodes them together with the public key from watsonx orchestrate. 

**Usage:** <br>
Before executing the script check the following:
- you copied the public key coming from wxo to `/local/keys/wxo_public.pem`
- you are currently in the main folder of the repository

```bash
./scripts/orchestrate/create_wxo_keys.sh
```

The script will create and save your public and private key in `local/keys` folder. Additionally it will output the base64 encoded keys for your environment variables file. Please go ahead and copy them to your `.env` or `.env.production` file.

### `create_connection.sh`
Creates a new MCP connection in Watson Orchestrate.

**Usage:**
```bash
./create_connection.sh <orchestrate_environment>
```

**Arguments:**
- `orchestrate_environment` (required): The Orchestrate environment to activate (e.g., `my_orchestrate_environment`)

**Examples:**
```bash
./create_connection.sh my_orchestrate_environment
```

**Note:** The script will:
1. Activate the specified Orchestrate environment
2. Perform OAuth2 token exchange to obtain a valid access token
3. Configure connections for both `draft` and `live` environments
4. Set up credentials with the exchanged token

### `delete_connection.sh`
Deletes an existing MCP connection from Watson Orchestrate.

**Usage:**
```bash
./delete_connection.sh
```

## Configuration

All configuration is managed through environment variables in `.env.sh`. See `.env.example.sh` for detailed documentation of each variable.

### Key Configuration Parameters

- **Watson Orchestrate**: `SERVICE_INSTANCE`, `API_KEY`
- **OAuth2 Credentials**: `agent_app_secret`, `agent_app_client_id`, `app_secret`, `app_client_id`
- **IBM Verify**: `server_url`, `token_url`
- **Token Exchange**: `grant_type`, `subject_token`, `scope`

## Security Notes

- ⚠️ **Never commit `.env.sh`** - it contains sensitive credentials
- Keep your API keys and secrets secure
- Rotate credentials regularly
- Use different credentials for development and production environments

## Troubleshooting

If you encounter authentication errors:
1. Verify all credentials are correct in `.env.sh`
2. Ensure your API key has the necessary permissions
3. Check that your OAuth2 client IDs and secrets are valid
4. Verify the service instance URL is correct for your region

## Requirements

- Bash shell
- `curl` command-line tool
- Valid IBM Cloud and IBM Verify credentials
- Access to a Watson Orchestrate instance