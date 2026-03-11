# Employee Appraisal Workflow for watsonx Orchestrate

A comprehensive employee appraisal system that processes employee data in parallel, calculates performance scores, determines ratings, and generates salary recommendations with downloadable Excel reports.

## 📋 Overview

This project provides an automated employee appraisal system with:
- **Parallel Processing** - Processes multiple employees simultaneously for fast results
- **Comprehensive Scoring** - Evaluates revenue achievement, experience, and loyalty
- **Automated Ratings** - Assigns performance ratings from Outstanding to Unsatisfactory
- **Salary Recommendations** - Calculates increment percentages and new salaries
- **Excel Reports** - Generates downloadable Excel files with complete results

## 🏗️ Architecture

### Components

1. **appraisal_tools.py** - Python tools for data processing
   - `read_employee_data` - Reads Excel/CSV from S3 URLs
   - `calculate_employee_appraisal` - Calculates appraisal for one employee
   - `generate_appraisal_excel` - Generates downloadable Excel file

2. **employee_appraisal_workflow.py** - Workflow orchestration
   - File upload handling
   - Parallel foreach processing
   - Excel generation
   - Result output with download link

3. **appraisal_agent.yaml** - Agent configuration
   - HR Appraisal Agent definition
   - Instructions for result presentation
   - Tool/workflow bindings


### Prerequisites

- watsonx Orchestrate platform access
- IBM watsonx Orchestrate ADK installed (`pip install ibm-watsonx-orchestrate`)
- [WXO Service Instance URL](https://www.ibm.com/docs/en/watsonx/watson-orchestrate/base?topic=api-getting-endpoint)
- [IBM Cloud API Key](https://www.ibm.com/docs/en/watsonx/watson-orchestrate/base?topic=api-generating-key-cloud)

### Add Orchestrate environment

```bash
orchestrate env add -n <env-name> -u <WO_INSTANCE_URL>
```
### Activate environment
```
orchestrate env activate <env-name> -a <WO_API_KEY>
```
### Import Tools

```bash
orchestrate tools import -f appraisal_tools.py -k python -r requirements-tools.txt
```

### Import Workflow

```bash
orchestrate tools import -f employee_appraisal_workflow.py -k python -r requirements-workflow.txt
```

### Import Agent

```bash
orchestrate agents import -f appraisal_agent.yaml
```

### Sample Data

See `sample_data` folder for example input files.

### Agent Flow
<img width="689" height="494" alt="Screenshot 2026-03-11 at 10 31 53 PM" src="https://github.com/user-attachments/assets/62d3a3f5-7b1d-4162-9b6b-9e0217548731" />
<img width="689" height="609" alt="Screenshot 2026-03-11 at 10 33 43 PM" src="https://github.com/user-attachments/assets/59f43363-9b37-4597-b784-97b1430cd36f" />

