import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createRouter } from "@tanstack/react-router";
import ReactDOM from "react-dom/client";
import { routeTree } from "./routeTree.gen";

import { StrictMode } from "react";
import { client } from "./client/client.gen";

import "./styles/globals.scss";
import "./styles/tailwind.scss";
import { Toaster } from "@/components/common/Toaster";
import { ThemeProvider } from "./components/theme/ThemeProvider";

client.setConfig({
  baseURL: import.meta.env.VITE_API_URL || "",
  throwOnError: true,
  auth: async () => {
    return localStorage.getItem("access_token") || undefined;
  },
});

const queryClient = new QueryClient();

const router = createRouter({ routeTree });
declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider>
      <Toaster />
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </ThemeProvider>
  </StrictMode>,
);
