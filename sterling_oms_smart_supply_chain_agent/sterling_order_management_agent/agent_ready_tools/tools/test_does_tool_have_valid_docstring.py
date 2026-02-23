from ibm_watsonx_orchestrate.agent_builder.tools import tool

from agent_ready_tools.utils.tool_docstring import validate_google_style_docstring


def test_tool_missing_argument_docstring() -> None:
    """Test that a tool argument with a missing docstring description fails validation."""

    # missing docstring description for arg_2
    @tool
    def missing_arg_docstring(arg_1: str, arg_2: str) -> str:  # noqa: DOC101
        """
        Helper function to assert that a tool argument is missing a docstring description.

        Args:
            arg_1: arg 1 description.

        Returns:
            String saying "Finished!"
        """
        return "Finished!"

    validation_result = validate_google_style_docstring(missing_arg_docstring)

    assert not validation_result.is_valid
    assert len(validation_result.arguments_with_errors) == 1
    assert validation_result.arguments_with_errors[0].tool_argument.argument_name == "Arg 2"
    assert validation_result.arguments_with_errors[0].tool_argument.argument_description is None


def test_tool_missing_docstring() -> None:
    """Test that a tool with no docstring fails validation."""

    # missing docstring description for both arguments
    @tool
    def missing_docstring(arg_1: str, arg_2: str) -> None:
        return

    validation_result = validate_google_style_docstring(missing_docstring)

    assert not validation_result.is_valid
    assert validation_result.docstring_missing


def test_incorrect_docstring_format() -> None:
    """Test that a tool argument with an incorrect docstring format fails validation."""

    # uses reStructuredText format instead of Google style
    @tool
    def rst_docstring(arg_1: str, arg_2: str) -> None:  # noqa: DOC003
        """
        Does a thing.

        :param arg_1: arg 1 description.
        :param arg_2: arg 2 description.
        """

    validation_result = validate_google_style_docstring(rst_docstring)

    assert not validation_result.is_valid
    assert len(validation_result.arguments_with_errors) == 2
    assert validation_result.arguments_with_errors[0].tool_argument.argument_name == "Arg 1"
    assert validation_result.arguments_with_errors[0].tool_argument.argument_description is None
    assert validation_result.arguments_with_errors[1].tool_argument.argument_name == "Arg 2"
    assert validation_result.arguments_with_errors[1].tool_argument.argument_description is None
    assert validation_result.return_error


def test_tool_multi_line_colon() -> None:
    """Test that a tool argument with a colon on the second line of the argument description fails
    validation."""

    # colon on the second line of the argument description should cause failure
    @tool
    def colon_on_second_line(arg_1: str, arg_2: str) -> str:
        """
        Helper function to assert that a tool argument is missing a docstring description.

        Args:
            arg_1: arg 1 description.
                Colon (:) on this line should cause failure
            arg_2: arg 2 description.

        Returns:
            String saying "Finished!"
        """
        return "Finished!"

    validation_result = validate_google_style_docstring(colon_on_second_line)

    assert not validation_result.is_valid
    assert len(validation_result.arguments_with_errors) == 2
    assert validation_result.arguments_with_errors[0].tool_argument.argument_name == "Arg 1"
    assert validation_result.arguments_with_errors[0].tool_argument.argument_description is None
    # arg 2 also fails when arg 1 fails
    assert validation_result.arguments_with_errors[1].tool_argument.argument_name == "Arg 2"
    assert validation_result.arguments_with_errors[1].tool_argument.argument_description is None


def test_correct_format() -> None:
    """Test that a tool with correctly formatted docstring passes validation."""

    # correct google style docstring for tool arguments
    @tool
    def correct_google_style(arg_1: str, arg_2: str) -> str:
        """
        Helper function to assert that a tool argument is missing a docstring description.

        Args:
            arg_1: arg 1 description. Colon (:) on this line should be fine.
            arg_2: arg 2 description.

        Returns:
            String saying "Finished!"
        """
        return "Finished!"

    validation_result = validate_google_style_docstring(correct_google_style)

    assert validation_result.is_valid
    assert (
        len(validation_result.arguments_with_errors) == 0
    ), "All tool arguments should have valid docstring descriptions."


def test_tool_missing_args() -> None:
    """Test that a tool that accepts some arguments but Args section missing fails the
    validation."""

    # tool accepts arguments but doesn't have Args section in the docstring
    @tool
    def missing_args(arg_1: str, arg_2: str) -> str:  # noqa: DOC101
        """
        Helper function.

        Returns:
            String saying "Finished!"
        """
        return "Finished!"

    validation_result = validate_google_style_docstring(missing_args)
    assert validation_result.arguments_with_errors[0].tool_argument.argument_name == "Arg 1"
    assert validation_result.arguments_with_errors[0].tool_argument.argument_description is None
    assert validation_result.arguments_with_errors[1].tool_argument.argument_name == "Arg 2"
    assert validation_result.arguments_with_errors[1].tool_argument.argument_description is None

    assert not validation_result.is_valid


def test_tool_without_arguments() -> None:
    """Test that a tool that doesn't accept any arguments passes validation when it doesn't have
    Args section in the docstring."""

    # tool doesn't accept arguments and doesn't have Args section in the docstring
    @tool
    def no_args() -> str:
        """
        Helper function to assert that a tool argument is missing a docstring description.

        Returns:
            String saying "Finished!"
        """
        return "Finished!"

    validation_result = validate_google_style_docstring(no_args)

    assert validation_result.is_valid
    assert (
        len(validation_result.arguments_with_errors) == 0
    ), "All tool arguments should have valid docstring descriptions."


def test_tool_missing_returns() -> None:
    """
    Test that a tool that doesn't have 'Returns' section fails the validation.

    Since the tools are AI agents' tools, they always return something, so we should always have a
    'Returns' section
    """

    # tool doesn't have returns section
    @tool
    def missing_returns(arg_1: str, arg_2: str) -> str:  # noqa: DOC201
        """
        Helper function to assert that a Returns section is missing in the docstring.

        Args:
            arg_1: arg 1 description. Colon (:) on this line should be fine.
            arg_2: arg 2 description.
        """
        return "Finished!"

    validation_result = validate_google_style_docstring(missing_returns)

    assert not validation_result.is_valid
    assert validation_result.return_error


def test_tool_wrong_returns_indentation() -> None:
    """Test that a tool with wrong indentation in the 'Returns' section fails the validation."""

    # tool's 'Returns' section has a line that's not indented - is omitted when parsing Python Tool
    @tool
    def wrong_indentation(arg_1: str, arg_2: str) -> str:
        """
        Helper function to assert that a Returns section is missing in the docstring.

        Args:
            arg_1: arg 1 description. Colon (:) on this line should be fine.
            arg_2: arg 2 description.

        Returns:
            String saying:
        Finished!
        """
        return "Finished!"

    validation_result = validate_google_style_docstring(wrong_indentation)

    assert not validation_result.is_valid
    assert validation_result.return_error
