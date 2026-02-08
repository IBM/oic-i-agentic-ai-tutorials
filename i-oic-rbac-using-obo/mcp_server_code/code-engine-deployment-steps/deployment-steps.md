# 🚀 Deploy FastAPI App on IBM Code Engine from GitHub

This guide outlines how to deploy a FastAPI application to **IBM Code Engine** using source code from a **GitHub repository**. The deployment uses a Dockerfile-based strategy.

---

## 🧰 Prerequisites

- IBM Cloud account with a Code Engine instance
- Access to GitHub (IBM GitHub)
- SSH key configured in GitHub and IBM Cloud  
  👉 [SSH Key Setup to Connect GitHub to IBM Code Engine](./ssh-key-setup.md)
- Container registry access (IBM Container Registry or other)

---
> ⚠️ **Important**
>
> If you do **not** complete the  
> [SSH Key Setup to Connect GitHub to IBM Code Engine](./ssh-key-setup.md),  
> IBM Cloud Code Engine will **not be able to pull the source code from GitHub**, and the deployment will fail.


## 📦 Prepare the GitHub Repository

Clone the source repository using the command below:

```bash
git clone https://github.com/IBM/oic-i-agentic-ai-tutorials.git
```

After cloning, navigate to the **`i-oic-rbac-using-obo`** directory. All materials related to this use case are available there.

Inside the **`mcp_server_code`** folder, you will find the following files:
- `server.py`
- `requirements.txt`
- `Dockerfile`

Next, create a new GitHub repository using:  
https://github.ibm.com/new  

While creating the repository:
- Set the **repository name** to **`mcp_server_code`**
- Upload the following files as the repository contents:
  - `server.py`
  - `requirements.txt`
  - `Dockerfile`

This repository will later be used by **IBM Cloud Code Engine** to pull the source code and deploy the MCP server.

---

## 📁 Project Structure

```
mcp_server_code/
├── server.py
├── requirements.txt
└── Dockerfile
```
<img width="2396" height="1256" alt="image (27)" src="https://github.com/user-attachments/assets/a2c3321e-eae7-4868-969a-de964eb3202f" />

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
Give `Name` as `mcp_server`

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
- **Original URL**: `https://mcp.example.cloud/`
- **Updated URL**: `https://mcp.example.cloud/mcp`



---

### Store MCP Server Endpoint

The **Updated URL** is the actual endpoint through which you can access the MCP tool.

Store this value securely as:

`MCP_SERVER_URL`

🔐 This URL will be required for future configurations and integrations.
