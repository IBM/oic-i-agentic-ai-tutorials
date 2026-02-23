from typing import Any, Dict

threads_test_data: list[Dict[Any, Any]] = [
    {
        "id": "7f520970-f413-4b01-adb9-225645cbdc8f",
        "tenant_id": "70f93689-2b4a-4a61-87d3-00a6cefc7e8d",
        "status": "ready",
        "tenant_name": "wxo-dev",
        "title": "k",
        "assistant_id": None,
        "agent_id": None,
        "created_by": "f242eadf-0dc9-4eae-b2d7-65b09b4b4b16",
        "created_by_username": "wxo.archer@ibm.com",
        "created_on": "2025-06-06T15:36:24.076471Z",
        "updated_at": "2025-06-06T16:24:33.037737Z",
        "deleted_at": None,
        "deleted_by": None,
    },
    {
        "id": "eb49d98c-f1a8-4620-9dc9-444c33765acb",
        "tenant_id": "70f93689-2b4a-4a61-87d3-00a6cefc7e8d",
        "status": "ready",
        "tenant_name": "wxo-dev",
        "title": "I want to see the benefits package for sandra.cullen_etaj-dev23@oraclepdemos.com",
        "assistant_id": None,
        "agent_id": "d81e7a58-f872-476d-b941-99922df02dae",
        "created_by": "f242eadf-0dc9-4eae-b2d7-65b09b4b4b16",
        "created_by_username": "wxo.archer@ibm.com",
        "created_on": "2025-06-05T02:09:43.931549Z",
        "updated_at": "2025-06-06T15:18:13.335414Z",
        "deleted_at": None,
        "deleted_by": None,
    },
]


