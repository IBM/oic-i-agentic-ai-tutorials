import { useState } from "react";
import { Button, Tile } from "@carbon/react";

const DeleteAccount = () => {
  const [, setIsOpen] = useState(false);
  const openModal = () => setIsOpen(true);

  return (
    <Tile className="max-w-md">
      <h3 className="mb-4 text-lg font-medium">Delete Account</h3>
      <div className="space-y-4 py-4">
        <p className="text-sm text-gray-600">
          Permanently delete your data and everything associated with your
          account.
        </p>
        <Button kind="danger" onClick={openModal}>
          Delete
        </Button>
      </div>
    </Tile>
  );
};

export default DeleteAccount;
