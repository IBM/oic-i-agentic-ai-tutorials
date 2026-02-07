# Connecting GitHub to IBM Code Engine

_All commands below are to be run in your terminal (e.g., Terminal on macOS)._  
_Ensure you're in your home directory unless specified otherwise._

---

## 🔐 STEP 1: Generate SSH Key Pair

```bash
ssh-keygen -t rsa -b 4096 -m PEM -f example-jwtRS256.key
```

- You’ll be prompted to enter a passphrase (optional).
- This will create two files:
  - `example-jwtRS256.key` (Private Key)
  - `example-jwtRS256.key.pub` (Public Key)

---

## 📂 STEP 2: Navigate to Home Directory and Verify Files

```bash
cd ~
ls -ltra
```

- Confirm that both `example-jwtRS256.key` and `example-jwtRS256.key.pub` are listed.

---

## 📄 STEP 3: View the Private Key

```bash
cat example-jwtRS256.key
```

- Copy the full contents of this file when prompted during IBM Code Engine configuration.

---

## 📄 STEP 4: View the Public Key

```bash
cat example-jwtRS256.key.pub
```

- Copy the public key to be added to GitHub Enterprise.

---

## ☁️ STEP 5: Configure Secret in IBM Code Engine

1. Visit [IBM Cloud](https://cloud.ibm.com).
2. Choose your account and navigate to **Resource List**.
<img width="1728" height="992" alt="Screenshot 2026-01-16 at 12 10 13 AM" src="https://github.com/user-attachments/assets/ec6ab116-05cf-4222-afd4-4b4e5f33d976" />
3. Under **Containers**, select **Code Engine**.
<img width="1728" height="992" alt="Screenshot 2026-01-16 at 12 11 38 AM" src="https://github.com/user-attachments/assets/70cc417f-9060-4fe6-8284-b0f036f3854c" />

4. Click on **Secrets and configmaps**.
5. Click **Create new** → Select **SSH Secret**.
<img width="1728" height="992" alt="Screenshot 2026-01-16 at 12 15 17 AM" src="https://github.com/user-attachments/assets/0e79b16b-5771-4558-bb1b-f681aa588e88" />
<img width="1728" height="992" alt="Screenshot 2026-01-16 at 12 21 21 AM" src="https://github.com/user-attachments/assets/894a9c54-0e4c-4548-a4e2-c63dc1dbefa4" />

6. Enter the following details:

  - **Secret name**: github-code-engine-ssh
  - **SSH private key**: Paste the private SSH key generated in Step 3 into the Private Key field.

<img width="3456" height="1984" alt="image" src="https://github.com/user-attachments/assets/aaa2c1d2-cd2d-4fa5-a0b7-a899a98afdac" />

---

## 🐙 STEP 6: Add SSH Key to GitHub Enterprise

1. Visit [GitHub Enterprise](https://github.ibm.com/).
2. Click your profile icon (top-right) → **Settings**.
3. In the left menu, click **SSH and GPG keys**.
4. Click **New SSH key** and fill in the form:
   - **Title**: e.g., "**github-code-engine-ssh**"
   - **Key type**: Select **Authentication Key**
   - **Key**: Paste the public key from **Step 4**
5. Click **Add SSH key** to save.

   <img width="1370" height="816" alt="Screenshot 2026-01-16 at 12 48 47 AM" src="https://github.com/user-attachments/assets/f2b9f89e-4e2c-400a-99c0-5070056caf77" />


---

✅ You're now ready to authenticate and deploy securely!
