import { createFileRoute } from "@tanstack/react-router";
import OrchestrateChat from "@/components/watsonx/OrchestrateChat";

export const Route = createFileRoute("/_layout/")({
  component: Dashboard,
});

function Dashboard() {
  return (
    <div className="flex flex-col py-12">
      <div id="wxo-container" className="flex flex-col py-12">
        <OrchestrateChat />
      </div>
    </div>
  );
}
