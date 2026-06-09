# watsonx Orchestrate Security Configurator Workspace

A high-density, professional configuration workspace for watsonx Orchestrate (WXO). This tool streamlines the process of enabling security, generating JWTs, and testing the embedded chat agent in a real-time, side-by-side preview environment.

![Workspace Preview](https://github.ibm.com/user-attachments/assets/75eb39f4-e18d-46bb-8f7b-89b58c3a322d)

## 🚀 Workspace Features

- **Side-by-Side Dashboard**: A strict 50/50 split layout that keeps your configuration settings and live agent preview visible at all times.
- **IBM Carbon Branding**: Designed with authentic IBM Blue accents and Carbon typography for a premium, native feel.
- **Automated Security Rotation**: Generate RSA-4096 key pairs, register them via the WXO API, and activate security in one click.
- **Live Agent Injection**: Launch your WXO agent directly into the workspace with valid security tokens and custom context variables.
- **Multi-Platform Support**: Tailored configurations for both **IBM Cloud SaaS** and **AWS** deployments.
- **Smart Script Parsing**: Automatically extracts configuration details from WXO script tags, handling smart quotes and hidden characters.

## 📁 File Structure

| File | Role |
|:---|:---|
| `server.js` | **Backend Engine**: Handles RSA key generation and RS-256 JWT signing (Port 3001). |
| `index.html` | **Main Workspace**: The primary high-density configuration interface. |
| `chat.html` | **Preview Frame**: The isolated environment where the WXO agent is loaded. |

## 🛠️ Quick Start

### 1. Launch the Backend
The configurator requires a local server to handle secure cryptographic operations that browsers cannot perform natively.

```bash
# Install dependencies
npm install

# Start the server
node server.js
```

### 2. Open the Workspace
Open **`index.html`** in your preferred browser.

### 3. Configure & Launch
1. **Paste your WXO Script**: The tool will automatically parse your Agent ID and Region.
2. **Setup Security**: Choose to auto-generate keys (requires API Key) or provide your own.
3. **Launch**: Click **Setup & Launch Agent** to see your agent appear in the right-hand preview pane.

## 🔐 Security & Privacy

- **Local-Only**: All private keys and API secrets are processed locally. No sensitive data is stored on external servers other than your own WXO instance.
- **Secure Proxying**: The Node.js backend acts as a secure proxy for IBM API calls, ensuring your API keys never touch the browser's network tab directly.
- **Standard Compliance**: Uses RS-256 for JWT signing and supports RSA-OAEP for payload encryption as per IBM security standards.

---
*Developed for the IBM watsonx Orchestrate ecosystem.*
