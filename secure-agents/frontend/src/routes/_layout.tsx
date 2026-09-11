import { Outlet, createFileRoute, redirect } from "@tanstack/react-router";
import { Loading } from "@carbon/react";

import { Header } from "../components/common/Header";
import useAuth, { isLoggedIn } from "../hooks/useAuth";

export const Route = createFileRoute("/_layout")({
  component: Layout,
  beforeLoad: async () => {
    if (!isLoggedIn()) {
      throw redirect({
        to: "/login",
      });
    }
  },
});

function Layout() {
  const { isLoading } = useAuth();

  return (
    <div className="relative">
      <Header />
      {isLoading ? (
        <Loading />
      ) : (
        <div className="mx-auto flex max-w-7xl px-8 pb-24 pt-[47px]">
          <Outlet />
        </div>
      )}
    </div>
  );
}
