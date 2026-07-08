import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";

import { Items } from "../../client";
import { Modal } from "@carbon/react";
import { toast } from "@/components/common/Toaster";

interface DeleteProps {
  type: string;
  id: string;
  isOpen: boolean;
  onClose: () => void;
}

const Delete = ({ type, id, isOpen, onClose }: DeleteProps) => {
  const queryClient = useQueryClient();
  const {
    handleSubmit,
    formState: { isSubmitting },
  } = useForm();

  const deleteEntity = async (id: string) => {
    if (type === "Item") {
      await Items.deleteItem({ path: { id } });
    } else {
      throw new Error(`Unexpected type: ${type}`);
    }
  };

  const mutation = useMutation({
    mutationFn: deleteEntity,
    onSuccess: () => {
      toast.success(`The ${type.toLowerCase()} was deleted successfully.`);
      onClose();
    },
    onError: () => {
      toast.error(
        `An error occurred while deleting the ${type.toLowerCase()}.`,
      );
    },
    onSettled: () => {
      queryClient.invalidateQueries({
        queryKey: [type === "Item" ? "items" : "users"],
      });
    },
  });

  const onSubmit = async () => {
    mutation.mutate(id);
  };

  return (
    <Modal
      open={isOpen}
      onRequestClose={onClose}
      modalHeading={`Delete ${type}`}
      primaryButtonText={isSubmitting ? "Deleting..." : "Delete"}
      primaryButtonDisabled={isSubmitting}
      secondaryButtonText="Cancel"
      onRequestSubmit={handleSubmit(onSubmit)}
      danger
    >
      <div className="py-4">
        {type === "User" && (
          <p>
            All items associated with this user will also be{" "}
            <strong>permanently deleted.</strong>
          </p>
        )}
        <p>Are you sure? You will not be able to undo this action.</p>
      </div>
    </Modal>
  );
};

export default Delete;
