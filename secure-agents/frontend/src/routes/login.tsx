import { Button, Stack } from "@carbon/react";
import { createFileRoute, redirect } from "@tanstack/react-router";
import { useEffect, useState } from "react";

import { Logo } from "@/components/common/Logo";
import { isLoggedIn } from "../hooks/useAuth";

export const Route = createFileRoute("/login")({
  component: Login,
  beforeLoad: async () => {
    if (isLoggedIn()) {
      throw redirect({
        to: "/",
      });
    }
  },
});

function Login() {
  const [isLoading, setIsLoading] = useState(false);
  const [isFetchingConfig, setIsFetchingConfig] = useState(true);
  const [config, setConfig] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Double-check if user is already logged in (in case beforeLoad didn't catch it)
    if (isLoggedIn()) {
      window.location.href = "/";
      return;
    }

    // Fetch OAuth configuration from backend
    const fetchConfig = async () => {
      setIsFetchingConfig(true);
      try {
        const res = await fetch(
          `${import.meta.env.VITE_API_URL || ""}/api/v1/oauth/config`,
        );
        if (!res.ok) {
          throw new Error(`Failed to fetch config: ${res.status}`);
        }
        const data = await res.json();
        console.log("OAuth config loaded:", data);
        setConfig(data);
        setError(null);
      } catch (err) {
        console.error("Failed to load OAuth config:", err);
        setError(
          "Failed to load authentication configuration. Please ensure the backend is running.",
        );
      } finally {
        setIsFetchingConfig(false);
      }
    };

    fetchConfig();
  }, []);

  const handleLogin = () => {
    if (!config) return;

    setIsLoading(true);

    // Build authorization URL
    const params = new URLSearchParams({
      client_id: config.client_id,
      response_type: "code",
      redirect_uri: config.redirect_uri,
      scope: config.scope,
      state: crypto.randomUUID(), // Generate random state for CSRF protection
    });

    // Redirect to IBM Verify
    window.location.href = `${config.authorize_url}?${params.toString()}`;
  };

  return (
    <div className="mx-auto flex min-h-[100dvh] max-w-sm flex-col justify-center p-4">
      <Stack gap={5}>
        <Logo className="mb-2 w-full" />

        <div className="rounded-lg border border-cds-border-subtle bg-cds-layer p-6">
          <h2 className="mb-4 text-xl font-semibold">Welcome</h2>
          <p className="mb-6 text-cds-text-secondary">
            Sign in with your IBM Verify account to continue
          </p>

          {error && (
            <div className="mb-4 rounded bg-cds-notification-background-error p-3 text-sm text-cds-text-error">
              {error}
            </div>
          )}

          <Button
            onClick={handleLogin}
            disabled={!config || isLoading || isFetchingConfig}
            className="w-full max-w-full"
          >
            {isFetchingConfig
              ? "Loading..."
              : isLoading
                ? "Redirecting..."
                : "Sign in with IBM Verify"}
          </Button>
        </div>

        <div className="text-center text-sm text-cds-text-secondary">
          <p>Secure authentication powered by IBM Verify</p>
        </div>
      </Stack>
    </div>
  );
}
