import logging
import re
from typing import Union

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class RequisitionIDError(Exception):
    """
    Custom exception raised when requisition ID is invalid.

    This exception is used to indicate issues such as:
    - No numeric value found in the requisition ID.
    - Multiple numeric values found in the requisition ID.
    """


def extract_requisition_number(req_id: Union[str, int]) -> int:
    """
    Extract a single numeric requisition number from a given ID.

    Args:
        req_id: The requisition number that uniquely identifies the job requisition within Oracle HCM.
            It may be alphanumeric, contain multiple numeric values, or have no numeric value at all.

    Returns:
        int: The extracted numeric requisition number.

    Raises:
        RequisitionIDError: If no numeric value is found or multiple numeric values exist.
    """
    logging.info(f"Normalizing requisition ID: {req_id}")
    req_id_str = str(req_id).strip()
    numbers = re.findall(r"\d+", req_id_str)

    if len(numbers) == 0:
        logging.error("No numeric value found in requisition ID.")
        raise RequisitionIDError("Requisition ID must contain a numeric value.")
    if len(numbers) > 1:
        logging.error("Multiple numeric values found in requisition ID.")
        raise RequisitionIDError("Requisition ID contains multiple numeric values.")

    return int(numbers[0])
