import pytest

from agent_ready_tools.utils.extract_requisition_number import (
    RequisitionIDError,
    extract_requisition_number,
)


def test_extract_requisition_number_numeric() -> None:
    """Verifies that the function correctly extracts a numeric requisition ID when input is purely
    numeric."""
    req_id = 12345
    result = extract_requisition_number(req_id)
    assert result == 12345


def test_extract_requisition_number_alphanumeric() -> None:
    """Verifies that the function correctly extracts a numeric requisition ID from an alphanumeric
    string."""
    req_id = "REQ-98765"
    result = extract_requisition_number(req_id)
    assert result == 98765


def test_extract_requisition_number_multiple_numbers() -> None:
    """Verifies that the function raises an error when multiple numeric values are present."""
    req_id = "REQ-123-456"
    with pytest.raises(RequisitionIDError) as exc_info:
        extract_requisition_number(req_id)
    assert "multiple numeric values" in str(exc_info.value)


def test_extract_requisition_number_no_numeric() -> None:
    """Verifies that the function raises an error when no numeric value is present."""
    req_id = "REQ-ABC"
    with pytest.raises(RequisitionIDError) as exc_info:
        extract_requisition_number(req_id)
    assert "must contain a numeric value" in str(exc_info.value)
