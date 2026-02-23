# pylint: skip-file
# flake8: noqa

import pathlib
from typing import Optional

import flake8.style_guide  # pants: no-infer-dep


class Plugin:
    name = __name__
    version = "0.0.0"

    def __init__(self, tree):
        pass

    @classmethod
    def add_options(cls, parser):
        """Add plugin configuration option to flake8."""
        parser.add_option(
            "--test-ignores",
            action="store",
            parse_from_config=True,
            comma_separated_list=True,
            default=[],
            help=("What codes to ignore for just test files. Gets appended to `ignore`."),
        )

    def run(self):
        return []


actual_handle_error = flake8.style_guide.StyleGuide.handle_error


def handle_error(
    self,
    code: str,
    filename: str,
    line_number: int,
    column_number: Optional[int],
    text: str,
    physical_line: Optional[str] = None,
) -> int:
    path = pathlib.Path(filename)
    is_test = (
        path.stem.startswith("test_") or path.stem.endswith("_test") or path.stem == "conftest"
    )
    if is_test and code in self.options.test_ignores:
        return 0

    return actual_handle_error(
        self,
        code,
        filename,
        line_number,
        column_number,
        text,
        physical_line,
    )


flake8.style_guide.StyleGuide.handle_error = handle_error
