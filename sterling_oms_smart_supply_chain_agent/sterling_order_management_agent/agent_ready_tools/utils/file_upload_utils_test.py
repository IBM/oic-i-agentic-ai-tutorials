from agent_ready_tools.utils import file_upload_utils


def test_is_non_empty_file_bytes() -> None:
    """Verifies that `is_non_empty_file_bytes` functions."""
    test_cases = [(b"Some content", True), (b"", False)]
    for file_bytes, expected in test_cases:
        result = file_upload_utils.is_non_empty_file_bytes(file_bytes)
        assert bool(result) == expected


def test_file_extension_check() -> None:
    """Verifies that `file_extension_check` functions."""
    test_cases = [
        ("Test_file.txt", True),
        ("Test_file", False),
        ("Test_file.", False),  # edge case: dot but no extension
        ("Test.file.name.doc", True),  # multiple dots
    ]
    expected = True
    for file_name, expected in test_cases:
        result = file_upload_utils.file_extension_check(file_name)
        assert result == expected


def test_matching_file_extension() -> None:
    """Verifies that `matching_file_extension` functions."""

    test_cases = [
        ("text.txt", b"Sample text content", True),  # UTF-8 decodable, matches 'txt'
        ("test_image.jpg", b"\xff\xd8\xff\xe0" + b"JPEG image data", True),  # JPEG signature
        ("test_file.pdf", b"%PDF-1.4", True),  # PDF signature
        (
            "test_file.pdf",
            b"\xff\xd8\xff\xe0" + b"JPEG image data",
            False,
        ),  # PDF name, JPEG content
        ("test_image.jpg", b"%PDF-1.4", False),  # JPG name, PDF content
    ]

    for file_name, file_bytes, expected in test_cases:
        result = file_upload_utils.matching_file_extension(file_name, file_bytes)
        assert result == expected
