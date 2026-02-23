from agent_ready_tools.utils.archer_api_data.api_data_parser import (
    ChatMessage,
    ChatThread,
    Content,
    InterlocutorRole,
    StepDetail,
    StepHistory,
    StepType,
    ToolCalls,
)

parsed_golden_chat_threads = [
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


golden_parsed_messages = [
    ChatMessage(
        role=InterlocutorRole.USER,
        step_history=None,
        content=[
            Content(
                response_type="text",
                text="Update a phone number of morgan.stanford_etaj-dev23@oraclepdemos.com.",
            )
        ],
    ),
    ChatMessage(
        role=InterlocutorRole.ASSISTANT,
        step_history=[
            StepHistory(
                step_details=[
                    StepDetail(
                        type=StepType.TOOL_CALLS,
                        name=None,
                        args=None,
                        content=None,
                        tool_calls=[
                            ToolCalls(
                                args={"email": "morgan.stanford_etaj-dev23@oraclepdemos.com"},
                                name="oracle_employee_personal_information_agent",
                            )
                        ],
                    )
                ]
            ),
            StepHistory(
                step_details=[
                    StepDetail(
                        type=StepType.TOOL_RESPONSE,
                        name="oracle_employee_personal_information_agent",
                        args=None,
                        content="Transferring to - oracle_employee_personal_information_agent",
                        tool_calls=None,
                    ),
                    StepDetail(
                        type=StepType.TOOL_CALL,
                        name="oracle_employee_personal_information_agent",
                        args={"email": "morgan.stanford_etaj-dev23@oraclepdemos.com"},
                        content=None,
                        tool_calls=None,
                    ),
                ]
            ),
            StepHistory(
                step_details=[
                    StepDetail(
                        type=StepType.TOOL_CALLS,
                        name=None,
                        args=None,
                        content=None,
                        tool_calls=[
                            ToolCalls(
                                args={"email": "morgan.stanford_etaj-dev23@oraclepdemos.com"},
                                name="oracle_get_user_ids",
                            )
                        ],
                    )
                ]
            ),
            StepHistory(
                step_details=[
                    StepDetail(
                        type=StepType.TOOL_RESPONSE,
                        name="oracle_get_user_ids",
                        args=None,
                        content='{"person_id": 300000049306680, "worker_id": "00020000000EACED00057708000110D9345F1C380000004AACED00057372000D6A6176612E73716C2E4461746514FA46683F3566970200007872000E6A6176612E7574696C2E44617465686A81014B59741903000078707708000001989B93A00078"}',
                        tool_calls=None,
                    ),
                    StepDetail(
                        type=StepType.TOOL_CALL,
                        name="oracle_get_user_ids",
                        args={"email": "morgan.stanford_etaj-dev23@oraclepdemos.com"},
                        content=None,
                        tool_calls=None,
                    ),
                ]
            ),
            StepHistory(
                step_details=[
                    StepDetail(
                        type=StepType.TOOL_CALLS,
                        name=None,
                        args=None,
                        content=None,
                        tool_calls=[
                            ToolCalls(
                                args={
                                    "worker_id": "00020000000EACED00057708000110D9345F1C380000004AACED00057372000D6A6176612E73716C2E4461746514FA46683F3566970200007872000E6A6176612E7574696C2E44617465686A81014B59741903000078707708000001989B93A00078"
                                },
                                name="get_phones",
                            )
                        ],
                    )
                ]
            ),
            StepHistory(
                step_details=[
                    StepDetail(
                        type=StepType.TOOL_RESPONSE,
                        name="get_phones",
                        args=None,
                        content='{"phones": [{"area_code": "456", "country_code": "1", "phone_id": 300000306007818, "phone_number": "909-3333", "phone_type": "H1"}, {"area_code": "55", "country_code": "52", "phone_id": 300000049306685, "phone_number": "5386 1125", "phone_type": "W1"}]}',
                        tool_calls=None,
                    ),
                    StepDetail(
                        type=StepType.TOOL_CALL,
                        name="get_phones",
                        args={
                            "worker_id": "00020000000EACED00057708000110D9345F1C380000004AACED00057372000D6A6176612E73716C2E4461746514FA46683F3566970200007872000E6A6176612E7574696C2E44617465686A81014B59741903000078707708000001989B93A00078"
                        },
                        content=None,
                        tool_calls=None,
                    ),
                ]
            ),
        ],
        content=[
            Content(
                response_type="text",
                text="There are two phone numbers associated with your account. Here are the details:\n\n| Phone Number | Phone Type |\n|--------------|------------|\n| 456-909-3333 | H1         |\n| 55-5386 1125 | W1         |\n\nWhich phone number would you like to update?",
            )
        ],
    ),
]
