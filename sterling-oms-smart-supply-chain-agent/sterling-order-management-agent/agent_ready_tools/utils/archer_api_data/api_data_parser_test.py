from agent_ready_tools.utils.archer_api_data.api_data_parser import WxOApiDataParser
from agent_ready_tools.utils.archer_api_data.api_test_data import (
    golden_parsed_messages,
    parsed_golden_chat_threads,
)
from agent_ready_tools.utils.export_chat_response_data import message_test_data, threads_test_data


def test_parse_chat_threads() -> None:
    """Test that the parse_threads function returns the expected response."""

    parsed_threads = WxOApiDataParser.parse_threads(threads_test_data)

    assert len(parsed_threads) == len(parsed_golden_chat_threads)
    assert parsed_threads[0] == parsed_golden_chat_threads[0]
    assert parsed_threads[1] == parsed_golden_chat_threads[1]


def test_parse_chat_message() -> None:
    """Test that the parse_messages function returns the expected response."""

    parsed_messages = WxOApiDataParser.parse_messages(message_test_data)

    assert len(parsed_messages) == len(golden_parsed_messages)
    assert parsed_messages[0] == golden_parsed_messages[0]
    assert parsed_messages[1] == golden_parsed_messages[1]
