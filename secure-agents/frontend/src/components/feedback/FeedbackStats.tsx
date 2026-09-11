import { useQuery } from "@tanstack/react-query";
import { Tile, SkeletonText } from "@carbon/react";
import { ThumbsUp, ThumbsDown } from "@carbon/icons-react";
import { Items } from "../../client";

export default function FeedbackStats() {
  const { data: items, isPending } = useQuery({
    queryFn: () => Items.readItems({ query: { skip: 0, limit: 1000 } }),
    queryKey: ["items", "stats"],
  });

  if (isPending) {
    return (
      <div className="mb-8 grid grid-cols-1 gap-4 md:grid-cols-3">
        <Tile className="p-6">
          <SkeletonText />
        </Tile>
        <Tile className="p-6">
          <SkeletonText />
        </Tile>
        <Tile className="p-6">
          <SkeletonText />
        </Tile>
      </div>
    );
  }

  const feedbackData = items?.data?.data || [];
  const positiveCount = feedbackData.filter(
    (item) => item.feedback_type === "positive",
  ).length;
  const negativeCount = feedbackData.filter(
    (item) => item.feedback_type === "negative",
  ).length;
  const totalCount = feedbackData.length;

  const positivePercentage =
    totalCount > 0 ? Math.round((positiveCount / totalCount) * 100) : 0;
  const negativePercentage =
    totalCount > 0 ? Math.round((negativeCount / totalCount) * 100) : 0;

  return (
    <div className="mb-8">
      <h2 className="mb-4 text-xl font-semibold">Feedback Overview</h2>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {/* Total Feedback */}
        <Tile className="p-6">
          <div className="flex flex-col">
            <span className="text-sm text-cds-text-secondary">
              Total Feedback
            </span>
            <span className="mt-2 text-3xl font-bold">{totalCount}</span>
          </div>
        </Tile>

        {/* Positive Feedback */}
        <Tile className="border-l-4 border-cds-support-success p-6">
          <div className="flex items-start justify-between">
            <div className="flex flex-col">
              <span className="text-sm text-cds-text-secondary">
                Positive Feedback
              </span>
              <span className="mt-2 text-3xl font-bold text-cds-support-success">
                {positiveCount}
              </span>
              <span className="mt-1 text-sm text-cds-text-secondary">
                {positivePercentage}% of total
              </span>
            </div>
            <ThumbsUp size={32} className="text-cds-support-success" />
          </div>
        </Tile>

        {/* Negative Feedback */}
        <Tile className="border-l-4 border-cds-support-error p-6">
          <div className="flex items-start justify-between">
            <div className="flex flex-col">
              <span className="text-sm text-cds-text-secondary">
                Negative Feedback
              </span>
              <span className="mt-2 text-3xl font-bold text-cds-support-error">
                {negativeCount}
              </span>
              <span className="mt-1 text-sm text-cds-text-secondary">
                {negativePercentage}% of total
              </span>
            </div>
            <ThumbsDown size={32} className="text-cds-support-error" />
          </div>
        </Tile>
      </div>

      {/* Visual Bar Chart */}
      {totalCount > 0 && (
        <Tile className="mt-4 p-6">
          <h3 className="mb-4 text-lg font-semibold">Feedback Distribution</h3>
          <div className="flex h-12 w-full overflow-hidden rounded">
            {positiveCount > 0 && (
              <div
                className="flex items-center justify-center bg-cds-support-success font-semibold text-white transition-all"
                style={{ width: `${positivePercentage}%` }}
              >
                {positivePercentage > 10 && `${positivePercentage}%`}
              </div>
            )}
            {negativeCount > 0 && (
              <div
                className="flex items-center justify-center bg-cds-support-error font-semibold text-white transition-all"
                style={{ width: `${negativePercentage}%` }}
              >
                {negativePercentage > 10 && `${negativePercentage}%`}
              </div>
            )}
          </div>
          <div className="mt-4 flex justify-between text-sm">
            <div className="flex items-center gap-2">
              <div className="h-3 w-3 rounded bg-cds-support-success" />
              <span>Positive ({positiveCount})</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="h-3 w-3 rounded bg-cds-support-error" />
              <span>Negative ({negativeCount})</span>
            </div>
          </div>
        </Tile>
      )}
    </div>
  );
}
