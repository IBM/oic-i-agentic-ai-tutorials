import NodeRSA from "node-rsa";
import crypto from "crypto";
import { Buffer } from "buffer";

export async function POST(request) {
  try {
    const { userInfo, accessToken, orchestrateInfo } = await request.json();

    if (!userInfo || !accessToken || !orchestrateInfo) {
      return new Response(
        JSON.stringify({
          error: "Missing userInfo, accessToken, or orchestrateInfo",
        }),
        { status: 400, headers: { "Content-Type": "application/json" } }
      );
    }

    // ------------------------------
    // Decode access token
    // ------------------------------
    function decodeAccessToken(jwt) {
      const parts = jwt.split(".");
      if (parts.length !== 3) throw new Error("Invalid JWT format");

      return JSON.parse(
        Buffer.from(parts[1].replace(/-/g, "+").replace(/_/g, "/"), "base64").toString()
      );
    }

    const decoded_access_token = decodeAccessToken(accessToken);

    // ------------------------------
    // Build user payload + context
    // ------------------------------
    const context = {
      user_profile: userInfo
    };
    const user_payload = { sso_token: accessToken };

    // ------------------------------
    // Encrypt user payload with IBM public key
    // ------------------------------
    const rsaKey = new NodeRSA(orchestrateInfo.ibmPublickey);
    const encryptedUserPayload = rsaKey.encrypt(
      Buffer.from(JSON.stringify(user_payload)),
      "base64"
    );

    // ------------------------------
    // Build JWT payload
    // ------------------------------
    const jwtContent = {
      sub: decoded_access_token.sub,
      iat: decoded_access_token.iat,
      exp: decoded_access_token.exp,
      user_payload: encryptedUserPayload,
      context,
    };

    // ------------------------------
    // Create RS256 JWT manually
    // ------------------------------
    const header = { alg: "RS256", typ: "JWT" };

    const encodedHeader = Buffer.from(JSON.stringify(header)).toString("base64url");
    const encodedPayload = Buffer.from(JSON.stringify(jwtContent)).toString("base64url");

    const signingInput = `${encodedHeader}.${encodedPayload}`;

    // private key from environment OR from orchestrateInfo
    const clientPrivateKey =
      process.env.CLIENT_PRIVATE_KEY || orchestrateInfo.clientPrivateKey;

    if (!clientPrivateKey) throw new Error("Missing client private key");

    const signature = crypto
      .sign("RSA-SHA256", Buffer.from(signingInput), {
        key: clientPrivateKey,
      })
      .toString("base64url");

    const finalJWT = `${signingInput}.${signature}`;

    console.log("JWT generated successfully");

    return new Response(JSON.stringify({ token: finalJWT }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  } catch (err) {
    console.error("Error building JWT:", err);
    return new Response(JSON.stringify({ error: err.message }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }
}
