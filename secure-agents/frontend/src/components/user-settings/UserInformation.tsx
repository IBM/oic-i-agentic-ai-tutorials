import { useQuery } from "@tanstack/react-query";
import useAuth from "../../hooks/useAuth";
import {
  Stack,
  Tile,
  FormGroup,
  FormLabel,
  Tag,
  Accordion,
  AccordionItem,
  CodeSnippet,
} from "@carbon/react";
import { Oauth, type TokenInfoResponse } from "@/client";

const UserInformation = () => {
  const { user: currentUser } = useAuth();

  // Get token info for authentication status
  const { data: tokenInfo } = useQuery<TokenInfoResponse | null>({
    queryKey: ["tokenInfo"],
    queryFn: async (): Promise<TokenInfoResponse | null> => {
      const accessToken = localStorage.getItem("access_token");
      if (!accessToken) return null;

      try {
        const response = await Oauth.getTokenInfo({
          query: { access_token: accessToken },
        });
        return response.data ?? null;
      } catch (error) {
        console.error("Error fetching token info:", error);
        return null;
      }
    },
    enabled: !!localStorage.getItem("access_token"),
    refetchInterval: 60000, // Refresh every minute
  });

  return (
    <Stack gap={6}>
      {/* Authentication Status Section */}
      <Tile className="max-w-md">
        <h3 className="mb-4 text-xl font-medium">🔐 Authentication Status</h3>
        <Stack gap={5}>
          <FormGroup legendText="">
            <FormLabel>Status</FormLabel>
            <div className="py-2">
              {tokenInfo?.is_valid ? (
                <Tag type="green" size="md">
                  ✅ Authenticated
                </Tag>
              ) : (
                <Tag type="red" size="md">
                  ❌ Token Issue
                </Tag>
              )}
            </div>
          </FormGroup>
          <FormGroup legendText="">
            <FormLabel>Token Validity</FormLabel>
            <p
              className={`py-2 ${tokenInfo?.is_valid ? "text-cds-support-success" : "text-cds-support-error"}`}
            >
              {tokenInfo?.status_message || "Checking..."}
            </p>
          </FormGroup>

          {/* Token Payload Details */}
          {tokenInfo?.payload && (
            <FormGroup legendText="">
              <FormLabel>Token Details</FormLabel>
              <Accordion>
                <AccordionItem title="View Raw Token Payload">
                  <CodeSnippet
                    type="multi"
                    feedback="Copied to clipboard"
                    wrapText={true}
                  >
                    {JSON.stringify(tokenInfo.payload, null, 2)}
                  </CodeSnippet>
                </AccordionItem>
              </Accordion>
            </FormGroup>
          )}
        </Stack>
      </Tile>

      {/* User Information Section */}
      <Tile className="max-w-md">
        <h3 className="mb-4 text-xl font-medium">User Information</h3>
        <p className="mb-6 text-sm text-cds-text-secondary">
          User information is managed by IBM Verify and cannot be edited here.
        </p>
        <Stack gap={5}>
          <FormGroup legendText="">
            <FormLabel className="mt-2">Full name</FormLabel>
            <p
              className={`py-2 ${!currentUser?.full_name && !currentUser?.preferred_username ? "text-gray-500" : ""}`}
            >
              {currentUser?.full_name ||
                currentUser?.preferred_username ||
                "N/A"}
            </p>
          </FormGroup>
          <FormGroup legendText="">
            <FormLabel>Email</FormLabel>
            <p className="py-2">{currentUser?.email || "N/A"}</p>
          </FormGroup>
          <FormGroup legendText="">
            <FormLabel>User ID</FormLabel>
            <p className="py-2 font-mono text-sm text-cds-text-secondary">
              {currentUser?.id || "N/A"}
            </p>
          </FormGroup>
        </Stack>
      </Tile>
    </Stack>
  );
};

export default UserInformation;