message_test_data: list[dict[Any, Any]] = [
    {
        "id": "834aca3e-7260-4f59-8035-ca944ee64d13",
        "tenant_id": "e457b05b-e4f4-4659-94a6-d1748b41df8e",
        "created_by": "f242eadf-0dc9-4eae-b2d7-65b09b4b4b16",
        "created_by_username": "wxo.archer@ibm.com",
        "created_on": "2025-08-12T18:35:02.536984Z",
        "updated_at": "2025-08-12T18:35:02.536984Z",
        "thread_id": "721b4ab6-0b96-4f54-a4ec-508849d1e353",
        "assistant": {"is_default": True},
        "parent_message_id": None,
        "role": "user",
        "content": [
            {
                "response_type": "text",
                "text": "Update a phone number of morgan.stanford_etaj-dev23@oraclepdemos.com.",
            }
        ],
        "mentions": None,
        "document_ids": None,
        "additional_properties": None,
        "context": None,
        "step_history": None,
        "message_state": None,
    },
    {
        "id": "3adb7a6e-7950-48b9-b9b1-7466280445e8",
        "tenant_id": "e457b05b-e4f4-4659-94a6-d1748b41df8e",
        "created_by": "f242eadf-0dc9-4eae-b2d7-65b09b4b4b16",
        "created_by_username": "wxo.archer@ibm.com",
        "created_on": "2025-08-12T18:35:20.595816Z",
        "updated_at": "2025-08-12T18:35:20.595816Z",
        "thread_id": "721b4ab6-0b96-4f54-a4ec-508849d1e353",
        "assistant": {"is_default": True},
        "parent_message_id": "834aca3e-7260-4f59-8035-ca944ee64d13",
        "role": "assistant",
        "content": [
            {
                "response_type": "text",
                "id": "1",
                "text": "There are two phone numbers associated with your account. Here are the details:\n\n| Phone Number | Phone Type |\n|--------------|------------|\n| 456-909-3333 | H1         |\n| 55-5386 1125 | W1         |\n\nWhich phone number would you like to update?",
            }
        ],
        "mentions": None,
        "document_ids": None,
        "additional_properties": {"display_properties": {"skip_render": False, "is_async": False}},
        "context": None,
        "step_history": [
            {
                "role": "assistant",
                "step_details": [
                    {
                        "type": "tool_calls",
                        "tool_calls": [
                            {
                                "id": "chatcmpl-tool-970ed3e5b6ee408d987ff14130",
                                "args": {"email": "morgan.stanford_etaj-dev23@oraclepdemos.com"},
                                "name": "oracle_employee_personal_information_agent",
                            }
                        ],
                        "agent_display_name": "oracle_employee_support_manager",
                    }
                ],
            },
            {
                "role": "assistant",
                "step_details": [
                    {
                        "name": "oracle_employee_personal_information_agent",
                        "type": "tool_response",
                        "content": "Transferring to - oracle_employee_personal_information_agent",
                        "tool_call_id": "chatcmpl-tool-970ed3e5b6ee408d987ff14130",
                    },
                    {
                        "args": {"email": "morgan.stanford_etaj-dev23@oraclepdemos.com"},
                        "name": "oracle_employee_personal_information_agent",
                        "type": "tool_call",
                        "tool_call_id": "chatcmpl-tool-970ed3e5b6ee408d987ff14130",
                    },
                ],
            },
            {
                "role": "assistant",
                "step_details": [
                    {
                        "type": "tool_calls",
                        "tool_calls": [
                            {
                                "id": "chatcmpl-tool-f760f673a9f844ac9392dd58ad",
                                "args": {"email": "morgan.stanford_etaj-dev23@oraclepdemos.com"},
                                "name": "oracle_get_user_ids",
                            }
                        ],
                        "agent_display_name": "oracle_employee_personal_information_agent",
                    }
                ],
            },
            {
                "role": "assistant",
                "step_details": [
                    {
                        "name": "oracle_get_user_ids",
                        "type": "tool_response",
                        "content": '{"person_id": 300000049306680, "worker_id": "00020000000EACED00057708000110D9345F1C380000004AACED00057372000D6A6176612E73716C2E4461746514FA46683F3566970200007872000E6A6176612E7574696C2E44617465686A81014B59741903000078707708000001989B93A00078"}',
                        "tool_call_id": "chatcmpl-tool-f760f673a9f844ac9392dd58ad",
                    },
                    {
                        "args": {"email": "morgan.stanford_etaj-dev23@oraclepdemos.com"},
                        "name": "oracle_get_user_ids",
                        "type": "tool_call",
                        "tool_call_id": "chatcmpl-tool-f760f673a9f844ac9392dd58ad",
                    },
                ],
            },
            {
                "role": "assistant",
                "step_details": [
                    {
                        "type": "tool_calls",
                        "tool_calls": [
                            {
                                "id": "chatcmpl-tool-2c7a99fc045b446790a4f4e87c",
                                "args": {
                                    "worker_id": "00020000000EACED00057708000110D9345F1C380000004AACED00057372000D6A6176612E73716C2E4461746514FA46683F3566970200007872000E6A6176612E7574696C2E44617465686A81014B59741903000078707708000001989B93A00078"
                                },
                                "name": "get_phones",
                            }
                        ],
                        "agent_display_name": "oracle_employee_personal_information_agent",
                    }
                ],
            },
            {
                "role": "assistant",
                "step_details": [
                    {
                        "name": "get_phones",
                        "type": "tool_response",
                        "content": '{"phones": [{"area_code": "456", "country_code": "1", "phone_id": 300000306007818, "phone_number": "909-3333", "phone_type": "H1"}, {"area_code": "55", "country_code": "52", "phone_id": 300000049306685, "phone_number": "5386 1125", "phone_type": "W1"}]}',
                        "tool_call_id": "chatcmpl-tool-2c7a99fc045b446790a4f4e87c",
                    },
                    {
                        "args": {
                            "worker_id": "00020000000EACED00057708000110D9345F1C380000004AACED00057372000D6A6176612E73716C2E4461746514FA46683F3566970200007872000E6A6176612E7574696C2E44617465686A81014B59741903000078707708000001989B93A00078"
                        },
                        "name": "get_phones",
                        "type": "tool_call",
                        "tool_call_id": "chatcmpl-tool-2c7a99fc045b446790a4f4e87c",
                    },
                ],
            },
        ],
        "message_state": None,
    },
]

