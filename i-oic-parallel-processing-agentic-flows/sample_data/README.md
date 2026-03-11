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

### Import Tools

```bash
# Import Python tools
orchestrate tools import -f appraisal_tools.py -k python -r requirements-tools.txt
```

### Import Workflow

```bash
# Import workflow
orchestrate tools import -f employee_appraisal_workflow.py -k python -r requirements-workflow.txt
```

### Import Agent

```bash
# Import agent
orchestrate agents import -f appraisal_agent.yaml
```

### Sample Data

See `sample_data` folder for example input files.

