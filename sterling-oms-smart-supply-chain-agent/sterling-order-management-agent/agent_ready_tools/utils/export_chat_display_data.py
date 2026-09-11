BUG_REPORT_CHAT = """\
EXPECTED BEHAVIOR
What were the earliest dialogue turn and reasoning step containing something unexpected?
Dialogue Turn:
Reasoning Step:
The expected output at this line was:


1. USER: Update a phone number of morgan.stanford_etaj-dev23@oraclepdemos.com.
2. ASSISTANT: There are two phone numbers associated with your account. Here are the details:

| Phone Number | Phone Type |
|--------------|------------|
| 456-909-3333 | H1         |
| 55-5386 1125 | W1         |

Which phone number would you like to update?\
"""


NO_FLAGS_CHAT = """\
1. USER: Update a phone number of morgan.stanford_etaj-dev23@oraclepdemos.com.
2. ASSISTANT: There are two phone numbers associated with your account. Here are the details:

| Phone Number | Phone Type |
|--------------|------------|
| 456-909-3333 | H1         |
| 55-5386 1125 | W1         |

Which phone number would you like to update?\
"""


STEPS_CHAT = """\
1. USER: Update a phone number of morgan.stanford_etaj-dev23@oraclepdemos.com.

Step 1:


Tool: oracle_employee_personal_information_agent


Input - 3 Lines
{
    "email": "morgan.stanford_etaj-dev23@oraclepdemos.com"
}


Output - 1 Line
Transferring to - oracle_employee_personal_information_agent

Step 2:


Tool: oracle_get_user_ids


Input - 3 Lines
{
    "email": "morgan.stanford_etaj-dev23@oraclepdemos.com"
}


Output - 4 Lines
{
    "person_id": 300000049306680,
    "worker_id": "00020000000EACED00057708000110D9345F1C380000004AACED00057372000D6A6176612E73716C2E4461746514FA46683F3566970200007872000E6A6176612E7574696C2E44617465686A81014B59741903000078707708000001989B93A00078"
}

Step 3:


Tool: get_phones


Input - 3 Lines
{
    "worker_id": "00020000000EACED00057708000110D9345F1C380000004AACED00057372000D6A6176612E73716C2E4461746514FA46683F3566970200007872000E6A6176612E7574696C2E44617465686A81014B59741903000078707708000001989B93A00078"
}


Output - 18 Lines
{
    "phones": [
        {
            "area_code": "456",
            "country_code": "1",
            "phone_id": 300000306007818,
            "phone_number": "909-3333",
            "phone_type": "H1"
        },
        {
            "area_code": "55",
            "country_code": "52",
            "phone_id": 300000049306685,
            "phone_number": "5386 1125",
            "phone_type": "W1"
        }
    ]
}
2. ASSISTANT: There are two phone numbers associated with your account. Here are the details:

| Phone Number | Phone Type |
|--------------|------------|
| 456-909-3333 | H1         |
| 55-5386 1125 | W1         |

Which phone number would you like to update?\
"""


STEPS_MARKDOWN_CHAT = """\
**1. USER**: Update a phone number of morgan.stanford_etaj-dev23@oraclepdemos.com.

**Step 1:**


Tool: oracle_employee_personal_information_agent


Input - 3 Lines
```python
{
    "email": "morgan.stanford_etaj-dev23@oraclepdemos.com"
}
```


Output - 1 Line
```
Transferring to - oracle_employee_personal_information_agent
```

**Step 2:**


Tool: oracle_get_user_ids


Input - 3 Lines
```python
{
    "email": "morgan.stanford_etaj-dev23@oraclepdemos.com"
}
```


Output - 4 Lines
```python
{
    "person_id": 300000049306680,
    "worker_id": "00020000000EACED00057708000110D9345F1C380000004AACED00057372000D6A6176612E73716C2E4461746514FA46683F3566970200007872000E6A6176612E7574696C2E44617465686A81014B59741903000078707708000001989B93A00078"
}
```

**Step 3:**


Tool: get_phones


Input - 3 Lines
```python
{
    "worker_id": "00020000000EACED00057708000110D9345F1C380000004AACED00057372000D6A6176612E73716C2E4461746514FA46683F3566970200007872000E6A6176612E7574696C2E44617465686A81014B59741903000078707708000001989B93A00078"
}
```


Output - 18 Lines
```python
{
    "phones": [
        {
            "area_code": "456",
            "country_code": "1",
            "phone_id": 300000306007818,
            "phone_number": "909-3333",
            "phone_type": "H1"
        },
        {
            "area_code": "55",
            "country_code": "52",
            "phone_id": 300000049306685,
            "phone_number": "5386 1125",
            "phone_type": "W1"
        }
    ]
}
```
**2. ASSISTANT**: There are two phone numbers associated with your account. Here are the details:

| Phone Number | Phone Type |
|--------------|------------|
| 456-909-3333 | H1         |
| 55-5386 1125 | W1         |

Which phone number would you like to update?\
"""
