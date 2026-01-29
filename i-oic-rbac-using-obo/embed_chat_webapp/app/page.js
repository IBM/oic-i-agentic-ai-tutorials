"use client";

/**
 * This file implements:
 * - Okta authentication using PKCE
 * - Secure access and ID token handling
 * - Watsonx Orchestrate embedded chat initialization
 * - Identity token refresh using an OBO-style flow
 */

import Script from "next/script";
import { useState, useEffect } from "react";
import { APP_CONFIG } from "../config";

// ---------------------------
// Configuration Constants
// ---------------------------
// Okta domain and client ID loaded from centralized config
const OKTA_DOMAIN = APP_CONFIG.okta.domain;
const CLIENT_ID = APP_CONFIG.okta.clientId;

// ---------------------------
// Helper Functions
// ---------------------------

/**
 * Function used to decode the ID token
 * and read user information from it.
 */
function decodeJWT(token) {
  const base64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
  return JSON.parse(atob(base64));
}

/**
 * Clears any existing Watsonx Orchestrate embed session.
 * This prevents session reuse issues during logout or re-login.
 */
function clearEmbedSession() {
  // Remove embed-related cookie
  document.cookie =
    "embed_user_id=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";

  // Clear session-scoped identifiers
  sessionStorage.removeItem("embed_user_id_dev");
  sessionStorage.removeItem("current_session_user_id");

  // Generate a fresh embed session ID
  sessionStorage.embed_user_id_dev = Math.trunc(Math.random() * 1000000);
}

