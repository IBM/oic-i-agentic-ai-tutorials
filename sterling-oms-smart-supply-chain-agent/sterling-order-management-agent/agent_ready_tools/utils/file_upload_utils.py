def is_non_empty_file_bytes(file_bytes: bytes) -> int:
    """
    Checks if the file is a non-empty bytes object.

    Args:
        file_bytes: The bytes format of the file to be uploaded.

    Returns:
        The result of checking if the file is empty
    """

    return isinstance(file_bytes, bytes) and len(file_bytes)


def file_extension_check(file_name: str) -> bool:
    """
    Checks if the file name includes the file extension.

    Args:
        file_name: Name of the file to be uploaded.

    Returns:
        The result of checking if the file name includes the file extension
    """
    return "." in file_name and bool(file_name.rsplit(".", 1)[-1].strip())


def matching_file_extension(file_name: str, file_bytes: bytes) -> bool:
    """
    Checks if the file_name extension and the uploaded file extension matches.

    Args:
        file_name: Name of the file to be uploaded
        file_bytes: The bytes format of the file to be uploaded

    Returns:
        The result of checking if the file_name extension and the uploaded file extension match
    """
    file_ext_name = file_name.rsplit(".", 1)[-1].lower()

    file_signatures = {
        b"%PDF": ["pdf"],
        b"\xff\xd8\xff": ["jpg", "jpeg"],
        b"\x89PNG\r\n\x1a\n": ["png"],
        b"PK\x03\x04": ["zip", "docx", "xlsx", "pptx", "odt", "ods", "odp"],  # ZIP-based formats
        b"GIF87a": ["gif"],
        b"GIF89a": ["gif"],
        b"\x42\x4d": ["bmp"],  # BMP files
        b"\x49\x49\x2a\x00": ["tif", "tiff"],  # TIFF (little endian)
        b"\x4d\x4d\x00\x2a": ["tif", "tiff"],  # TIFF (big endian)
        b"\x25\x21": ["ps"],  # PostScript
        b"\xd0\xcf\x11\xe0": ["doc", "xls", "ppt"],  # Older MS Office formats
        b"\x7b\x5c\x72\x74\x66": ["rtf"],  # Rich Text Format
        b"\xff\xfb": ["mp3"],  # MP3 audio
        b"\x52\x49\x46\x46": ["avi", "wav", "webp"],  # RIFF container
        b"\x00\x00\x00\x18\x66\x74\x79\x70": ["mp4"],  # MP4 video
        b"\x1f\x8b": ["gz"],  # GZIP
        b"\x75\x73\x74\x61\x72": ["tar"],  # TAR archive
        b"\x3c\x3f\x78\x6d\x6c": ["xml"],  # XML
        b"\xef\xbb\xbf": ["txt"],  # UTF-8 BOM for text files
    }

    for signature, expected_exts in file_signatures.items():
        if file_bytes.startswith(signature) or signature in file_bytes:
            if isinstance(expected_exts, str):
                expected_exts = [expected_exts]
            return file_ext_name in expected_exts

    try:
        file_bytes.decode("utf-8")
        return file_ext_name in ["txt", "log", "csv", "json", "xml", "html"]
    except UnicodeDecodeError:
        return False
