# Okta OAuth 2.0 – On-Behalf-Of (OBO) Flow Setup

This repository documents the complete setup for **OAuth 2.0 SSO / IDP authentication using Okta**, including an **On-Behalf-Of (OBO) token exchange flow**.

This setup is typically used when:
- A **frontend (SPA)** authenticates a user via Okta
- A **backend service** securely calls APIs **on behalf of the authenticated user**

---

## Step 1.Sign Up for Okta Free Trial

1. Go to the [Okta Free Trial](https://www.okta.com/free-trial/workforce-identity/).
2. Provide the following details:
   - **First Name**
   - **Last Name**
   - **Work Email**
   - **Country / Region**
   - **Phone Number**
3. Click **Start Free Trial**.
4. You will receive an **activation email**:
   - Activate your account
   - Set a password
   - Complete **device setup** for verification

After setup, you will receive an Okta Admin URL similar to:

```
https://{okta_org}-admin.okta.com/admin/getting-started
```

**Example:**
```
https://trial-8712265-admin.okta.com/admin/getting-started
```
Go to the above URL and complete the setup process.

---

### Extract Okta Organization Details

From the Admin URL, extract the `okta_org` value and derive the Okta base URL.

**okta_org**

```
trial-8712265
```

**OKTA_BASE_URL**

```
https://{okta_org}.okta.com
```

**Example:**

```
https://trial-8712265.okta.com
```

🔐 **Important:** Store `OKTA_BASE_URL` securely.


---
## Step 2. Create Users and Configure Manager Attribute

In this setup, you need to create **exactly two users**:
- One user with **manager access**
- One user with **employee access**

---

### Add Custom User Attribute

**Directory → Profile Editor → All → User (default)**

1. Click **Add Attribute**
2. Configure the attribute:
   - **Data type:** Boolean
   - **Display name:** `is_manager`
   - **Variable name:** `is_manager`
3. Click **Save**

---

### Create Two Users

**Directory → People**

1. Click **Add Person**
2. Enter the following details:
   - **First name**
   - **Last name**
   - **Username**
   - **Primary email**
3. Click **Save**
4. Repeat the above steps to create a **second user**

---

### Assign Manager Access

**Directory → People**

1. Click on the **first user**
   - Go to the **Profile** tab → **Edit**
   - Set **is_manager** = `true` (Manager access)
   - Click **Save**

2. Click on the **second user**
   - Go to the **Profile** tab → **Edit**
   - Set **is_manager** = `false` (Employee access)
   - Click **Save**

---

This setup ensures that **one user has manager access and the other has employee access**.



## Step 3. Create OIDC Single-Page Application (Frontend)

This application handles **user login and SSO**.

### Steps

1. Go to **Admin Console → Applications → Applications**
2. Click **Create App Integration**
3. Select:
   - **Sign-in method:** OIDC – OpenID Connect
   - **Application type:** Single-Page Application
4. Click **Next**

### Configure Application Settings

- **App integration name:** `SPA WEB APPLICATION`
- **Grant types:**
  - [x] Authorization Code
  - [x] Refresh Token
- **Sign-in redirect URIs:**
  - Production: `https://yourdomain.com/your-chat-page/` (The URL endpoint where the webchat web application is hosted)
  - Local testing: `http://localhost:3000`
- **Sign-out redirect URIs:**
  - Production: `https://yourdomain.com/your-chat-page/` (The URL endpoint where the webchat web application is hosted)
  - Local testing: `http://localhost:3000`
- **Controlled access:** Allow everyone in your organization
- **Disable:** Enable immediate access with Federation Broker Mode
<img width="1078" height="1790" alt="image" src="https://github.com/user-attachments/assets/878426d8-4970-4564-bf28-f7705dddbf24" />

Click **Save**.

### Store Application Details

After saving the application, copy the **Client ID** and store it securely as:

**SPA_CLIENT_ID**


---

## Step 4. Assign Users to SPA Application

1. Go to **Applications → Applications → SPA WEB APPLICATION**
2. Open the **Assignments** tab.
3. Click **Assign → Assign to People**.
4. Add users who should access the webchat.

---

## Step 5. Configure Authorization Server for SPA

1. Go to **Security → API → Authorization Servers**
2. Open the **Default** server
<img width="2074" height="732" alt="image" src="https://github.com/user-attachments/assets/792cfe5e-2dc6-427a-941d-e7ec85cbbf08" />

3. Go to the **Claims** tab → click **Add Claim**
   - **Name:** `is_manager`
   - **Include in token type:** `ID Token` (Always)
   - **Value type:** `Expression`
   - **Value:** `user.is_manager`
   <img width="554" height="487" alt="Screenshot 2026-01-09 at 12 06 52 AM" src="https://github.com/user-attachments/assets/2f32c532-22c9-4ec7-ba01-db3365211db4" />


4. Go to **Access Policies** tab → **Add Policy**
   - **Name:** `SPA Access Policy`
   - **Description:** `SPA Access Policy`
   - **Assign to:** `SPA WEB APPLICATION`
   - Click **Create Policy**
<img width="1618" height="1248" alt="image" src="https://github.com/user-attachments/assets/81ec4069-5e36-43b2-9bc3-c509f34f165c" />


## Step 6. Create SPA Access Policy Rule

1. In the SPA access policy, click **Add Rule**
   <img width="1105" height="811" alt="Screenshot 2026-01-04 at 1 32 26 AM" src="https://github.com/user-attachments/assets/5234e0f4-c440-4534-a662-5ac002c0f1c2" />

2. Configure:
   - **Rule Name:** `SPA Rule`
   - **Grant type:**
      - [x] Authorization Code
   - **User:** Any user assigned the app
   - **Scopes requested:**
     - `openid`
     - `profile`
     - `email`
   - **Access token lifetime:** 5 minutes
   - **Refresh token lifetime:** 90 days
<img width="1296" height="1876" alt="image" src="https://github.com/user-attachments/assets/69fc70d2-c6f0-4f35-96bf-b2ce51abf658" />
   - Click **Create Rule**

---

## Step 7. Create API Service Application (Backend)

This application is used for **token exchange (OBO)** and backend API access.

### Steps

1. Go to **Admin Console → Applications → Applications**
2. Click **Create App Integration**
3. Select:
   - **Sign-in method:** API Services
4. Click **Next**

### Configure Application Settings

- **App integration name:** `API Services Application`
- **Client authentication:** 
   - [x] Client secret
- Click **Save**
### Store Application Credentials

After saving the application, copy and securely store the following values:

- **Client ID** → `API_SERVICES_CLIENT_ID`
- **Client Secret** → `API_SERVICES_CLIENT_SECRET`
- Edit **General Settings**
   - In **Proof of Possession**
     - Uncheck **Require Demonstrating Proof of Possession (DPoP) header in token requests**
   - In **Grant types**, select **Client Credentials**
      - **Click Advanced**, Select **Token Exchange**
   - Click **save**
  <img width="1360" height="1120" alt="image" src="https://github.com/user-attachments/assets/afcba6bb-c7f0-4451-8432-8dc851db29ef" />



---

## Step 8. Configure Authorization Server for API Services

1. Go to **Security → API → Authorization Servers**
2. Open the **Default** server  
3. Go to **Access Policies** tab → **Add Policy**
   - **Name:** `API Services Access Policy`
   - **Description:** `API Services Access Policy`
   - **Assign to:** `API Services Application`
     <img width="1360" height="876" alt="image" src="https://github.com/user-attachments/assets/38290aa3-52fb-4dd1-ab41-dbc29cec40fa" />
   - click **Create Policy**

---

## Step 9. Add Custom Scope

1. Go to the **Scopes** tab
2. Click **Add Scope**
   - **Name:** `mcp.read`
   - **Display phrase:** `MCP Read`
   - click **Create** 
<img width="1300" height="1328" alt="image" src="https://github.com/user-attachments/assets/c67d662d-87b9-4cd3-95c1-6b5bf5b977bd" />



---

## Step 10. Create API Services Policy Rule
<img width="2002" height="1432" alt="Screenshot 2026-01-08 at 10 39 44 PM" src="https://github.com/user-attachments/assets/5539fd14-545a-4565-950b-c7b9dc6c6072" />

1. Go to the **Access Policies** tab → under the **API Services access policy**, click **Add Rule**.
2. Configure:
   - **Rule Name:** `API Services Rule`
   - **Grant types:**
     - Client Credentials
     - Authorization Code
     - Device Authorization
     - Token Exchange (Advanced → Non-interactive grants)
   - **User**: Any user assigned to the app
   - **Scopes requested:**
     - `mcp.read`
   - **Access token lifetime:** 5 minutes
   - **Refresh token lifetime:** 90 days
   - <img width="1062" height="1782" alt="image (1)" src="https://github.com/user-attachments/assets/f1cfdbbf-9c58-4170-829b-fddd875e3cae" />


---

## Okta Setup Complete

✅ Your Okta setup is now ready. Please store the following values securely, as they will be required for future configurations and integrations.

### From Step 1
- `OKTA_BASE_URL` 

### From Step 3
- `SPA_CLIENT_ID`

### From Step 7
- `API_SERVICES_CLIENT_ID`
- `API_SERVICES_CLIENT_SECRET`





