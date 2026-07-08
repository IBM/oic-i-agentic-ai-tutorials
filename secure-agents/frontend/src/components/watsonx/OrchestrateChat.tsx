import React, { useEffect } from "react";
import { useRouter } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { Loading } from "@carbon/react";
import { getCustomLanguageSelector, defaultLocale } from "./languageSelector";
import { createHandlers } from "./orchestrateHandlers";
import useAuth from "@/hooks/useAuth";

declare global {
  interface Window {
    wxOConfiguration: any;
    wxoLoader: any;
    __hasLoadedWatsonSources__: boolean;
  }
}

const OrchestrateChat: React.FC = () => {
  const html_container_id = "wxo-container";
  const router = useRouter();
  const pathname = router.state.location.pathname;

  // Get authentication state
  const { user, isLoading: isAuthLoading } = useAuth();

  // Create handlers with queryClient
  const queryClient = useQueryClient();
  const handlers = createHandlers(queryClient);

  // Function to get identity token with SSO token
  const getIdentityToken = async () => {
    try {
      console.log("🔍 getIdentityToken() called");

      const accessToken = localStorage.getItem("access_token");
      if (!accessToken) {
        console.warn("No access token available for WXO");
        return null;
      }

      console.log("🔄 Requesting WXO JWT from backend with SSO token...");
      console.log(user);
      // Request WXO JWT from backend with SSO token

      const response = await fetch(
        `${import.meta.env.VITE_API_URL || ""}/api/v1/wxo/jwt`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            sso_token: accessToken,
            user_name: user?.preferred_username,
            custom_user_id: user?.id,
          }),
        },
      );

      if (!response.ok) {
        console.error("Failed to get WXO JWT");
        return null;
      }

      const data = await response.json();
      console.log("✅ Retrieved JWT token for WxO (signed with private key)");
      console.log("Token preview:", data.token.substring(0, 50) + "...");
      console.log("SSO token included:", data.has_sso_token);

      return data.token;
    } catch (error) {
      console.error("Error getting identity token:", error);
      return null;
    }
  };

  // Register event handlers when chat loads
  const onChatLoad = (instance: any) => {
    window.wxoLoader.chatInstance = instance;

    if (typeof instance.on === "function") {
      instance.on("send", handlers.sendHandler);
      instance.on("receive", handlers.receiveHandler);
      instance.on("pre:receive", handlers.preReceiveHandler);
      instance.on("feedback", handlers.feedbackHandler);
      instance.updateCustomHeaderItems([getCustomLanguageSelector()]);

      // Handle auth token needed event
      // Set the token on the event object, not by calling updateIdentityToken
      instance.on("authTokenNeeded", async (e: any) => {
        console.log("WxO requesting auth token");
        const token = await getIdentityToken();
        if (token) {
          console.log(token);
          e.authToken = token;
        }
      });
    }
  };

  // Load watsonx Orchestrate script once user is authenticated
  useEffect(() => {
    // Don't initialize if still loading auth or user is not authenticated
    if (isAuthLoading || !user) {
      return;
    }

    // Don't load if already loaded
    if (window.__hasLoadedWatsonSources__) return;

    console.log("✅ User authenticated, initializing Watson Orchestrate");
    window.__hasLoadedWatsonSources__ = true;

    // Fetch WxO config from backend, get identity token, then configure and load WxO
    Promise.all([
      fetch(`${import.meta.env.VITE_API_URL || ""}/api/v1/wxo/config`).then(
        (res) => res.json(),
      ),
      getIdentityToken(),
    ])
      .then(([wxoConfig, token]) => {
        if (!token) {
          console.warn(
            "No identity token available, WxO may have limited functionality",
          );
        }

        console.log("✅ Loaded WxO configuration from backend");

        // Configure Watson Orchestrate with backend config
        window.wxOConfiguration = {
          orchestrationID: wxoConfig.orchestrationID || null,
          hostURL: wxoConfig.hostURL || null,
          rootElementID: html_container_id,
          showLauncher: false,
          deploymentPlatform: wxoConfig.deploymentPlatform || "ibmcloud",
          crn: wxoConfig.crn || null,
          token: token, // Set initial token
          identityTokenFunction: getIdentityToken, // For token refresh
          chatOptions: {
            agentId: wxoConfig.agentId || null,
            agentEnvironmentId: wxoConfig.agentEnvironmentId || null,
            onLoad: onChatLoad,
          },
          defaultLocale: defaultLocale,

          // Options: float (default) | custom | fullscreen-overlay
          // width and height optional, only honored when form is float
          layout: {
            showHeader: true,
            form: "fullscreen-overlay",
            showOrchestrateHeader: true,
            width: "600px",
            height: "600px",
            showMaxWidth: false,
            customElement: null,
          },

          // empty for default style - try combining #fff0f7 #ffafd2 #ee5396
          style: {
            headerColor: "",
            userMessageBackgroundColor: "",
            primaryColor: "",
            showBackgroundGradient: true,
          },
          header: {
            showResetButton: true,
            showAiDisclaimer: true,
            showMaximize: false,
          },
        };

        // Load Watson Orchestrate script after configuration is set
        const script = document.createElement("script");
        script.src = `${window.wxOConfiguration.hostURL}/wxochat/wxoLoader.js?embed=true`;
        script.async = true;
        script.onload = async () => {
          // Initialize chat instance
          try {
            if (window.wxoLoader) {
              await window.wxoLoader.init();
              console.log(
                "Watson Orchestrate chat initialized with authentication",
              );
            }
          } catch (error) {
            console.error("Error initializing chat instance:", error);
          }
        };
        script.onerror = () => {
          console.error("Failed to load watsonx Orchestrate script");
        };

        document.body.appendChild(script);
      })
      .catch((error) => {
        console.error("Failed to initialize WxO with authentication:", error);
      });
  }, [isAuthLoading, user]); // Only initialize when auth state is resolved

  // Show/hide container based on route
  useEffect(() => {
    const container = document.getElementById(html_container_id);
    if (container && pathname === "/") {
      container.style.display = "block";
    }

    // Hide container when leaving the route
    // Ensure body scroll is enabled when leaving
    return () => {
      const container = document.getElementById(html_container_id);
      if (container) {
        container.style.display = "none";
        document.body.style.overflow = "";
      }
    };
  }, [pathname]);

  // Show loading state while checking authentication
  if (isAuthLoading) {
    return (
      <div id={html_container_id}>
        <Loading description="Authenticating..." />
      </div>
    );
  }

  // Don't render if user is not authenticated (shouldn't happen in protected route)
  if (!user) {
    return null;
  }

  return (
    <div id={html_container_id}>
      <Loading description="Booting watsonx Orchestrate" />
    </div>
  );
};

export default OrchestrateChat;
