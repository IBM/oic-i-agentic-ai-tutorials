# Sample Custom Knowledge Base FastAPI Service

This project implements a custom search service endpoint compatible with **IBM watsonx Orchestrate** Custom Knowledge Base (`conversational_search_tool`).

## Overview

watsonx Orchestrate supports connecting agents to external knowledge bases. Using context variables, you can inject user/session context (such as `project_id`, `customer_id`, or identity headers) into the retrieval call to apply dynamic RBAC filtering.

This FastAPI service:
- Accepts `KBRequest` payloads from watsonx Orchestrate containing `query`, `filter`, and user identity fields.
- Filters search results based on query terms and context variables (`project_id`, `customer_id`, etc.).
- Returns formatted `KBResponse` results matching watsonx Orchestrate field mappings (`title`, `body`, `url`, and `result_metadata`).

---

## Prerequisites

- Python 3.10+
- `pip` or `uv`

---

## Getting Started

### 1. Install Dependencies

Navigate to this directory and install the required dependencies:

```bash
cd sample-fast-api
pip install -r requirements.txt
```

### 2. Run the Server

Start the application with Uvicorn:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Or run directly with Python:

```bash
python main.py
```

The service will start at `http://localhost:8000`.

---

## API Documentation

Interactive Swagger API docs are accessible at:
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## Endpoints

### 1. Health Check
- **Method:** `GET`
- **Path:** `/`
- **Response:**
  ```json
  {
    "status": "ok",
    "service": "watsonx-orchestrate-custom-kb"
  }
  ```

### 2. Search Knowledge Base
- **Method:** `POST`
- **Path:** `/api/knowledge-base`
- **Request Body (`KBRequest`):**
  ```json
  {
    "query": "How do I onboard?",
    "filter": "project_id=proj-42,customer_id=cust-99",
    "user_email": "user@example.com",
    "user_oid": "0000-1111-2222",
    "source_filter": "sharepoint",
    "metadata": {}
  }
  ```
- **Response Body (`KBResponse`):**
  ```json
  {
    "search_results": [
      {
        "title": "Onboarding Guide - Project Phoenix",
        "body": "Welcome to Project Phoenix. Setup your development environment using Python 3.11 and Docker...",
        "url": "https://wiki.internal.example.com/phoenix/onboarding",
        "result_metadata": {
          "source": "sharepoint",
          "score": 0.95
        }
      }
    ]
  }
  ```

---

## Testing with cURL

Test the endpoint locally using cURL:

```bash
curl -X POST http://localhost:8000/api/v2/knowledge-base \
  -H "Content-Type: application/json" \
  -d '{
    "query": "onboarding",
    "filter": "project_id=proj-42,customer_id=cust-99"
  }'
```
