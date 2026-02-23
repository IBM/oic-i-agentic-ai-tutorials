import locale


def integer_readable_format(number: int | str, style: str = "long_int") -> str:
    """
    Formats an integer to be more human-readable, with options for currency.

    Args:
        number: The integer to format, or empty string "".
        style: The formatting style.
            "long_int": Adds comma separators (e.g., 50000 -> 50,000).
            "dollar": Adds a '$' prefix and comma separators (e.g., 377595000 -> $377,595,000).

    Returns:
        The formatted string, or an empty string if the input was "".
    """
    if number == "":
        return ""

    if not isinstance(number, int):
        raise TypeError("Input 'number' must be an integer.")

    try:
        locale.setlocale(locale.LC_ALL, "en_US.UTF-8")
    except locale.Error:
        # Fallback if locale setting fails
        # If so, rely on the f-string formatting directly.
        pass

    current_locale_setting = locale.getlocale()[0] or ""

    if style == "long_int":
        return f"{number:n}" if "en_US.UTF-8" in current_locale_setting else f"{number:,}"
    elif style == "dollar":
        return f"${number:n}" if "en_US.UTF-8" in current_locale_setting else f"${number:,}"
    else:
        raise ValueError(f"Unsupported style: '{style}'. Choose 'long_int' or 'dollar'.")
