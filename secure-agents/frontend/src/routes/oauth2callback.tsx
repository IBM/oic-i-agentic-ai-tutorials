import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Loading } from "@carbon/react";

export const Route = createFileRoute("/oauth2callback")({
  component: OAuth2Callback,
});

function OAuth2Callback() {
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Prevent double execution in React StrictMode
    // This is critical because OAuth authorization codes can only be used once
    let isExecuted = false;

    const handleCallback = async () => {
      // Guard against double execution
      if (isExecuted) {
        console.log(
          "⚠️ OAuth callback already executed, skipping duplicate call",
        );
        return;
      }
      isExecuted = true;

      // Get code and state from URL
      const params = new URLSearchParams(window.location.search);
      const code = params.get("code");
      const state = params.get("state");
      const errorParam = params.get("error");

      if (errorParam) {
        setError(`Authentication failed: ${errorParam}`);
        setTimeout(() => navigate({ to: "/login" }), 3000);
        return;
      }

      if (!code) {
        setError("No authorization code received");
        setTimeout(() => navigate({ to: "/login" }), 3000);
        return;
      }

      // Check if we already have a token (from a previous execution)
      const existingToken = localStorage.getItem("access_token");
      if (existingToken) {
        console.log("✅ Token already exists, redirecting to home");
        window.location.href = "/";
        return;
      }

      try {
        console.log("🔄 Exchanging authorization code for token...");

        // Exchange code for token
        const response = await fetch(
          `${import.meta.env.VITE_API_URL || ""}/api/v1/oauth/callback?code=${code}&state=${state}`,
        );

        if (!response.ok) {
          throw new Error("Token exchange failed");
        }

        const data = await response.json();

        // Store access token
        if (data.access_token) {
          localStorage.setItem("access_token", data.access_token);

          if (data.correlation_id) {
            localStorage.setItem("correlation_id", data.correlation_id);
          }

          // Store refresh token if available
          if (data.refresh_token) {
            localStorage.setItem("refresh_token", data.refresh_token);
          }

          // Store id_token for logout (required by OIDC standard)
          if (data.id_token) {
            localStorage.setItem("id_token", data.id_token);
          }

          // DEBUG: Print access token to console
          console.log("=".repeat(80));
          console.log("🔑 IBM VERIFY ACCESS TOKEN (for debugging):");
          console.log("=".repeat(80));
          console.log(data.access_token);
          console.log("=".repeat(80));
          console.log("📋 To test token validation, run this in console:");
          console.log(`fetch('${import.meta.env.VITE_API_URL || ""}/api/v1/oauth/validate-flow', {
  method: 'POST',
  headers: {'Content-Type': 'application/x-www-form-urlencoded'},
  body: 'access_token=' + encodeURIComponent(localStorage.getItem('access_token'))
}).then(r => r.json()).then(console.log)`);
          console.log("=".repeat(80));

          // Use window.location for a full page reload to ensure token is available
          // This prevents race conditions with route guards
          window.location.href = "/";
        } else {
          throw new Error("No access token in response");
        }
      } catch (err) {
        console.error("OAuth callback error:", err);
        setError("Authentication failed. Please try again.");
        setTimeout(() => {
          window.location.href = "/login";
        }, 3000);
      }
    };

    handleCallback();

    // Cleanup function to prevent memory leaks
    return () => {
      isExecuted = true;
    };
  }, [navigate]);

  return (
    <div className="flex min-h-[100dvh] flex-col items-center justify-center p-4">
      {error ? (
        <div className="text-center">
          <p className="mb-4 text-cds-text-error">{error}</p>
          <p className="text-cds-text-secondary">Redirecting to login...</p>
        </div>
      ) : (
        <div className="text-center">
          <Loading
            description="Completing authentication..."
            withOverlay={false}
          />
          <p className="mt-4 text-cds-text-secondary">Please wait...</p>
        </div>
      )}
    </div>
  );
}
