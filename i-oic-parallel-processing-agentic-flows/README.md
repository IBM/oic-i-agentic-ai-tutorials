# Employee Appraisal Workflow for watsonx Orchestrate

A comprehensive employee appraisal system that processes employee data in parallel, calculates performance scores, determines ratings, and generates salary recommendations with downloadable Excel reports.

## 📋 Overview

This project provides an automated employee appraisal system with:
- **Form-Based File Upload** - User-friendly form interface for uploading employee data
- **Editable Data Review** - Interactive table to review and edit employee data before processing
- **Parallel Processing** - Processes multiple employees simultaneously for fast results
- **Excel Reports** - Generates downloadable Excel files with complete results

## 🏗️ Architecture

### Components

1. **tools/appraisal_tools.py** - Python tools for data processing
   - `read_employee_data` - Reads Excel/CSV from S3 URLs
   - `calculate_employee_appraisal` - Calculates appraisal for one employee
   - `generate_appraisal_excel` - Generates downloadable Excel file

2. **workflows/employee_appraisal_workflow.py** - Workflow orchestration
   - Form-based file upload with validation
   - Editable data table for review and corrections
   - Parallel foreach processing for efficiency
   - Excel generation with comprehensive results

3. **agents/appraisal_agent.yaml** - Agent configuration


## 🔄 Workflow Steps

1. **File Upload Form** - User uploads employee data file (Excel or CSV) through a form interface
2. **Read Employee Data** - System reads and parses the uploaded file
3. **Data Review & Edit** - Interactive table displays all employee data for review and editing
4. **Parallel Processing** - Each employee's appraisal is calculated simultaneously
5. **Excel Generation** - Comprehensive Excel report is generated automatically
6. **Results Delivery** - Agent presents summary and provides download link

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
orchestrate tools import -f tools/appraisal_tools.py -k python -r tools/requirements-tools.txt
```

### Import Workflow

```bash
orchestrate tools import -f workflows/employee_appraisal_workflow.py -k flow -r workflows/requirements-workflow.txt
```

### Import Agent

```bash
orchestrate agents import -f agents/appraisal_agent.yaml
```

## Sample Data

The `sample_data` folder contains example input files:
- **employee_data(20).xlsx/csv** - Small dataset for testing (20 employees)
- **employee_data(500).xlsx/csv** - Large dataset for performance testing (500 employees)

## Agent Flow

<img width="846" height="540" alt="Screenshot 2026-03-13 at 7 15 54 PM" src="https://github.com/user-attachments/assets/0543570e-b7f2-4010-a1a8-4a742bd1d554" />
<img width="846" height="669" alt="Screenshot 2026-03-13 at 7 16 41 PM" src="https://github.com/user-attachments/assets/b1d49056-fe71-46a3-9c8d-c9caa4ea6783" />
<img width="846" height="623" alt="Screenshot 2026-03-13 at 7 17 14 PM" src="https://github.com/user-attachments/assets/5d5d5beb-b40e-4128-8689-135752b56617" />
