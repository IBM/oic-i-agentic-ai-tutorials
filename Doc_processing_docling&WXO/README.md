# Docling Document Processing Tool for IBM watsonx Orchestrate

This project provides a document-processing microservice powered by Docling, deployed on IBM Cloud Code Engine, and integrated as a callable external tool inside IBM watsonx Orchestrate.

The solution enables Orchestrate agents to process uploaded documents stored in IBM Cloud Object Storage (COS) and extract structured information such as:
-Tables
-Paragraph text
-Key-value pairs
-Images


### Repository Contents
* 1:main.py: FastAPI application implementing file extraction from COS and Docling processing logic
* 2:Dockerfile:	Container build file for IBM Cloud Code Engine
* 3:openapi.json:	Minimal OpenAPI spec for registering the service as a tool in Orchestrate
* 4:examples.py:	Example usage and next-step extension guidance

### Installation & Development
Prerequisites:
1:Python 3.11+

Access to:
* 1:watsonx Orchestrate
* 2:IBM Cloud Object Storage
* 3:IBM Code Engine

### Run Locally

```bash
-pip install -r requirements.txt
```
```bash
-uvicorn main:app --reload --port 8000
```

### Run Inside Orchestrate
* - Deploy the app on Code Engine.
* - Replace the url in the openapi.json with the new deployed url.
* - Use the openapi to connect the app as a tool in one of the agents on Orchestrate.
