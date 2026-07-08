import {
  DataTable,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  Button,
  Tag,
} from "@carbon/react";
import { ThumbsUp, ThumbsDown } from "@carbon/icons-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useSearch } from "@tanstack/react-router";
import { useEffect } from "react";

import { Items } from "../../client";
import ActionsMenu from "../common/ActionsMenu";

const PER_PAGE = 10;

function getItemsQueryOptions({ page }: { page: number }) {
  return {
    queryFn: async () => {
      const response = await Items.readItems({
        query: { skip: (page - 1) * PER_PAGE, limit: PER_PAGE },
      });
      return response.data;
    },
    queryKey: ["items", { page }],
  };
}

export default function FeedbackTable() {
  const queryClient = useQueryClient();
  const navigate = useNavigate({ from: "/feedback" });
  const { page } = useSearch({ from: "/_layout/feedback" });
  const setPage = (newPage: number) =>
    navigate({ search: () => ({ page: newPage }) });

  const {
    data: items,
    isPending,
    isPlaceholderData,
  } = useQuery({
    ...getItemsQueryOptions({ page }),
    placeholderData: (prevData) => prevData,
  });

  const hasNextPage = !isPlaceholderData && items?.data.length === PER_PAGE;
  const hasPreviousPage = page > 1;

  useEffect(() => {
    if (hasNextPage) {
      queryClient.prefetchQuery(getItemsQueryOptions({ page: page + 1 }));
    }
  }, [page, queryClient, hasNextPage]);

  const headers = [
    { header: "Feedback Type", key: "feedback_type" },
    { header: "Comment", key: "feedback_comment" },
    { header: "Rated Message", key: "rated_message" },
    { header: "User Message", key: "user_message_before" },
    { header: "Actions", key: "actions" },
  ];

  const rows =
    items?.data.map((item) => ({
      id: item.id,
      feedback_type: (
        <div className="flex items-center gap-2">
          {item.feedback_type === "positive" ? (
            <>
              <ThumbsUp size={20} className="text-cds-support-success" />
              <Tag type="green" size="sm">
                Positive
              </Tag>
            </>
          ) : (
            <>
              <ThumbsDown size={20} className="text-cds-support-error" />
              <Tag type="red" size="sm">
                Negative
              </Tag>
            </>
          )}
        </div>
      ),
      feedback_comment: (
        <div
          className={`max-w-[200px] truncate ${!item.feedback_comment ? "text-cds-text-placeholder" : ""}`}
        >
          {item.feedback_comment || "No comment"}
        </div>
      ),
      rated_message: (
        <div
          className={`max-w-[250px] truncate ${!item.rated_message ? "text-cds-text-placeholder" : ""}`}
        >
          {item.rated_message || "N/A"}
        </div>
      ),
      user_message_before: (
        <div
          className={`max-w-[250px] truncate ${!item.user_message_before ? "text-cds-text-placeholder" : ""}`}
        >
          {item.user_message_before || "N/A"}
        </div>
      ),
      actions: <ActionsMenu type="Item" value={item} />,
    })) || [];

  return (
    <>
      <DataTable rows={rows} headers={headers}>
        {({ rows, headers, getHeaderProps, getTableProps }) => (
          <Table {...getTableProps()}>
            <TableHead>
              <TableRow>
                {headers.map((header) => (
                  <TableHeader
                    {...getHeaderProps({ header, isSortable: false })}
                    key={header.key}
                  >
                    {header.header}
                  </TableHeader>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {isPending ? (
                <TableRow>
                  {headers.map((_, i) => (
                    <TableCell key={i}>
                      <div className="h-4 w-full animate-pulse bg-gray-200" />
                    </TableCell>
                  ))}
                </TableRow>
              ) : (
                rows.map((row) => (
                  <TableRow key={row.id}>
                    {row.cells.map((cell, i) => (
                      <TableCell key={i}>{cell.value}</TableCell>
                    ))}
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        )}
      </DataTable>
      <div className="mt-4 flex items-center justify-end gap-4">
        <Button
          kind="secondary"
          onClick={() => setPage(page - 1)}
          disabled={!hasPreviousPage}
        >
          Previous
        </Button>
        <span>Page {page}</span>
        <Button
          kind="primary"
          disabled={!hasNextPage}
          onClick={() => setPage(page + 1)}
        >
          Next
        </Button>
      </div>
    </>
  );
}
