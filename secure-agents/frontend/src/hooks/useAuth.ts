import { useQuery, useMutation } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import type { UserPublic } from "../client";
import { Oauth } from "../client";

const isLoggedIn = () => {
  return localStorage.getItem("access_token") !== null;
};

const useAuth = () => {
  const navigate = useNavigate();

  // Get user info from IBM Verify token
  const { data: user, isLoading } = useQuery<UserPublic | null, Error>({
    queryKey: ["currentUser"],
    queryFn: async () => {
      try {
        const token = localStorage.getItem("access_token");
        if (!token) {
          return null;
        }

        // Decode JWT token to get user info (without verification - backend will verify)
        const payload = JSON.parse(atob(token.split(".")[1]));

        // Check if token is expired
        if (payload.exp && payload.exp < Date.now() / 1000) {
          localStorage.removeItem("access_token");
          localStorage.removeItem("refresh_token");
          localStorage.removeItem("id_token");
          navigate({ to: "/login" });
          return null;
        }

        // Return user info from token
        return {
          id: payload.sub || "",
          email: payload.unique_name || payload.email || null,
          full_name: payload.name || null,
          preferred_username: payload.preferred_username || null,
          unique_name: payload.unique_name || null,
          upn: payload.upn || null,
        } as UserPublic;
      } catch (err) {
        console.error("Error decoding token:", err);
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        localStorage.removeItem("id_token");
        navigate({ to: "/login" });
        return null;
      }
    },
    enabled: isLoggedIn(),
  });

  const logoutMutation = useMutation({
    mutationFn: async () => {
      const accessToken = localStorage.getItem("access_token");
      const refreshToken = localStorage.getItem("refresh_token");
      const idToken = localStorage.getItem("id_token");

      if (!accessToken) {
        return null;
      }

      try {
        // Call backend logout endpoint to revoke tokens with IBM Verify
        await Oauth.logout({
          query: {
            access_token: accessToken,
            refresh_token: refreshToken || undefined,
          },
        });
      } catch (error) {
        // Log error but continue with local logout
        console.error("Error revoking tokens with IBM Verify:", error);
      }

      // Fetch OAuth config to get tenant info for logout URL
      try {
        const config = await Oauth.getOauthConfig();
        return { config: config.data, idToken };
      } catch (error) {
        console.error("Error fetching OAuth config:", error);
        return { config: null, idToken };
      }
    },
    onSuccess: (data) => {
      // Clear local storage first
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      localStorage.removeItem("id_token");

      const config = data?.config;
      const idToken = data?.idToken;

      // Redirect to IBM Verify logout to clear the session
      if (config && config.tenant_id && config.frontend_host) {
        // IBM Verify logout endpoint with post_logout_redirect_uri and id_token_hint
        // According to OIDC standard, id_token_hint is required for secure logout
        const logoutUrl = `https://${config.tenant_id}/oauth2/rplogout`;
        const redirectUri = `${config.frontend_host}`;
        
        // Build logout URL with required parameters
        const params = new URLSearchParams();
        if (idToken) {
          params.append("id_token_hint", idToken);
        }
        params.append("post_logout_redirect_uri", redirectUri);
        
        window.location.href = `${logoutUrl}?${params.toString()}`;
      } else {
        // Fallback to local navigation if config not available
        window.location.href = "/login";
      }
    },
    onError: () => {
      // On error, still clear local storage and redirect
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      localStorage.removeItem("id_token");
      window.location.href = "/login";
    },
  });

  const logout = () => {
    logoutMutation.mutate();
  };

  return {
    logout,
    user,
    isLoading,
  };
};

export { isLoggedIn };
export default useAuth;
