import { createFileRoute } from "@tanstack/react-router";
import { z } from "zod";

const usersSearchSchema = z.object({
  page: z.number().catch(1),
});

export const Route = createFileRoute("/_layout/admin")({
  component: Admin,
  validateSearch: (search) => usersSearchSchema.parse(search),
});

function Admin() {
  return (
    <div className="w-full">
      <h1 className="py-12 text-center text-2xl font-bold sm:text-left">
        Users Management
      </h1>
    </div>
  );
}