export default function Page() {
  // ---------------------------
  // React State
  // ---------------------------

  // Stores the Okta client used for login, token management, and logout
  const [oktaClient, setOktaClient] = useState(null);

  // Tracks whether the user is authenticated
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  // Stores decoded user info from the ID token
  const [userInfo, setUserInfo] = useState(null);

  // Stores the Okta access token string
  const [accessToken, setAccessToken] = useState(null);

  // ---------------------------
  // Okta Initialization (Runs Once)
  // ---------------------------
  /**
   * Initializes the Okta Auth JS client.
   * - Handles redirect-based login
   * - Restores an existing session if present
   * - Automatically renews tokens
   * - Redirects to Okta if no session exists
   */
  function initializeOkta() {
    // Prevent duplicate initialization
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

    // Store client globally and in React state
    window.oktaClient = client;
    setOktaClient(client);

    /**
     * Listen for token renewals and update state
     * so the application always uses fresh tokens
     */
    client.tokenManager.on("renewed", (key, token) => {
      if (key === "accessToken") setAccessToken(token.accessToken);
      if (key === "idToken") setUserInfo(decodeJWT(token.idToken));
    });

    /**
     * Step 1: Handle redirect callback from Okta
     * If tokens are present in the URL, store them
     */
    client.token
      .parseFromUrl()
      .then(({ tokens }) => {
        client.tokenManager.setTokens(tokens);
        setIsAuthenticated(true);

        if (tokens.accessToken) {
          setAccessToken(tokens.accessToken.accessToken);
        }

        if (tokens.idToken) {
          setUserInfo(decodeJWT(tokens.idToken.idToken));
        }
      })
      .catch(async () => {
        /**
         * Step 2: If no redirect tokens are found,
         * check if an active Okta session exists
         */
        const session = await client.session.get();

        if (session.status === "ACTIVE") {
          setIsAuthenticated(true);

          const a = await client.tokenManager.get("accessToken");
          const i = await client.tokenManager.get("idToken");

          if (a) setAccessToken(a.accessToken);
          if (i) setUserInfo(decodeJWT(i.idToken));
        } else {
          /**
           * Step 3: No active session → redirect to Okta login
           */
          client.token.getWithRedirect({
            responseType: ["token", "id_token"],
          });
        }
      });
  }

  // ---------------------------
  // Clear Embed Session (Runs Once)
  // ---------------------------
  /**
   * Ensures the embedded chat always starts
   * with a clean session on page load.
   */
  useEffect(() => {
    if (typeof window !== "undefined") {
      clearEmbedSession();
    }
  }, []);

  // ---------------------------
  // Watsonx Orchestrate Initialization
  // ---------------------------
  /**
   * Initializes Watsonx Orchestrate only after:
   * - User info is available
   * - Access token is available
   * - Ensures initialization happens only once
   */
  useEffect(() => {
    if (!userInfo || !accessToken) return;
    if (window.orchestrateInitCalled) return;

    const orchestrateInfo = APP_CONFIG.orchestrate;

    /**
     * Retrieves the latest valid Okta access token.
     * Renews it if required.
     */
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

    /**
     * Calls the backend to generate a signed JWT
     * trusted by Watsonx Orchestrate.
     */
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
      if (!token) throw new Error("JWT creation failed");
      return token;
    }

    /**
     * Function used by Orchestrate to obtain
     * a fresh identity token whenever required.
     */
    async function getIdentityToken() {
      const accessToken = await getLatestAccessToken();
      const token = await generateJWT(accessToken);
      window.wxOConfiguration.token = token;
      return token;
    }

    /**
     * Global Watsonx Orchestrate configuration
     * consumed by wxoLoader.js
     */
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
          /**
           * Handles token expiry events
           * inside the embedded chat
           */
          instance.on("authTokenNeeded", async (e) => {
            e.authToken = await getIdentityToken();
          });
        },
      },
      layout: {
        // form: "float",
        // width: "450px",
        // height: "600px",
        form: 'fullscreen-overlay',
        showOrchestrateHeader: true,
      },
    };

    // Prevent re-initialization
    window.orchestrateInitCalled = true;

    /**
     * Load the Orchestrate embed script
     * and initialize the chat widget
     */
    getIdentityToken().then(() => {
      const script = document.createElement("script");
      script.src = `${orchestrateInfo.hostURL}/wxochat/wxoLoader.js?embed=true`;
      script.onload = () => wxoLoader.init();
      document.head.appendChild(script);
    });
  }, [userInfo, accessToken]);

  // ---------------------------
  // Logout Handler
  // ---------------------------
  /**
   * Clears the embed session and logs the user out of Okta.
   */
  async function handleLogout() {
    clearEmbedSession();
    await (oktaClient || window.oktaClient)?.signOut();
  }

  // ---------------------------
  // UI Rendering
  // ---------------------------
  return (
    <>
      {/* Load Okta Auth JS SDK */}
      <Script
        src="https://global.oktacdn.com/okta-auth-js/7.7.0/okta-auth-js.min.js"
        strategy="afterInteractive"
        onLoad={initializeOkta}
      />

      {/* Show loading state while redirecting to Okta */}
      {!isAuthenticated ? (
        <div
          style={{
            height: "100vh",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: "#f3f4f6",
          }}
        >
          <h2>Redirecting to Okta...</h2>
        </div>
      ) : (
        // Authenticated view
        <div style={{ height: "100vh", background: "#f3f4f6" }}>
          {/* User info and logout button */}
          <div
            style={{
              position: "fixed",
              top: 0,
              right:0,
              padding: "12px",
              background: "#fff",
              zIndex: 9999,
            }}
          >
            Signed in as <b>{userInfo?.email || "User"}</b>
            <button
              onClick={handleLogout}
              style={{
                marginLeft: 12,
                padding: "6px 14px",
                backgroundColor: "#0c0c0dff", // IBM blue
                color: "#fff",
                border: "none",
                borderRadius: "6px",
                fontSize: "14px",
                fontWeight: 500,
                cursor: "pointer",
              }}
            >
              Sign out
            </button>

          </div>

          {/* Root container for Orchestrate embed */}
          <div style={{ paddingTop: 60, height: "100%" }}>
            <div id="root" style={{ width: "100%", height: "100%" }} />
          </div>
        </div>
      )}
    </>
  );
}
