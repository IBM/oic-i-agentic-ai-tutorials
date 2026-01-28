# 🚀 Deploy FastAPI App on IBM Code Engine from GitHub

This guide outlines how to deploy a FastAPI application to **IBM Code Engine** using source code from a **GitHub repository**. The deployment uses a Dockerfile-based strategy.

---
## 🧰 Prerequisites

- IBM Cloud account with a Code Engine instance
- GitHub repository with your project
- [SSH Key Setup to Connect GitHub to IBM Code Engine](./SSH_KEY_SETUP.md)
---
## 📁 Project Structure

```
Main_Folder/
├── server.py
├── requirements.txt
└── Dockerfile
```
<img width="2656" height="1428" alt="image" src="https://github.com/user-attachments/assets/e8a514fc-6c0a-401a-b7e5-73efa91d2f75" />


---

## 🧰 Prerequisites

- IBM Cloud account with Code Engine enabled
- GitHub repository with your project
- SSH key configured in GitHub and IBM Cloud
- Registry access (IBM Container Registry or other)

---

## 🛠️ Steps to Deploy

### 1. **Navigate to Code Engine**

- Go to [cloud.ibm.com](https://cloud.ibm.com)
- Choose your account with Code Engine
- Go to **Resource List** > **Containers** > **Code Engine**
- Click on your **Project** or create a new one
- Select **Applications** > **Create**

---

### 2. **Configure Build Source**

Choose “**Build container image from source code**” and click on “**Specify build details**”.
<img width="1728" height="989" alt="Screenshot 2026-01-16 at 2 08 51 PM" src="https://github.com/user-attachments/assets/fd2bdbd6-dc8a-485e-9318-7d0acd8d886e" />



#### **Source Tab**

- **Code repo URL**: Paste the GitHub repository URL that contains your application
- **SSH Secret**: `github-code-engine-ssh` — select the SSH key you configured to access the GitHub repository.
- **Branch name**: Enter the branch to build from (e.g., `main`)
- **Context directory**: Leave this empty, since all files are in the root folder of the repository


#### **Strategy Tab**

- **Strategy**: Select `Dockerfile`
- **Dockerfile**: Enter `Dockerfile`
- **Timeout (seconds)**: `10m`
- **Build resources**: `M (1 vCPU / 4 GB)`


#### **Output Tab**

- **Registry server**: Select your container registry (e.g., `private.us.icr.io`)
- **Registry secret**: Choose the registry secret (Code Engine managed secret)
- **Namespace**: Select from the available namespaces 
- **Repository (image name)**: Enter `MCP`
- **Tag**: Use `latest` or select an appropriate version tag

Click **Done**.

---

### 3 Resources & Scaling

#### Instance resources
- **CPU and memory**: 1 vCPU / 4 GB  
- **Ephemeral storage**: 4 GB  

#### Autoscaling – Instance scaling range
- **Minimum number of instances**: 1  
- **Maximum number of instances**: 1  


#### Autoscaling – Request concurrency and timing settings
- **Target concurrency**: 100  
- **Max concurrency**: 100  
- **Request timeout (seconds)**: 300  
- **Scale-down delay (seconds)**: 0  



---

### 4. **Domain Mapping**

- **Visibility**: Set to **Public**

---

### 5. **Optional Settings**

- **Environment variables**: Add any key-value pairs required
- **Image start command/args**: Set custom values if needed

---

### 6. **Create the Application**

click **Create** and wait for the status to show **Running**. After that, click **Application**.
<img width="3456" height="1882" alt="Screenshot 2026-01-16 at 2 40 08 PM" src="https://github.com/user-attachments/assets/cd87d127-a8ad-4159-b9f2-a063a5d39031" />
Then, right-click on the **Application link** and select **Copy Link Address**.
<img width="3456" height="1882" alt="Screenshot 2026-01-16 at 4 47 47 PM" src="https://github.com/user-attachments/assets/ff29d27a-e678-4f13-b27e-4b53c42f4f6f" />
- After that, add `mcp` as a suffix to the URL you copied using **Copy Link Address**.

**Example:**
- **Original URL**: `www.mcp.com`
- **Updated URL**: `www.mcp.com/mcp`



---

### Store MCP Server Endpoint

The **Updated URL** is the actual endpoint through which you can access the MCP tool.

Store this value securely as:

`MCP_SERVER_URL`

🔐 This URL will be required for future configurations and integrations.


