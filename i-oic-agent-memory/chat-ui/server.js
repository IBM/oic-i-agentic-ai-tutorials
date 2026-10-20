import express from 'express';
import jwt from 'jsonwebtoken';
import crypto from 'crypto';
import NodeRSA from 'node-rsa';
import cors from 'cors';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
app.use(express.json());
app.use(cors());

app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'index.html'));
});

app.get('/index.html', (req, res) => {
    res.sendFile(path.join(__dirname, 'index.html'));
});

app.get('/chat.html', (req, res) => {
    res.sendFile(path.join(__dirname, 'chat.html'));
});

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

const ALLOWED_DOMAIN_SUFFIXES = [
    '.ibm.com',
    '.cloud.ibm.com',
    '.saas.ibm.com'
];
const ALLOWED_EXACT_HOSTS = ['localhost', '127.0.0.1'];

function isValidProxyUrl(rawUrl) {
    if (typeof rawUrl !== 'string') return false;
    try {
        const parsed = new URL(rawUrl);
        if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
            return false;
        }
        const host = parsed.hostname.toLowerCase();
        if (ALLOWED_EXACT_HOSTS.includes(host)) return true;
        return ALLOWED_DOMAIN_SUFFIXES.some(suffix => host === suffix.slice(1) || host.endsWith(suffix));
    } catch {
        return false;
    }
}

/**
 * POST /api/proxy
 * Generic proxy to bypass CORS for IBM Cloud external APIs from the browser.
 */
app.post('/api/proxy', async (req, res) => {
    try {
        const { url, method, headers, textBody } = req.body;
        
        if (!url || !isValidProxyUrl(url)) {
            return res.status(400).json({ error: "Invalid or unauthorized target URL." });
        }

        if (typeof fetch === 'undefined') {
            return res.status(500).json({ error: "Node fetch unavailable. Requires Node 18+." });
        }

        const targetUrl = new URL(url).toString();

        const fetchRes = await fetch(targetUrl, {
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
