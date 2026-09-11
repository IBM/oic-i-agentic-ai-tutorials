# Agent Validation Framework

## Overview

The Agent Validation Framework helps you test and validate AI agents built with the Agent Development Kit (ADK). It evaluates agent performance by running test cases and measuring how well agents execute tasks, call tools, and provide accurate responses.

**Compatible with ADK version:** 1.10.*

---

## Table of Contents

- [Quick Start](#quick-start)
- [Understanding Test Results](#understanding-test-results)
- [Configuration Guide](#configuration-guide)
- [Working with Patch Data](#working-with-patch-data)
- [Advanced Topics](#advanced-topics)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

### Running Your First Evaluation

**The recommended way to run evaluations is using the framework** with a configuration file. The framework handles environment setup, tool imports, and cleanup automatically.

**Step 1:** Create a configuration file (e.g., `my_config.yaml`):

```yaml
test_paths:
  - agent_validation/adk_test_cases/hr/oracle/employee_support

agent_paths:
  - collaborator_agents/hr/employee_support/oracle_hcm/oracle_employee_support_manager.yaml

output_dir: "agent_validation/results"
env_file: ".env"

env_setup: true
verbose_logging: true
```

**Step 2:** Run the evaluation:

```bash
bash domains evals adk my_config.yaml
```

**Step 3:** Check your results in the output directory specified in your config.

### Where to Find Test Cases

Pre-built test cases are available in: `agent_validation/adk_test_cases/`

The directory is organized by:
- **Domain** (hr, it, procurement, etc.)
- **System** (oracle, sap, workday, etc.)
- **Use case** (employee_support, talent_acquisition, etc.)

### Framework Types

The framework supports two modes:

- **`adk`** - Standard evaluation mode for testing with live APIs
- **`patch`** - Evaluation mode with patch data injection

```bash
# Standard evaluation
bash domains evals adk /path/to/config.yaml

# Evaluation with patch data
bash domains evals patch /path/to/config.yaml
```

---

## Understanding Test Results

After running an evaluation, you'll find a `summary_metrics.txt` file in your output directory. Here's what each metric means:

### Core Metrics

| Metric | What It Measures | What Good Looks Like |
|--------|------------------|---------------------|
| **Journey Success** | Did the agent complete the entire task correctly? | 1.0 (100%) |
| **Tool Call Precision** | Of all tools called, how many were correct? | High (>0.8) |
| **Tool Call Recall** | Did the agent call all the right tools in the right order? | High (>0.8) |
| **Text Match** | How similar is the final response to the expected answer? | High (>0.7) |
| **Agent Routing Accuracy** | Did the agent route to the correct sub-agents? | 1.0 if routing is used |

### Performance Metrics

| Metric | Description |
|--------|-------------|
| **Total Steps** | Total messages/interactions in the conversation |
| **LLM Steps** | Number of assistant responses (text + tool calls) |
| **Total Tool Calls** | Number of tools the agent invoked |
| **Avg Resp Time (sec)** | Average response time per agent interaction |

**Note:** Agent Routing Accuracy defaults to 0.0 if no agent routing occurs in the test.

---

## Configuration Guide

### Using Configuration Files

Configuration files simplify running evaluations by defining all settings in one place.

#### Basic Configuration Example

```yaml
# config.yaml
test_paths:
  - agent_validation/adk_test_cases/hr/sap/employee_support
  - agent_validation/adk_test_cases/hr/sap/employee_support/test_compensation_details.json

agent_paths:
  - collaborator_agents/hr/employee_support/sap_successfactors/sap_employee_support_manager.yaml

output_dir: "agent_validation/test_run"

env_file: ".env"
env_setup: false
env_cleanup: false
verbose_logging: true

threshold: 0.0
```

#### Configuration Parameters

| Parameter | Description | Required |
|-----------|-------------|----------|
| `test_paths` | List of test case files or directories | Yes |
| `agent_paths` | List of agent YAML files to load tools from | Yes |
| `output_dir` | Where to save evaluation results | Yes |
| `env_file` | Path to environment file (defaults to `.env`) | No |
| `env_setup` | Import connections and tools before testing | No |
| `env_cleanup` | Clean up tools after each test | No |
| `verbose_logging` | Enable debug-level logging | No |
| `threshold` | Minimum Journey Success score to pass (0.0-1.0) | No |

#### Running with Configuration

```bash
# Standard evaluation
bash domains evals adk /path/to/config.yaml

# Evaluation with patch data
bash domains evals patch /path/to/config.yaml
```

---

## Working with Patch Data

Patch data allows you to test agents without making real API calls. This is useful for:
- Testing without access to live systems
- Creating reproducible test scenarios
- Avoiding rate limits or costs
- Testing edge cases and error conditions

### Using Patch Data with the Framework

To run evaluations with patch data, use the `patch` framework mode:

```bash
bash domains evals patch /path/to/config.yaml
```

The framework will automatically:
1. Load your patch data files (`.py` files alongside test cases)
2. Inject patch responses into tool calls
3. Run evaluations using patched data instead of live APIs

**Important Notes:**
- Patch data files must exist alongside test cases (same directory, same name, `.py` extension)
- Tests will fail if patch data is not found
- There's no fallback to live API calls

### Generating Patch Data

Patch data files are placed in the same directory as their corresponding test case files:

```
agent_validation/adk_test_cases/
└── hr/oracle/employee_support/
    ├── test_get_address.json          # Test case
    └── test_get_address.py            # Patch data (same folder)
```

**Key Rules:**
1. Patch data files must be in the same directory as their test case
2. Patch data files must have the same name as the test case
3. Use `.py` extension for patch data (instead of `.json`)

#### Automated Patch Generation

The framework provides commands to automatically  patch data files by calling real tools and capturing their responses.

❗Before using this code, you will need to configure all connections required by your tools. ❗

**Generate patch from a tool call config file:**

```bash
bash domains evals patch-tool \
  --config_path agent_ready_tools/utils/call_tools/call_tool_config.yaml \
  --output_path agent_validation/adk_test_cases/hr/sap/employee_support/test_get_benefits_plan.py # example output
```

The config file should specify the tool name and arguments:

```yaml
# call_tool_config.yaml
tool_name: "get_benefits_plan"
tool_args:
  worker_id: "12345"
  effective_date: "2024-01-01"
```

**Generate patch from an ADK test case:**

```bash
bash domains evals patch-test-case \
  --test_case_path agent_validation/adk_test_cases/hr/sap/employee_support/test_get_benefits_plan.json \
  --output_path agent_validation/adk_test_cases/hr/sap/employee_support/test_get_benefits_plan.py
```

This command:
1. Reads the test case JSON file
2. Extracts all tool calls from the `goal_details` array
3. Calls each tool with the specified arguments
4. Generates a complete patch file with all fixture functions
5. Outputs to the specified path or prints to stdout

If `--output_path` is not specified, the generated code is printed to stdout (same as `patch-tool`).

**Benefits of automated generation:**
- Captures real API responses for accurate fixture patching
- Generates proper Pydantic model constructors
- Handles complex nested types automatically
- Includes all necessary imports
- Creates properly formatted `@patch_tool_id` decorators

### Creating Patch Data Functions

Patch data functions use the `@patch_tool_id` decorator to replace real tool calls.

#### Basic Example

```python
from typing import Any
from agent_ready_tools.utils.tool_snapshot.patch import patch_tool_id

@patch_tool_id(
    tool_name="get_user_oracle_ids",
    tool_kwargs={"email": "user@example.com"}
)
def mock_get_user_ids(*args: Any, **kwargs: Any) -> UserOracleIDs:
    """Patch response for get_user_oracle_ids"""
    return UserOracleIDs(person_id=1, worker_id=12345)
```

#### Decorator Parameters

- **`tool_name`** (required): Name of the tool function to patch
- **`tool_kwargs`** (optional): Specific arguments to match. If omitted, matches any call to the tool

#### Matching Priority

When multiple patch functions exist for the same tool, the framework uses the most specific match:

```python
# Highest priority: matches exact arguments
@patch_tool_id(tool_name="example_tool", tool_kwargs={"arg1": 1, "arg2": 2})

# Medium priority: matches partial arguments
@patch_tool_id(tool_name="example_tool", tool_kwargs={"arg1": 1})

# Lowest priority: matches any call
@patch_tool_id(tool_name="example_tool")
```

#### Function Signatures

You have three options for defining function signatures:

**Option 1: Catch-all (simplest)**
```python
def mock_function(*args: Any, **kwargs: Any) -> ToolResponse:
    # Hardcoded response, ignore all arguments
    return ToolResponse(...)
```

**Option 2: Match original tool signature**
```python
# Original tool
def get_emails_ids(worker_id: str) -> ToolResponse[EmailsIdsResponse]:
    ...

# Patch function
def mock_get_emails(worker_id: str) -> ToolResponse[EmailsIdsResponse]:
    # Can use worker_id in custom logic
    return ToolResponse(...)
```

**Option 3: Mixed approach**
```python
def mock_function(required_arg: str, *args, **kwargs) -> ToolResponse:
    # Use required_arg, ignore others
    return ToolResponse(...)
```

### Step-by-Step Patch Data Creation

**1. Create the patch data file**

For test case: `agent_validation/adk_test_cases/hr/oracle/employee_support/test_get_address.json`

Create patch data in the same folder: `agent_validation/adk_test_cases/hr/oracle/employee_support/test_get_address.py`

**2. Run the evaluation to see what's needed**

```bash
bash domains evals patch /path/to/config.yaml
```

You'll see an error like:
```
KeyError: 'No matching patch data. 
tool_name: get_address_types_oracle 
tool_kwargs: {}'
```

**3. Create the patch function**

```python
from agent_ready_tools.utils.tool_snapshot.patch import patch_tool_id

@patch_tool_id(tool_name="get_address_types_oracle", tool_kwargs={})
def mock_address_types() -> ToolResponse[AddressTypeResponse]:
    address_types = [
        AddressTypes(type_id=1, type_name="Home"),
        AddressTypes(type_id=2, type_name="Work")
    ]
    return ToolResponse(
        error_details=None,
        tool_output=AddressTypeResponse(address_types=address_types)
    )
```

**4. Find the return type**

Check the original tool in `agent_ready_tools/tools/` to get the correct return type.

**5. Test and iterate**

```bash
bash domains clear_env local  # Clear environment
bash domains evals patch /path/to/config.yaml  # Run again
```

Repeat until all tool calls have a patch fixture function.

### Patch Data Constraints

- **Imports:** Only code from `agent_ready_tools` can be imported
- **Return types:** Must match the original tool's return type
- **No validation:** The framework doesn't verify return type correctness
- **Function names:** Can be anything; matching is done via decorator metadata

---

## Advanced Topics

### Creating Custom Test Cases

Learn how to build your own test cases:
- [ADK Evaluation Documentation](https://developer.watson-orchestrate.ibm.com/evaluate/overview#ground-truth-datasets)

### Converting Legacy Test Cases

If you have test cases from the deprecated Domains format:

```bash
pants run agent_validation/data_processing/testsuite_builder/convert_to_eval_data.py -- \
  --input_paths <legacy_test_cases> \
  --output_dir <output_location>
```

### Using Threshold Checks

Set a minimum Journey Success score that tests must achieve:

```yaml
threshold: 0.8  # Tests must achieve 80% Journey Success
```

Run with threshold checking:
```bash
pants run agent_validation/adk_validation/threshold_validation.py -- --config_path /path/to/config.yaml
```

The evaluation will pass only if Journey Success ≥ threshold.

---

## Troubleshooting

### Common Issues

**Problem:** Tests fail with "No matching patch data"
- **Solution:** Create a patch data file with the exact tool name and arguments shown in the error

**Problem:** Import errors in patch data files
- **Solution:** Only import from `agent_ready_tools`. Other imports will fail.

**Problem:** Previous results are overwritten
- **Solution:** Use a different `--output-dir` for each evaluation run

**Problem:** Patch data not being used
- **Solution:** Ensure you imported tools with `--mock_eval` flag before running evaluations

### Getting Help

- Check the [ADK Documentation](https://developer.watson-orchestrate.ibm.com)
- Review example test cases in `agent_validation/adk_test_cases/`
- Examine working patch data files (`.py` files) alongside test cases in `agent_validation/adk_test_cases/`

---

## Quick Reference

### Essential Framework Commands

```bash
# Run evaluation with framework (RECOMMENDED)
bash domains evals adk <config.yaml>

# Run evaluation with patch data
bash domains evals patch <config.yaml>

# Clear environment
bash domains clear_env local

# Convert legacy tests
pants run agent_validation/data_processing/testsuite_builder/convert_to_eval_data.py -- \
  --input_paths <input> --output_dir <output>

# Generate patch data from tool call config
pants run agent_validation/framework.py -- patch-tool \
  --config_path <path/to/config.yaml> \
  --output_path <output.py>

# Generate patch data from ADK test case
pants run agent_validation/framework.py -- patch-test-case \
  --test_case_path <path/to/test_case.json> \
  --output_path <output.py>
```

**Note:** For direct ADK commands without the framework, see [Running Evaluations Directly](#running-evaluations-directly-without-framework).

### File Structure

```
agent_validation/
├── adk_test_cases/              # Test cases organized by domain
│   ├── hr/
│   │   ├── test_example.json    # Test case config
│   │   └── test_example.py      # Test case patch data
│   ├── it/
│   └── procurement/
└── README.md                    # This file
```

---

## Running Evaluations Directly (Without Framework)

> **⚠️ Note:** The framework approach (`bash domains evals`) is **strongly recommended** as it handles environment setup, tool imports, and cleanup automatically. Use direct commands only if you have specific requirements that the framework doesn't support.

If you need to run evaluations directly using the ADK command:

```bash
orchestrate evaluations evaluate \
  --test-paths <path_to_test_cases> \
  --output-dir <output_location> \
  --env-file <path_to_env_file>
```

**Example:**
```bash
orchestrate evaluations evaluate \
  --test-paths agent_validation/adk_test_cases/hr/oracle/employee_support \
  --output-dir agent_validation/results \
  --env-file .env
```

**Important Notes:**
- **Manual setup required:** You must import connections and tools before running
- Change the `--output-dir` path for each evaluation run to avoid overwriting previous results
- **No automatic cleanup:** You must manually clean up the environment after testing
- **Framework is preferred:** Use `bash domains evals` instead for automated setup and cleanup

### Running with Patch Data (Direct Method)

> **⚠️ Recommended Alternative:** Use `bash domains evals patch <config.yaml>` instead for automatic patch data handling.

If you must use the direct method:

**Step 1:** Import tools with patch data enabled:

```bash
bash import --manager path/to/manager.yaml --mock_eval
```

**Step 2:** Run evaluations:

```bash
orchestrate evaluations evaluate \
  --test-paths <path_to_test_cases> \
  --output-dir <output_location> \
  --env-file <path_to_env_file>
```

**Limitations:**
- Requires manual import step with `--mock_eval` flag
- Tests will fail if patch data is not found
- No fallback to live API calls
- No automatic cleanup
- **Use the framework instead:** `bash domains evals patch` handles all of this automatically
