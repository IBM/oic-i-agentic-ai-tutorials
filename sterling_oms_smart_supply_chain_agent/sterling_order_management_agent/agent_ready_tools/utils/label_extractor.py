from typing import Any


def get_first_en_label(labels: list[dict[str, Any]]) -> str:
    """
    Extracts the name of the first english label from a dictionary of labels.

    Args:
        labels: A dictionary of labels.

    Returns:
        The name of the first english label.
    """
    return next(label["label"] for label in labels if label["locale"].startswith("en_"))
