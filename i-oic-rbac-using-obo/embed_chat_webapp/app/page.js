"use client";

import Script from "next/script";
import { useState, useEffect } from "react";
import { APP_CONFIG } from "../config";

// ---------------------------
// Configuration
// ---------------------------

const OKTA_DOMAIN = APP_CONFIG.okta.domain;
const CLIENT_ID = APP_CONFIG.okta.clientId;

// ---------------------------
// Helpers
// ---------------------------

function decodeJWT(token) {
  const base64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
  return JSON.parse(atob(base64));
}

function clearEmbedSession() {
  document.cookie =
    "embed_user_id=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";

  sessionStorage.removeItem("embed_user_id_dev");
  sessionStorage.removeItem("current_session_user_id");

  sessionStorage.embed_user_id_dev = Math.trunc(Math.random() * 1000000);
}

export default function Page() {

  const [oktaClient, setOktaClient] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [userInfo, setUserInfo] = useState(null);
  const [accessToken, setAccessToken] = useState(null);

  // ---------------------------
  // Okta Init
  // ---------------------------

  function initializeOkta() {
    if (!window.OktaAuth || window.oktaClient) return;

    const redirectUri = window.location.origin + "/";

    const client = new window.OktaAuth({
      issuer: `${OKTA_DOMAIN}/oauth2/default`,
      clientId: CLIENT_ID,
      redirectUri,
      scopes: ["openid", "profile", "email"],
      pkce: true,
      tokenManager: { autoRenew: true },
      postLogoutRedirectUri: redirectUri,
    });

    window.oktaClient = client;
    setOktaClient(client);

    client.tokenManager.on("renewed", (key, token) => {
      if (key === "accessToken") setAccessToken(token.accessToken);
      if (key === "idToken") setUserInfo(decodeJWT(token.idToken));
    });

    client.token
      .parseFromUrl()
      .then(({ tokens }) => {
        client.tokenManager.setTokens(tokens);
        setIsAuthenticated(true);

        if (tokens.accessToken)
          setAccessToken(tokens.accessToken.accessToken);

        if (tokens.idToken)
          setUserInfo(decodeJWT(tokens.idToken.idToken));
      })
      .catch(async () => {
        const session = await client.session.get();

        if (session.status === "ACTIVE") {
          setIsAuthenticated(true);

          const a = await client.tokenManager.get("accessToken");
          const i = await client.tokenManager.get("idToken");

          if (a) setAccessToken(a.accessToken);
          if (i) setUserInfo(decodeJWT(i.idToken));
        } else {
          client.token.getWithRedirect({
            responseType: ["token", "id_token"],
          });
        }
      });
  }

  // ---------------------------
  // Clear embed session once
  // ---------------------------

  useEffect(() => {
    clearEmbedSession();
  }, []);

  // ---------------------------
  // Watsonx Orchestrate Init
  // ---------------------------

  useEffect(() => {
    if (!userInfo || !accessToken) return;
    if (window.orchestrateInitCalled) return;

    const orchestrateInfo = APP_CONFIG.orchestrate;

    async function getLatestAccessToken() {
      try {
        const renewed =
          await window.oktaClient.tokenManager.renew("accessToken");
        return renewed.accessToken;
      } catch {
        const stored =
          await window.oktaClient.tokenManager.get("accessToken");
        return stored?.accessToken || accessToken;
      }
    }

    async function generateJWT(accessToken) {
      const res = await fetch("/api/encrypt", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          userInfo,
          accessToken,
          orchestrateInfo,
        }),
      });

      const { token } = await res.json();
      return token;
    }

    async function getIdentityToken() {
      const accessToken = await getLatestAccessToken();
      const token = await generateJWT(accessToken);
      window.wxOConfiguration.token = token;
      return token;
    }

    window.wxOConfiguration = {
      orchestrationID: orchestrateInfo.orchestrationID,
      hostURL: orchestrateInfo.hostURL,
      rootElementID: "root",
      deploymentPlatform: "ibmcloud",
      crn: orchestrateInfo.crn,
      identityTokenFunction: getIdentityToken,
      chatOptions: {
        agentId: orchestrateInfo.agentId,
        agentEnvironmentId: orchestrateInfo.agentEnvironmentId,
        onLoad(instance) {
          instance.on("authTokenNeeded", async (e) => {
            e.authToken = await getIdentityToken();
          });
        },
      },
      layout: {
        form: "float",
        showOrchestrateHeader: true,
      },
    };

    window.orchestrateInitCalled = true;

    getIdentityToken().then(() => {
      const script = document.createElement("script");
      script.src = `${orchestrateInfo.hostURL}/wxochat/wxoLoader.js?embed=true`;
      script.onload = () => wxoLoader.init();
      document.head.appendChild(script);
    });
  }, [userInfo, accessToken]);

  // ---------------------------
  // Logout
  // ---------------------------

  async function handleLogout() {
    clearEmbedSession();
    await (oktaClient || window.oktaClient)?.signOut();
  }

  // ---------------------------
  // UI
  // ---------------------------

  const backgroundStyle = {
    height: "100vh",
    width: "100vw",
    backgroundImage: "url('/hr-banner.png')",
    backgroundSize: "cover",
    backgroundPosition: "center",
    backgroundRepeat: "no-repeat",
  };

  return (
    <>
      <Script
        src="https://global.oktacdn.com/okta-auth-js/7.7.0/okta-auth-js.min.js"
        strategy="afterInteractive"
        onLoad={initializeOkta}
      />

      {/* NOT AUTHENTICATED */}
      {!isAuthenticated ? (
        <div style={backgroundStyle}>
          <div
            style={{
              height: "100%",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <div
              style={{
                background: "rgba(255,255,255,0.85)",
                padding: "24px 50px",
                borderRadius: "14px",
                fontSize: "22px",
                fontWeight: "600",
              }}
            >
              Redirecting to Okta...
            </div>
          </div>
        </div>
      ) : (
        // AUTHENTICATED
        <div style={backgroundStyle}>

          {/* User bar */}
          <div
            style={{
              position: "fixed",
              top: 0,
              right: 0,
              padding: "12px 16px",
              background: "#ffffffdd",
              zIndex: 9999,
            }}
          >
            Signed in as <b>{userInfo?.email || "User"}</b>

            <button
              onClick={handleLogout}
              style={{
                marginLeft: 12,
                padding: "6px 14px",
                backgroundColor: "#0c0c0dff",
                color: "#fff",
                border: "none",
                borderRadius: "6px",
                cursor: "pointer",
              }}
            >
              Sign out
            </button>
          </div>

          {/* Orchestrate root */}
          <div style={{ paddingTop: 60, height: "100%" }}>
            <div id="root" style={{ width: "100%", height: "100%" }} />
          </div>

        </div>
      )}
    </>
  );
}
