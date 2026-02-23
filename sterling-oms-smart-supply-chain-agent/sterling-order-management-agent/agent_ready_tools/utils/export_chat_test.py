from unittest.mock import patch

from agent_ready_tools.clients.swagger_client import WxOSwaggerClient
from agent_ready_tools.utils.archer_api_data.api_data_parser import (
    ChatThread,
    InterlocutorRole,
    WxOApiDataParser,
)
from agent_ready_tools.utils.export_chat import (
    AgentStep,
    ConversationFormatter,
    DialogueTurn,
    WxOApiDataNormalizer,
    row_selection_is_valid,
)
from agent_ready_tools.utils.export_chat_display_data import (
    BUG_REPORT_CHAT,
    NO_FLAGS_CHAT,
    STEPS_CHAT,
    STEPS_MARKDOWN_CHAT,
)
from agent_ready_tools.utils.export_chat_response_data import (
    message_test_data,
    message_test_data_duplicate,
    threads_test_data,
)

golden_normalized_messages = [
    DialogueTurn(
        role=InterlocutorRole.USER,
        text="Update a phone number of morgan.stanford_etaj-dev23@oraclepdemos.com.",
        steps=None,
    ),
    DialogueTurn(
        role=InterlocutorRole.ASSISTANT,
        text="There are two phone numbers associated with your account. Here are the details:\n\n| Phone Number | Phone Type |\n|--------------|------------|\n| 456-909-3333 | H1         |\n| 55-5386 1125 | W1         |\n\nWhich phone number would you like to update?",
        steps=[
            AgentStep(
                name="oracle_employee_personal_information_agent",
                content={},
                args={"email": "morgan.stanford_etaj-dev23@oraclepdemos.com"},
                is_duplicate=True,
            ),
            AgentStep(
                name="oracle_employee_personal_information_agent",
                content="Transferring to - oracle_employee_personal_information_agent",
                args={"email": "morgan.stanford_etaj-dev23@oraclepdemos.com"},
                is_duplicate=False,
            ),
            AgentStep(
                name="oracle_get_user_ids",
                content={},
                args={"email": "morgan.stanford_etaj-dev23@oraclepdemos.com"},
                is_duplicate=True,
            ),
            AgentStep(
                name="oracle_get_user_ids",
                content={
                    "person_id": 300000049306680,
                    "worker_id": "00020000000EACED00057708000110D9345F1C380000004AACED00057372000D6A6176612E73716C2E4461746514FA46683F3566970200007872000E6A6176612E7574696C2E44617465686A81014B59741903000078707708000001989B93A00078",
                },
                args={"email": "morgan.stanford_etaj-dev23@oraclepdemos.com"},
                is_duplicate=False,
            ),
            AgentStep(
                name="get_phones",
                content={},
                args={
                    "worker_id": "00020000000EACED00057708000110D9345F1C380000004AACED00057372000D6A6176612E73716C2E4461746514FA46683F3566970200007872000E6A6176612E7574696C2E44617465686A81014B59741903000078707708000001989B93A00078"
                },
                is_duplicate=True,
            ),
            AgentStep(
                name="get_phones",
                content={
                    "phones": [
                        {
                            "area_code": "456",
                            "country_code": "1",
                            "phone_id": 300000306007818,
                            "phone_number": "909-3333",
                            "phone_type": "H1",
                        },
                        {
                            "area_code": "55",
                            "country_code": "52",
                            "phone_id": 300000049306685,
                            "phone_number": "5386 1125",
                            "phone_type": "W1",
                        },
                    ]
                },
                args={
                    "worker_id": "00020000000EACED00057708000110D9345F1C380000004AACED00057372000D6A6176612E73716C2E4461746514FA46683F3566970200007872000E6A6176612E7574696C2E44617465686A81014B59741903000078707708000001989B93A00078"
                },
                is_duplicate=False,
            ),
        ],
    ),
]

