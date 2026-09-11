import { Outlet, createRootRoute } from "@tanstack/react-router";
import React, { Suspense } from "react";

import NotFound from "../components/common/NotFound";

const loadDevtools = () =>
  Promise.all([
    import("@tanstack/react-router-devtools"),
    import("@tanstack/react-query-devtools"),
  ]).then(([routerDevtools, reactQueryDevtools]) => {
    return {
      default: () => (
        <>
          <routerDevtools.TanStackRouterDevtools />
          <reactQueryDevtools.ReactQueryDevtools />
        </>
      ),
    };
  });

const TanStackDevtools =
  process.env.NODE_ENV === "production" ? () => null : React.lazy(loadDevtools);

export const Route = createRootRoute({
  component: () => (
    <div className="bg-cds-background min-h-[calc(100dvh-47px)]">
      <Outlet />
      <Suspense>
        <TanStackDevtools />
      </Suspense>
    </div>
  ),
  notFoundComponent: () => <NotFound />,
});
