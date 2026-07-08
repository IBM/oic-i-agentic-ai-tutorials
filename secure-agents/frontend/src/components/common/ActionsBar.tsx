import { Button } from "@carbon/react";
import { Add } from "@carbon/icons-react";
import type { ComponentType, ElementType } from "react";
import { useState } from "react";

interface NavbarProps {
  type: string;
  addModalAs: ComponentType | ElementType;
}

const ActionBar = ({ type, addModalAs }: NavbarProps) => {
  const [isModalOpen, setIsModalOpen] = useState(false);

  const AddModal = addModalAs;
  return (
    <>
      <div className="flex gap-4 py-8">
        <Button
          kind="primary"
          className="md:text-base text-sm"
          onClick={() => setIsModalOpen(true)}
          renderIcon={Add}
        >
          Add {type}
        </Button>
        <AddModal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} />
      </div>
    </>
  );
};

export default ActionBar;