normalize_duplicate_messages = [
    DialogueTurn(
        role=InterlocutorRole.USER,
        text="request vacation time off for testuser@example.com",
        steps=None,
    ),
    DialogueTurn(
        role=InterlocutorRole.ASSISTANT,
        text="Please provide the absence type name.",
        steps=[
            AgentStep(
                name="oracle_leave_manager_agent",
                content={},
                args={"input_message": "request vacation time off for testuser@example.com"},
                is_duplicate=True,
            ),
            AgentStep(
                name="oracle_leave_manager_agent",
                content="Transferring to - oracle_leave_manager_agent",
                args={"input_message": "request vacation time off for testuser@example.com"},
                is_duplicate=False,
            ),
            AgentStep(
                name="oracle_get_user_ids",
                content={
                    "error_details": None,
                    "is_success": True,
                    "tool_output": {
                        "person_id": 300000305944804,
                        "worker_id": "00020000000EACED00057708000110D943AB18E40000004AACED00057372000D6A6176612E73716C2E4461746514FA46683F3566970200007872000E6A6176612E7574696C2E44617465686A81014B597419030000787077080000019AA3B5EC0078",
                    },
                },
                args={"email": "testuser@example.com"},
                is_duplicate=False,
            ),
            AgentStep(
                name="get_absence_types",
                content={
                    "error_details": None,
                    "is_success": True,
                    "tool_output": {
                        "absence_types": [
                            {
                                "absence_type_id": 300000257354703,
                                "absence_type_name": "Authorized Leave",
                                "description": "Authorized Leave",
                                "employer_id": 300000046974965,
                                "unit_of_measure": "Calendar Days",
                            },
                            {
                                "absence_type_id": 300000071752612,
                                "absence_type_name": "Bereavement",
                                "description": "Bereavement Type for all Employees",
                                "employer_id": 300000046974965,
                                "unit_of_measure": "Hours",
                            },
                            {
                                "absence_type_id": 300000163660194,
                                "absence_type_name": "Compensatory Time Type",
                                "description": "",
                                "employer_id": 300000046974965,
                                "unit_of_measure": "Hours",
                            },
                            {
                                "absence_type_id": 300000152401556,
                                "absence_type_name": "FMLA",
                                "description": "",
                                "employer_id": 300000046974965,
                                "unit_of_measure": "Days",
                            },
                            {
                                "absence_type_id": 300000114462108,
                                "absence_type_name": "Jury Duty - US",
                                "description": "",
                                "employer_id": 300000046974965,
                                "unit_of_measure": "Hours",
                            },
                            {
                                "absence_type_id": 300000151473093,
                                "absence_type_name": "Long Term Disability US",
                                "description": "Long Term Disability to Payroll",
                                "employer_id": 300000046974965,
                                "unit_of_measure": "Days",
                            },
                            {
                                "absence_type_id": 300000202371246,
                                "absence_type_name": "Parental Leave",
                                "description": "",
                                "employer_id": 300000046974965,
                                "unit_of_measure": "Days",
                            },
                            {
                                "absence_type_id": 300000151473140,
                                "absence_type_name": "Short Term Disability US",
                                "description": "STD to Payroll",
                                "employer_id": 300000046974965,
                                "unit_of_measure": "Days",
                            },
                            {
                                "absence_type_id": 300000073800559,
                                "absence_type_name": "Sick",
                                "description": "Sickness Plan for all Employees",
                                "employer_id": 300000046974965,
                                "unit_of_measure": "Hours",
                            },
                            {
                                "absence_type_id": 300000120002399,
                                "absence_type_name": "Training",
                                "description": "Informational Only Type Absence",
                                "employer_id": 300000046974965,
                                "unit_of_measure": "Hours",
                            },
                            {
                                "absence_type_id": 300000071752546,
                                "absence_type_name": "Vacation",
                                "description": "Vacation Type for all Employees",
                                "employer_id": 300000046974965,
                                "unit_of_measure": "Hours",
                            },
                            {
                                "absence_type_id": 300000246067560,
                                "absence_type_name": "Volunteering",
                                "description": "",
                                "employer_id": 300000046974965,
                                "unit_of_measure": "Hours",
                            },
                        ]
                    },
                },
                args={"person_id": "300000305944804"},
                is_duplicate=False,
            ),
            AgentStep(name="submit_pto_request", content={}, args={}, is_duplicate=False),
        ],
    ),
    DialogueTurn(role=InterlocutorRole.USER, text="Vacation", steps=None),
    DialogueTurn(
        role=InterlocutorRole.ASSISTANT,
        text="What is the start date of the requested time off in ISO 8601 format (YYYY-MM-DD)?",
        steps=[
            AgentStep(name="submit_pto_request", content={}, args={}, is_duplicate=False),
            AgentStep(
                name="oracle_leave_manager_agent",
                content="Transferring to - oracle_leave_manager_agent",
                args={"input_message": "submit vacation time off request for testuser@example.com"},
                is_duplicate=False,
            ),
            AgentStep(
                name="get_absence_reasons",
                content={
                    "error_details": {
                        "details": "GET API call returned no data",
                        "reason": "OK",
                        "recommendation": "Verify the request parameters and ensure the requested resource exists.",
                        "status_code": 200,
                        "url": "https://fa-etaj-dev23-saasfademo1.ds-fa.oraclepdemos.com/hcmRestApi/resources/11.13.18.05/absenceTypeReasonsLOV?links=self&q=AbsenceTypeId%3D300000071752546",
                    },
                    "is_success": False,
                    "tool_output": None,
                },
                args={"absence_type_id": "300000071752546"},
                is_duplicate=False,
            ),
        ],
    ),
    DialogueTurn(role=InterlocutorRole.USER, text="2025-11-25", steps=None),
]


def test_parse_chat_threads() -> None:
    """Test that the parse_threads function returns the expected response."""

    with patch.object(
        WxOSwaggerClient, "get_request", return_value=threads_test_data
    ) as mock_method:
        client = WxOSwaggerClient(bearer_token="FAKE TOKEN")
        response = client.get_request(f"api/v1/threads")

        assert response == threads_test_data

        parsed_threads = WxOApiDataParser.parse_threads(threads_test_data)

        assert parsed_threads == [
            ChatThread(
                title="k",
                id="7f520970-f413-4b01-adb9-225645cbdc8f",
                created_on="2025-06-06T15:36:24.076471Z",
                updated_at="2025-06-06T16:24:33.037737Z",
            ),
            ChatThread(
                title="I want to see the benefits package for sandra.cullen_etaj-dev23@oraclepdemos.com",
                id="eb49d98c-f1a8-4620-9dc9-444c33765acb",
                created_on="2025-06-05T02:09:43.931549Z",
                updated_at="2025-06-06T15:18:13.335414Z",
            ),
        ]

        mock_method.assert_called_once()


