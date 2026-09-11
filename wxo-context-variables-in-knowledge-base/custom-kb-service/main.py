import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(
    title="Custom Knowledge Base Service for watsonx Orchestrate",
    description="Custom search backend conforming to watsonx Orchestrate knowledge base integration specifications.",
    version="1.0.0",
)


# ---------------------------------------------------------
# Request / Response Schemas
# ---------------------------------------------------------
class KBRequest(BaseModel):
    query: str = Field(..., description="The user's natural-language question.")
    filter: str | None = Field(
        None,
        description=(
            'Packed identity string: "project_id=...,customer_id=..."'
            "Set by the KB YAML filter field with wxO context variable substitution."
        ),
    )


class KBResultMetadata(BaseModel):
    source: str | None = None
    score: float | None = None


class KBResult(BaseModel):
    result_metadata: KBResultMetadata | None = None
    title: str
    body: str
    url: str = ""


class KBResponse(BaseModel):
    search_results: list[KBResult]


# ---------------------------------------------------------
# Mock Sample Knowledge Base Data
# ---------------------------------------------------------
SAMPLE_DOCUMENTS = [
    {
        "title": "Onboarding Guide - Project Phoenix",
        "body": "Welcome to Project Phoenix. Setup your development environment using Python 3.11 and Docker. Access the repository at git.internal/phoenix.",
        "url": "https://wiki.internal.example.com/phoenix/onboarding",
        "project_id": "proj-42",
        "customer_id": "cust-99",
        "source": "sharepoint",
        "score": 0.95,
    },
    {
        "title": "Customer Support Escalation Policy - Acme Corp",
        "body": "For customer cust-99 (Acme Corp), Tier 3 escalations should be routed directly to the dedicated technical account manager.",
        "url": "https://wiki.internal.example.com/customers/cust-99/escalation",
        "project_id": "proj-42",
        "customer_id": "cust-99",
        "source": "servicenow",
        "score": 0.91,
    },
    {
        "title": "Project Alpha Architecture & Guidelines",
        "body": "Project Alpha utilizes microservices deployed on Kubernetes with PostgreSQL database clusters.",
        "url": "https://wiki.internal.example.com/alpha/guidelines",
        "project_id": "proj-101",
        "customer_id": "cust-200",
        "source": "sharepoint",
        "score": 0.88,
    },
    {
        "title": "General Company IT Security Policy",
        "body": "All employees must use multi-factor authentication (MFA) and rotate access credentials every 90 days.",
        "url": "https://wiki.internal.example.com/policies/security",
        "project_id": None,
        "customer_id": None,
        "source": "sharepoint",
        "score": 0.75,
    },
]


def parse_filter_string(filter_str: str | None) -> dict[str, str]:
    """Parse comma-separated key=value filter strings like 'project_id=proj-42,customer_id=cust-99'."""
    parsed = {}
    if not filter_str:
        return parsed
    parts = filter_str.split(",")
    for part in parts:
        if "=" in part:
            k, v = part.split("=", 1)
            parsed[k.strip()] = v.strip()
    return parsed


# ---------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------
@app.get("/")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "watsonx-orchestrate-custom-kb"}


@app.post("/api/knowledge-base", response_model=KBResponse)
def search_knowledge_base(request: KBRequest) -> KBResponse:
    """
    Search endpoint compatible with watsonx Orchestrate custom knowledge base.
    Filters documents based on query text and context parameters (e.g. project_id, customer_id).
    """
    # 1. Parse filter string fallback if provided
    filter_params = parse_filter_string(request.filter)

    # 2. Extract context filter values from top-level fields or parsed filter string
    project_id = filter_params.get("project_id")
    customer_id = filter_params.get("customer_id")

    # -----------------------------------------------------------------
    # REPLACE THIS BLOCK WITH YOUR REAL DATA SOURCE
    # -----------------------------------------------------------------
    # The mock search below (iterating over SAMPLE_DOCUMENTS) is for
    # demonstration purposes only. In production, replace it with a
    # query against your actual data source, for example:
    #
    #   Elasticsearch / OpenSearch
    #     client = Elasticsearch("https://my-cluster:9200")
    #     resp = client.search(
    #         index="knowledge-base",
    #         query={"match": {"body": request.query}},
    #         post_filter={"term": {"project_id": project_id}},
    #     )
    #     raw_docs = [hit["_source"] for hit in resp["hits"]["hits"]]
    #
    #   Relational database (SQLAlchemy / psycopg2 / etc.)
    #     rows = db.execute(
    #         "SELECT title, body, url, source FROM docs "
    #         "WHERE project_id = %s AND to_tsvector(body) @@ plainto_tsquery(%s)",
    #         (project_id, request.query),
    #     ).fetchall()
    #     raw_docs = [dict(row) for row in rows]
    #
    #   Vector / semantic search (pgvector, Pinecone, Milvus, Weaviate …)
    #     embedding = embed_model.encode(request.query)
    #     raw_docs = vector_store.query(
    #         vector=embedding, filter={"project_id": project_id}, top_k=10
    #     )
    #
    # After fetching raw_docs, map each record to KBResult / KBResultMetadata
    # exactly as shown in the mock block below, then return KBResponse.
    # -----------------------------------------------------------------

    query_lower = request.query.lower()
    results: list[KBResult] = []

    for doc in SAMPLE_DOCUMENTS:
        # Context variable filtering (RBAC scoping)
        if project_id and doc["project_id"] and doc["project_id"] != project_id:
            continue
        if customer_id and doc["customer_id"] and doc["customer_id"] != customer_id:
            continue

        # Basic text matching on query across title or body (or fallback return if matched context)
        is_match = (
            query_lower in doc["title"].lower()
            or query_lower in doc["body"].lower()
            or any(word in doc["body"].lower() for word in query_lower.split() if len(word) > 2)
            or not query_lower
        )

        if is_match:
            results.append(
                KBResult(
                    title=doc["title"],
                    body=doc["body"],
                    url=doc["url"],
                    result_metadata=KBResultMetadata(
                        source=doc["source"],
                        score=doc["score"]
                    )
                )
            )

    return KBResponse(search_results=results)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
