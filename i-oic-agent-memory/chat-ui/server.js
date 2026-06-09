import express from 'express';
import jwt from 'jsonwebtoken';
import crypto from 'crypto';
import NodeRSA from 'node-rsa';
import cors from 'cors';

const app = express();
app.use(express.json());
app.use(cors());
app.use(express.static('.')); // Serve static files from current directory

/**
 * POST /api/jwt
 * Generates and encrypts a JWT for WXO Chat.
 */
app.post('/api/jwt', async (req, res) => {
    try {
        const {
            subject,
            userPayload,
            context,
            privateKey,
            ibmKey
        } = req.body;

        if (!privateKey) {
            return res.status(400).json({ error: "Client private key is missing." });
        }

        const privateKeyBuffer = typeof privateKey === 'string'
            ? Buffer.from(privateKey, 'utf-8')
            : privateKey;

        const ibmKeyBuffer = ibmKey && typeof ibmKey === 'string'
            ? Buffer.from(ibmKey, 'utf-8')
            : ibmKey;

        // Construct jwtContent - Order matters per WXO docs: sub -> exp -> user_payload -> context -> iat
        const jwtContent = {
            sub: subject,
            exp: Math.floor(Date.now() / 1000) + (60 * 60)  // 1 hour (3600 seconds)
        };

        if (userPayload && typeof userPayload === 'object') {
            jwtContent.user_payload = userPayload;
        }

        jwtContent.context = context || {};

        // Encrypt user_payload with IBM public key if provided
        if (ibmKeyBuffer && jwtContent.user_payload) {
            const plaintext = JSON.stringify(jwtContent.user_payload);
            const rsaKey = new NodeRSA(ibmKeyBuffer);
            rsaKey.setOptions({ encryptionScheme: 'pkcs1_oaep' });
            jwtContent.user_payload = rsaKey.encrypt(Buffer.from(plaintext, "utf-8"), "base64");
        }

        // Sign JWT with client private key
        const token = jwt.sign(jwtContent, privateKeyBuffer, {
            algorithm: "RS256",
            allowInsecureKeySizes: true
        });

        return res.json({ jwt: token });

    } catch (error) {
        console.error(`❌ JWT generation error:`, error);
        return res.status(500).json({ error: error.message });
    }
});

/**
 * POST /api/keys/generate
 * Generates a new RSA key pair for the client.
 */
app.post('/api/keys/generate', (req, res) => {
    try {
        const { publicKey, privateKey } = crypto.generateKeyPairSync('rsa', {
            modulusLength: 2048,
            publicKeyEncoding: { type: 'spki', format: 'pem' },
            privateKeyEncoding: { type: 'pkcs8', format: 'pem' }
        });
        return res.json({ publicKey, privateKey });
    } catch (error) {
        console.error(`❌ Key generation error:`, error);
        return res.status(500).json({ error: error.message });
    }
});

/**
 * POST /api/proxy
 * Generic proxy to bypass CORS for IBM Cloud external APIs from the browser.
 */
app.post('/api/proxy', async (req, res) => {
    try {
        const { url, method, headers, textBody } = req.body;
        
        if (typeof fetch === 'undefined') {
            return res.status(500).json({ error: "Node fetch unavailable. Requires Node 18+." });
        }

        const fetchRes = await fetch(url, {
            method: method || 'GET',
            headers: headers || {},
            body: textBody || undefined
        });

        const respText = await fetchRes.text();
        let respData;
        try {
            respData = JSON.parse(respText);
        } catch(e) {
            respData = { raw: respText };
        }

        return res.status(fetchRes.status).json(respData);

    } catch (error) {
        console.error('❌ Proxy error:', error);
        return res.status(500).json({ error: error.message });
    }
});

const PORT = 3001;
app.listen(PORT, () => {
    console.log(`🚀 WXO JWT Server running on http://localhost:${PORT}`);
});
