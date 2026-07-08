import { createFileRoute } from "@tanstack/react-router";
import { z } from "zod";

import FeedbackStats from "@/components/feedback/FeedbackStats";
import FeedbackTable from "@/components/feedback/FeedbackTable";

const feedbackSearchSchema = z.object({
  page: z.number().catch(1),
});

export const Route = createFileRoute("/_layout/feedback")({
  component: Feedback,
  validateSearch: (search) => feedbackSearchSchema.parse(search),
});

function Feedback() {
  return (
    <div className="w-full">
      <h1 className="py-12 text-center text-2xl font-bold sm:text-left">
        Feedback Management
      </h1>

      <FeedbackStats />

      <div className="mt-8">
        <FeedbackTable />
      </div>
    </div>
  );
}
