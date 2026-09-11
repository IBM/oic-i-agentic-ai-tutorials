import os

CONFIG_PATH = "agent_validation/config"
TEST_CASE_PATH = "agent_validation/test_cases"
TEMPLATE_TEST_SUITE_FILE = "template_test_suite.json"
TRANSFER_TOOL_CALL_PREFIX = "transfer_to_"

TEMPLATE_DIRECTORY = "agent_validation/prompts/"

WATSONX_AI_SERVICE_URL = "https://us-south.ml.cloud.ibm.com"
WATSONX_SPACE_ID = os.getenv("WATSONX_SPACE_ID", None)
WATSONX_APIKEY = os.getenv("WATSONX_APIKEY", None)
