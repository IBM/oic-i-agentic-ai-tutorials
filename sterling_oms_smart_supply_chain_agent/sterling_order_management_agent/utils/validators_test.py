from utils import validators


def test_is_iso_format() -> None:
    """Test is_iso_format function."""
    test_cases = [
        ("2023-10-20", True),
        ("2023-13-20", False),  # Invalid month
        ("2023-10-32", False),  # Invalid day
        ("2023-10-20T14:30:00", True),
        ("2023-10-20T25:30:00", False),  # Invalid hour
        ("2023-10-20T14:60:00", False),  # Invalid minute
        ("2023-10-20T14:30:60", False),  # Invalid second
        ("2023-10-20T14:30:00.123456", True),  # Microseconds
        ("invalid_date", False),
    ]

    for date_string, expected in test_cases:
        assert validators.is_iso_format(date_string) == expected


def test_is_short_git_hash() -> None:
    """Test is_short_git_hash function."""
    test_cases = [
        ("abcdef123456", True),
        ("1234567890abcdef", True),
        ("12345", True),
        ("12345678901234567890", True),
        ("123g456", False),  # Invalid characters
        ("1234567890g", False),  # Invalid characters
        ("1" * 41, False),  # Exceeds 40 characters
        ("", False),  # Empty string
        (" " * 41, False),  # Exceeds 40 characters with spaces
    ]

    for git_hash, expected in test_cases:
        assert validators.is_short_git_hash(git_hash) == expected


def test_is_valid_svg_string() -> None:
    """Test is_valid_svg_string function."""
    test_cases = [
        # Valid SVG strings
        ("<svg></svg>", True),
        ("<svg><circle cx='50' cy='50' r='40'/></svg>", True),
        ("<svg xmlns='http://www.w3.org/2000/svg'><rect width='100' height='100'/></svg>", True),
        ("<svg>sap_svg_icon</svg>", True),
        ("<svg>oracle_svg_icon</svg>", True),
        ("<svg>workday_svg_icon</svg>", True),
        # Invalid SVG strings
        ("", False),  # Empty string
        ("not an svg", False),  # Plain text
        ("<svg>", False),  # Unclosed tag
        ("</svg>", False),  # Only closing tag
        ("<svg><circle></svg>", False),  # Malformed (unclosed circle)
    ]

    for svg_string, expected in test_cases:
        assert validators.is_valid_svg_string(svg_string) == expected
