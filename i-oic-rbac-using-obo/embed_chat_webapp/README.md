# 💬 Embed Chat WebApp

A **Next.js** web application that embeds the **watsonx Orchestrate** chat widget with **Okta SSO** authentication. Users log in via Okta, and the app securely generates a signed JWT (RS256) to authenticate against the Orchestrate embedded chat API using the **On-Behalf-Of (OBO)** flow.

---

## 📁 Project Structure

```
embed_chat_webapp/
├── app/
│   ├── api/
│   │   └── encrypt/
│   │       └── route.js        # Server-side API route – builds & signs the JWT (RS256)
│   ├── layout.js               # Root layout
│   └── page.js                 # Main page – Okta login + Orchestrate chat embed
├── config.js                   # Centralised app configuration (reads from .env)
├── public/
│   └── hr-banner.png           # Background image
├── .env                        # Environment variables (see below)
├── Dockerfile                  # Multi-stage Docker build
├── package.json
└── README.md
```

---

## ⚙️ How It Works

1. **Okta Authentication** – The client-side Okta Auth JS SDK redirects the user to Okta for login and retrieves an access token + ID token.
2. **JWT Generation** – The app calls an internal Next.js API route (`/api/encrypt`) which:
   - Decodes the Okta access token.
   - Encrypts the SSO token with IBM's public key (RSA).
   - Signs a JWT with the client's private key (RS256).
   - Includes user profile context in the JWT payload.
3. **Orchestrate Chat Embed** – The signed JWT is passed to the watsonx Orchestrate chat loader script, which renders the embedded chat widget.

---

## 🚀 Getting Started

### 1. Navigate to the web app directory

```bash
cd embed_chat_webapp
```

### 2. Install dependencies

```bash
npm install && npm install node-rsa
```

### 3. Start the app

```bash
npm run dev
```

### 4. Open in browser

```
http://localhost:3000
```

The Embed Chat WebApp should now be running successfully. You will be redirected to Okta for login, and after authentication the watsonx Orchestrate chat widget will appear.

---

## 🔍 Understanding the Token Flow

If you right-click on the UI and select **Inspect**, then go to the **Network** tab, you can see that the **token** is issued by the Okta IdP.
<img width="3370" height="1792" alt="io" src="https://github.com/user-attachments/assets/64c177d3-ac31-4ec4-9eeb-579a504081d8" />

The response contains both an `access_token` and an `id_token`.

- The `access_token` is passed to the Orchestrate Connection Manager as the `sso_token`, allowing the agent to access the secured MCP tool.
- The `id_token` is decoded to extract user information, such as whether the user is a manager.

## Verifying the id_token

1. Copy the `id_token` from the response.
2. Paste it into https://www.jwt.io/.
3. View the decoded JWT payload.
4. Look for a claim such as `is_manager`.
<img width="1447" height="933" alt="Screenshot 2026-02-13 at 8 23 10 PM" src="https://github.com/user-attachments/assets/63d28cf0-865c-4c13-9147-7589b95142b4" />

Based on the value of the `is_manager` claim, we can determine whether the user is a manager.

The decoded information from the `id_token` is then sent to Orchestrate as a context variable, which is used for role-based access control (RBAC) and workflow decision-making.
