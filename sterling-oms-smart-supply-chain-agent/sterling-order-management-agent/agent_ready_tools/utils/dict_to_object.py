class Obj:
    """This class is used to cast an existing dictionary to object."""

    def __init__(self, dictionary: dict) -> None:
        """
        Args:
            dictionary: A dictionary: {"key": "value"}
        """
        for key, value in dictionary.items():
            if isinstance(value, dict):
                setattr(self, key, Obj(value))  # Recursively convert nested dicts
            else:
                setattr(self, key, value)
