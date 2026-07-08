import { useState } from "react";
import { OverflowMenu, OverflowMenuItem } from "@carbon/react";
import { Edit, TrashCan } from "@carbon/icons-react";

import type { FeedbackPublic, UserPublic } from "../../client";
import EditItem from "../feedback/EditItem";
import Delete from "./DeleteAlert";

interface ActionsMenuProps {
  type: string;
  value: FeedbackPublic | UserPublic;
  disabled?: boolean;
}

const ActionsMenu = ({ type, value }: ActionsMenuProps) => {
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);

  return (
    <>
      <OverflowMenu size="sm" flipped aria-label="Actions menu">
        <OverflowMenuItem
          itemText={
            <div className="flex items-center gap-2">
              <Edit size={16} /> Edit {type}
            </div>
          }
          onClick={() => setIsEditModalOpen(true)}
        />
        <OverflowMenuItem
          itemText={
            <div className="flex items-center gap-2">
              <TrashCan size={16} /> Delete {type}
            </div>
          }
          onClick={() => setIsDeleteModalOpen(true)}
          isDelete
          hasDivider
        />
      </OverflowMenu>
      <EditItem
        item={value as FeedbackPublic}
        isOpen={isEditModalOpen}
        onClose={() => setIsEditModalOpen(false)}
      />
      <Delete
        type={type}
        id={value.id}
        isOpen={isDeleteModalOpen}
        onClose={() => setIsDeleteModalOpen(false)}
      />
    </>
  );
};

export default ActionsMenu;