def test_normalize_messages() -> None:
    """Test that the normalize message function returns normalized data."""

    thread_id = "123"

    with patch.object(
        WxOSwaggerClient, "get_request", return_value=message_test_data
    ) as mock_method:
        client = WxOSwaggerClient(bearer_token="FAKE TOKEN")
        response = client.get_request(f"api/v1/threads/{thread_id}/messages")
        parsed_messages = WxOApiDataParser().parse_messages(response)

        normalized_messages = WxOApiDataNormalizer.normalize_messages(parsed_messages)

        assert len(response) == len(normalized_messages)
        assert len(golden_normalized_messages) == len(normalized_messages)
        assert len(message_test_data) == 2

        assert isinstance(normalized_messages[0], DialogueTurn)
        assert isinstance(normalized_messages[1], DialogueTurn)

        # First Message
        message1 = normalized_messages[0]
        golden1 = golden_normalized_messages[0]

        assert message1.role is golden1.role
        assert message1.text == golden1.text
        assert message1.steps is golden1.steps

        # 2nd Message
        message2 = normalized_messages[1]
        golden2 = golden_normalized_messages[1]

        assert message2.role is golden2.role
        assert message2.text == golden2.text
        assert message2.steps == golden2.steps

        mock_method.assert_called_once_with("api/v1/threads/123/messages")


def test_row_selection_is_valid() -> None:
    """Test that selections are valid."""

    threads = [
        ChatThread(title="Sample 1", id="1a", updated_at="2025-05-04", created_on="2025-05-04"),
        ChatThread(title="Sample 2", id="1b", updated_at="2025-05-04", created_on="2025-05-04"),
    ]

    row0, _ = row_selection_is_valid("0", threads)
    assert row0 is False

    row1, _ = row_selection_is_valid("1", threads)
    assert row1

    row2, _ = row_selection_is_valid("2", threads)
    assert row2

    row3, _ = row_selection_is_valid("3", threads)
    assert row3 is False


def test_regular_conversation() -> None:
    """Test chat with no flags."""

    formatted_chat = ConversationFormatter().format_conversation(
        dialogue_turns=golden_normalized_messages,
        include_steps=False,
        markdown=False,
        bug_report=False,
    )

    assert formatted_chat == NO_FLAGS_CHAT


def test_steps_conversation() -> None:
    """Test chat with steps."""

    formatted_chat = ConversationFormatter().format_conversation(
        dialogue_turns=golden_normalized_messages,
        include_steps=True,
        markdown=False,
        bug_report=False,
    )

    assert formatted_chat == STEPS_CHAT


def test_steps_markdown_conversation() -> None:
    """Test chat with steps and markdown."""

    formatted_chat = ConversationFormatter().format_conversation(
        dialogue_turns=golden_normalized_messages,
        include_steps=True,
        markdown=True,
        bug_report=False,
    )

    assert formatted_chat == STEPS_MARKDOWN_CHAT


def test_bug_report_conversation() -> None:
    """Test chat with no flags."""

    formatted_chat = ConversationFormatter().format_conversation(
        dialogue_turns=golden_normalized_messages,
        include_steps=False,
        markdown=False,
        bug_report=True,
    )

    assert formatted_chat == BUG_REPORT_CHAT


def test_message_test_data_duplicate() -> None:
    """Test that the normalize message function returns normalized data."""

    thread_id = "123"

    with patch.object(
        WxOSwaggerClient, "get_request", return_value=message_test_data_duplicate
    ) as mock_method:
        client = WxOSwaggerClient(bearer_token="FAKE TOKEN")
        response = client.get_request(f"api/v1/threads/{thread_id}/messages")
        parsed_messages = WxOApiDataParser().parse_messages(response)

        normalized_messages = WxOApiDataNormalizer.normalize_messages(parsed_messages)

        assert len(response) == len(normalized_messages)
        assert len(normalize_duplicate_messages) == len(normalized_messages)
        assert len(message_test_data_duplicate) == 5

        assert isinstance(normalized_messages[0], DialogueTurn)
        assert isinstance(normalized_messages[1], DialogueTurn)

        # First Message
        message1 = normalized_messages[0]
        golden1 = normalize_duplicate_messages[0]

        assert message1.role is golden1.role
        assert message1.text == golden1.text
        assert message1.steps is golden1.steps

        # 2nd Message
        message2 = normalized_messages[1]
        golden2 = normalize_duplicate_messages[1]
        assert message2.role is golden2.role
        assert message2.text == golden2.text
        assert message2.steps is not None
        assert golden2.steps is not None
        assert message2.steps[0].name == golden2.steps[0].name

        mock_method.assert_called_once_with("api/v1/threads/123/messages")