message_test_data_duplicate: list[dict[Any, Any]] = [
    {
        "id": "9e4e836c-2f6a-4e6f-bda4-96bb85a298f6",
        "tenant_id": "59e0e71e-4d84-4b88-bed3-72bf6c667a74",
        "created_by": "f242eadf-0dc9-4eae-b2d7-65b09b4b4b16",
        "created_by_username": "wxo.archer@ibm.com",
        "created_on": "2025-11-21T13:42:14.826633Z",
        "updated_at": "2025-11-21T13:42:14.826633Z",
        "thread_id": "3b983be9-232f-448d-aa60-2954184ddf20",
        "assistant": {"is_default": True},
        "parent_message_id": None,
        "role": "user",
        "content": [
            {
                "response_type": "text",
                "text": "request vacation time off for testuser@example.com",
            }
        ],
        "mentions": None,
        "document_ids": None,
        "additional_properties": None,
        "context": None,
        "step_history": None,
        "message_state": None,
    },
    {
        "id": "a9ff3122-efac-4813-b721-c77d8be61ed1",
        "tenant_id": "59e0e71e-4d84-4b88-bed3-72bf6c667a74",
        "created_by": "f242eadf-0dc9-4eae-b2d7-65b09b4b4b16",
        "created_by_username": "wxo.archer@ibm.com",
        "created_on": "2025-11-21T13:42:42.826127Z",
        "updated_at": "2025-11-21T13:42:42.826127Z",
        "thread_id": "3b983be9-232f-448d-aa60-2954184ddf20",
        "assistant": {"is_default": True},
        "parent_message_id": "9e4e836c-2f6a-4e6f-bda4-96bb85a298f6",
        "role": "assistant",
        "content": [
            {"response_type": "text", "id": "1", "text": "Please provide the absence type name."}
        ],
        "mentions": None,
        "document_ids": None,
        "additional_properties": {"display_properties": {"skip_render": False, "is_async": False}},
        "context": None,
        "step_history": [
            {
                "role": "assistant",
                "step_details": [
                    {
                        "type": "tool_calls",
                        "tool_calls": [
                            {
                                "id": "chatcmpl-tool-cd1903f0d65042809b4030f51a",
                                "args": {
                                    "input_message": "request vacation time off for testuser@example.com"
                                },
                                "name": "oracle_leave_manager_agent",
                            }
                        ],
                        "agent_display_name": "oracle_employee_support_manager",
                    }
                ],
            },
            {
                "role": "assistant",
                "step_details": [
                    {
                        "name": "oracle_leave_manager_agent",
                        "type": "tool_response",
                        "content": "Transferring to - oracle_leave_manager_agent",
                        "tool_call_id": "chatcmpl-tool-cd1903f0d65042809b4030f51a",
                    },
                    {
                        "args": {
                            "input_message": "request vacation time off for testuser@example.com"
                        },
                        "name": "oracle_leave_manager_agent",
                        "type": "tool_call",
                        "tool_call_id": "chatcmpl-tool-cd1903f0d65042809b4030f51a",
                    },
                ],
            },
            {
                "role": "assistant",
                "step_details": [
                    {
                        "type": "tool_calls",
                        "tool_calls": [
                            {
                                "id": "chatcmpl-tool-e89da3f47b194544a7def26a47",
                                "args": {"email": "testuser@example.com"},
                                "name": "oracle_get_user_ids",
                            }
                        ],
                        "agent_display_name": "oracle_leave_manager_agent",
                    }
                ],
            },
            {
                "role": "assistant",
                "step_details": [
                    {
                        "name": "oracle_get_user_ids",
                        "type": "tool_response",
                        "content": '{"error_details": None, "is_success": True, "tool_output": {"person_id": 300000305944804, "worker_id": "00020000000EACED00057708000110D943AB18E40000004AACED00057372000D6A6176612E73716C2E4461746514FA46683F3566970200007872000E6A6176612E7574696C2E44617465686A81014B597419030000787077080000019AA3B5EC0078"}}',
                        "tool_call_id": "chatcmpl-tool-e89da3f47b194544a7def26a47",
                    },
                    {
                        "args": {"email": "testuser@example.com"},
                        "name": "oracle_get_user_ids",
                        "type": "tool_call",
                        "tool_call_id": "chatcmpl-tool-e89da3f47b194544a7def26a47",
                    },
                ],
            },
            {
                "role": "assistant",
                "step_details": [
                    {
                        "type": "tool_calls",
                        "tool_calls": [
                            {
                                "id": "chatcmpl-tool-6ec7798d7b074fca854a820ac0",
                                "args": {"person_id": "300000305944804"},
                                "name": "get_absence_types",
                            }
                        ],
                        "agent_display_name": "oracle_leave_manager_agent",
                    }
                ],
            },
            {
                "role": "assistant",
                "step_details": [
                    {
                        "name": "get_absence_types",
                        "type": "tool_response",
                        "content": '{"error_details": None, "is_success": True, "tool_output": {"absence_types": [{"absence_type_id": 300000257354703, "absence_type_name": "Authorized Leave", "description": "Authorized Leave", "employer_id": 300000046974965, "unit_of_measure": "Calendar Days"}, {"absence_type_id": 300000071752612, "absence_type_name": "Bereavement", "description": "Bereavement Type for all Employees", "employer_id": 300000046974965, "unit_of_measure": "Hours"}, {"absence_type_id": 300000163660194, "absence_type_name": "Compensatory Time Type", "description": "", "employer_id": 300000046974965, "unit_of_measure": "Hours"}, {"absence_type_id": 300000152401556, "absence_type_name": "FMLA", "description": "", "employer_id": 300000046974965, "unit_of_measure": "Days"}, {"absence_type_id": 300000114462108, "absence_type_name": "Jury Duty - US", "description": "", "employer_id": 300000046974965, "unit_of_measure": "Hours"}, {"absence_type_id": 300000151473093, "absence_type_name": "Long Term Disability US", "description": "Long Term Disability to Payroll", "employer_id": 300000046974965, "unit_of_measure": "Days"}, {"absence_type_id": 300000202371246, "absence_type_name": "Parental Leave", "description": "", "employer_id": 300000046974965, "unit_of_measure": "Days"}, {"absence_type_id": 300000151473140, "absence_type_name": "Short Term Disability US", "description": "STD to Payroll", "employer_id": 300000046974965, "unit_of_measure": "Days"}, {"absence_type_id": 300000073800559, "absence_type_name": "Sick", "description": "Sickness Plan for all Employees", "employer_id": 300000046974965, "unit_of_measure": "Hours"}, {"absence_type_id": 300000120002399, "absence_type_name": "Training", "description": "Informational Only Type Absence", "employer_id": 300000046974965, "unit_of_measure": "Hours"}, {"absence_type_id": 300000071752546, "absence_type_name": "Vacation", "description": "Vacation Type for all Employees", "employer_id": 300000046974965, "unit_of_measure": "Hours"}, {"absence_type_id": 300000246067560, "absence_type_name": "Volunteering", "description": "", "employer_id": 300000046974965, "unit_of_measure": "Hours"}]}}',
                        "tool_call_id": "chatcmpl-tool-6ec7798d7b074fca854a820ac0",
                    },
                    {
                        "args": {"person_id": "300000305944804"},
                        "name": "get_absence_types",
                        "type": "tool_call",
                        "tool_call_id": "chatcmpl-tool-6ec7798d7b074fca854a820ac0",
                    },
                ],
            },
            {
                "role": "assistant",
                "step_details": [
                    {
                        "type": "tool_calls",
                        "tool_calls": [
                            {
                                "id": "chatcmpl-tool-5c80547358a449f48f807bbf79",
                                "args": {},
                                "name": "submit_pto_request",
                            }
                        ],
                        "agent_display_name": "oracle_employee_support_manager",
                    }
                ],
            },
        ],
        "message_state": None,
    },
    {
        "id": "d8e96bc2-f265-4fd8-b530-f4938dcffd07",
        "tenant_id": "59e0e71e-4d84-4b88-bed3-72bf6c667a74",
        "created_by": "f242eadf-0dc9-4eae-b2d7-65b09b4b4b16",
        "created_by_username": "wxo.archer@ibm.com",
        "created_on": "2025-11-21T13:42:53.361589Z",
        "updated_at": "2025-11-21T13:42:53.361589Z",
        "thread_id": "3b983be9-232f-448d-aa60-2954184ddf20",
        "assistant": {"is_default": True},
        "parent_message_id": None,
        "role": "user",
        "content": [{"response_type": "text", "text": "Vacation"}],
        "mentions": None,
        "document_ids": None,
        "additional_properties": None,
        "context": None,
        "step_history": None,
        "message_state": None,
    },
    {
        "id": "d21b2098-c57e-43dd-8562-52a4f088a9a0",
        "tenant_id": "59e0e71e-4d84-4b88-bed3-72bf6c667a74",
        "created_by": "f242eadf-0dc9-4eae-b2d7-65b09b4b4b16",
        "created_by_username": "wxo.archer@ibm.com",
        "created_on": "2025-11-21T13:43:01.107369Z",
        "updated_at": "2025-11-21T13:43:01.107369Z",
        "thread_id": "3b983be9-232f-448d-aa60-2954184ddf20",
        "assistant": {"is_default": True},
        "parent_message_id": "d8e96bc2-f265-4fd8-b530-f4938dcffd07",
        "role": "assistant",
        "content": [
            {
                "response_type": "text",
                "id": "1",
                "text": "What is the start date of the requested time off in ISO 8601 format (YYYY-MM-DD)?",
            }
        ],
        "mentions": None,
        "document_ids": None,
        "additional_properties": {"display_properties": {"skip_render": False, "is_async": False}},
        "context": None,
        "step_history": [
            {
                "role": "assistant",
                "step_details": [
                    {
                        "type": "tool_calls",
                        "tool_calls": [
                            {
                                "id": "chatcmpl-tool-33f1e5d884f0470087c19f7a26",
                                "args": {},
                                "name": "submit_pto_request",
                            }
                        ],
                        "agent_display_name": "oracle_employee_support_manager",
                    }
                ],
            },
            {
                "role": "assistant",
                "step_details": [
                    {
                        "type": "tool_calls",
                        "tool_calls": [
                            {
                                "id": "chatcmpl-tool-82325b4567b7416fb8f55b4127",
                                "args": {
                                    "input_message": "submit vacation time off request for testuser@example.com"
                                },
                                "name": "oracle_leave_manager_agent",
                            }
                        ],
                        "agent_display_name": "oracle_employee_support_manager",
                    }
                ],
            },
            {
                "role": "assistant",
                "step_details": [
                    {
                        "type": "tool_calls",
                        "tool_calls": [
                            {
                                "id": "chatcmpl-tool-a73c4c6cd90e4864a22bfe2438",
                                "args": {"absence_type_id": "300000071752546"},
                                "name": "get_absence_reasons",
                            }
                        ],
                        "agent_display_name": "oracle_leave_manager_agent",
                    }
                ],
            },
            {
                "role": "assistant",
                "step_details": [
                    {
                        "name": "get_absence_reasons",
                        "type": "tool_response",
                        "content": '{"error_details": {"details": "GET API call returned no data", "reason": "OK", "recommendation": "Verify the request parameters and ensure the requested resource exists.", "status_code": 200, "url": "https://fa-etaj-dev23-saasfademo1.ds-fa.oraclepdemos.com/hcmRestApi/resources/11.13.18.05/absenceTypeReasonsLOV?links=self&q=AbsenceTypeId%3D300000071752546"}, "is_success": False, "tool_output": None}',
                        "tool_call_id": "chatcmpl-tool-a73c4c6cd90e4864a22bfe2438",
                    },
                    {
                        "args": {"absence_type_id": "300000071752546"},
                        "name": "get_absence_reasons",
                        "type": "tool_call",
                        "tool_call_id": "chatcmpl-tool-a73c4c6cd90e4864a22bfe2438",
                    },
                ],
            },
        ],
        "message_state": None,
    },
    {
        "id": "fcb8c265-3cc6-45a8-8e7b-e6c63fc7c1df",
        "tenant_id": "59e0e71e-4d84-4b88-bed3-72bf6c667a74",
        "created_by": "f242eadf-0dc9-4eae-b2d7-65b09b4b4b16",
        "created_by_username": "wxo.archer@ibm.com",
        "created_on": "2025-11-21T13:43:10.349247Z",
        "updated_at": "2025-11-21T13:43:10.349247Z",
        "thread_id": "3b983be9-232f-448d-aa60-2954184ddf20",
        "assistant": {"is_default": True},
        "parent_message_id": None,
        "role": "user",
        "content": [{"response_type": "text", "text": "2025-11-25"}],
        "mentions": None,
        "document_ids": None,
        "additional_properties": None,
        "context": None,
        "step_history": None,
        "message_state": None,
    },
]
