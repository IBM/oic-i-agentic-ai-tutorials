import express from 'express';
import jwt from 'jsonwebtoken';
import crypto from 'crypto';
import NodeRSA from 'node-rsa';
import cors from 'cors';
import rateLimit from 'express-rate-limit';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
app.use(express.json());
app.use(cors());

const limiter = rateLimit({
    windowMs: 15 * 60 * 1000,
    max: 1000,
    standardHeaders: true,
    legacyHeaders: false,
});
app.use(limiter);

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

const REGIONS = ['us-south', 'us-east', 'eu-gb', 'eu-de', 'jp-tok', 'jp-osa', 'au-syd', 'ca-tor', 'br-sao', 'in-che', 'mad'];
const ALLOWED_HOST_LIST = [
    'iam.cloud.ibm.com',
    'iam.platform.saas.ibm.com',
    'iam.platform.test.saas.ibm.com',
    'iam.platform.dev.saas.ibm.com',
    'dl.watson-orchestrate.ibm.com',
    'localhost',
    '127.0.0.1'
];

for (const region of REGIONS) {
    ALLOWED_HOST_LIST.push(`api.${region}.watson-orchestrate.cloud.ibm.com`);
    ALLOWED_HOST_LIST.push(`api.${region}.orchestrate.watsonx.ibm.com`);
    ALLOWED_HOST_LIST.push(`api.${region}.watson-orchestrate.ibm.com`);
    ALLOWED_HOST_LIST.push(`${region}.orchestrate.watsonx.ibm.com`);
    ALLOWED_HOST_LIST.push(`${region}.watson-orchestrate.cloud.ibm.com`);
}

/**
 * POST /api/proxy
 * Generic proxy to bypass CORS for IBM Cloud external APIs from the browser.
 */
app.post('/api/proxy', async (req, res) => {
    try {
        const { url, method, headers, textBody } = req.body;
        
        if (!url || typeof url !== 'string') {
            return res.status(400).json({ error: "Missing or invalid url parameter." });
        }

        let parsedUrl;
        try {
            parsedUrl = new URL(url);
        } catch {
            return res.status(400).json({ error: "Invalid target URL." });
        }

        if (parsedUrl.protocol !== 'http:' && parsedUrl.protocol !== 'https:') {
            return res.status(400).json({ error: "Only HTTP and HTTPS protocols are permitted." });
        }

        const reqHostname = parsedUrl.hostname.toLowerCase();
        const matchedHost = ALLOWED_HOST_LIST.find(h => h === reqHostname);
        if (!matchedHost) {
            return res.status(403).json({ error: "Target domain is not authorized for proxying." });
        }

        if (typeof fetch === 'undefined') {
            return res.status(500).json({ error: "Node fetch unavailable. Requires Node 18+." });
        }

        const cleanPath = parsedUrl.pathname.replace(/[^a-zA-Z0-9_\-\/]/g, '');
        if (cleanPath.includes('..')) {
            return res.status(400).json({ error: "Path traversal detected." });
        }

        const safeProtocol = (matchedHost === 'localhost' || matchedHost === '127.0.0.1') && parsedUrl.protocol === 'http:'
            ? 'http:'
            : 'https:';

        const portPart = parsedUrl.port ? `:${Number(parsedUrl.port)}` : '';
        const safeUrl = `${safeProtocol}//${matchedHost}${portPart}${cleanPath}`;

        const fetchRes = await fetch(safeUrl, {
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
