import { Modal, TextArea, Select, SelectItem } from "@carbon/react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type SubmitHandler, useForm } from "react-hook-form";
import type { AxiosError } from "axios";

import { type FeedbackPublic, type FeedbackUpdate, Items } from "../../client";
import { handleError } from "../../utils";
import { toast } from "../common/Toaster";

interface EditItemProps {
  item: FeedbackPublic;
  isOpen: boolean;
  onClose: () => void;
}

const EditItem = ({ item, isOpen, onClose }: EditItemProps) => {
  const queryClient = useQueryClient();
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting, isDirty },
  } = useForm<FeedbackUpdate>({
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: item,
  });

  const mutation = useMutation({
    mutationFn: (data: FeedbackUpdate) =>
      Items.updateItem({ path: { id: item.id }, body: data }),
    onSuccess: () => {
      toast.success("Feedback updated successfully.");
      onClose();
    },
    onError: (err: AxiosError) => {
      handleError(err);
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["items"] });
    },
  });

  const onSubmit: SubmitHandler<FeedbackUpdate> = (data) => {
    mutation.mutate(data);
  };

  const onCancel = () => {
    reset();
    onClose();
  };

  return (
    <Modal
      open={isOpen}
      onRequestClose={onCancel}
      onRequestSubmit={handleSubmit(onSubmit)}
      modalHeading="Edit Feedback"
      primaryButtonText="Save"
      secondaryButtonText="Cancel"
      primaryButtonDisabled={isSubmitting || !isDirty}
    >
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSubmit(onSubmit)(e);
        }}
      >
        <div className="space-y-4">
          <Select
            id="feedback_type"
            labelText="Feedback Type"
            {...register("feedback_type")}
            invalid={!!errors.feedback_type}
            invalidText={errors.feedback_type?.message}
          >
            <SelectItem value="positive" text="Positive" />
            <SelectItem value="negative" text="Negative" />
          </Select>

          <TextArea
            id="feedback_comment"
            labelText="Comment"
            placeholder="Optional feedback comment"
            rows={3}
            {...register("feedback_comment")}
            invalid={!!errors.feedback_comment}
            invalidText={errors.feedback_comment?.message}
          />

          <TextArea
            id="rated_message"
            labelText="Rated Message (Assistant)"
            placeholder="The assistant message being rated"
            rows={4}
            {...register("rated_message")}
            invalid={!!errors.rated_message}
            invalidText={errors.rated_message?.message}
          />

          <TextArea
            id="user_message_before"
            labelText="User Message Before"
            placeholder="The user's message before the assistant response"
            rows={4}
            {...register("user_message_before")}
            invalid={!!errors.user_message_before}
            invalidText={errors.user_message_before?.message}
          />
        </div>
      </form>
    </Modal>
  );
};

export default EditItem;
