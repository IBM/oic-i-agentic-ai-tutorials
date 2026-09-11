from pydantic_extra_types.semantic_version import SemanticVersion  # pants: no-infer-dep


def is_valid_version(version_str: str) -> str:
    """
    Version format validator. Accepts formats such as 'x.y.z' (i.e. '1.3.2', '2.3.2-beta',
    '3.0.0-rc.1')

    For information on all valid version types accepted, please refer to:
    https://packaging.python.org/en/latest/specifications/version-specifiers/

    Args:
        version_str: the version string to validate for proper format

    Returns:
        the version string, if valid. Otherwise, throws a ValueError.
    """
    try:
        SemanticVersion.validate_from_str(value=version_str)
    except ValueError:
        raise ValueError(
            f"Invalid version format: '{version_str}'. Valid formats: 'x.y.z' (i.e. '1.3.2', "
            "'2.3.2-beta', '3.0.0-rc.1')"
        )
    return version_str
