from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission
from ibm_watsonx_orchestrate.agent_builder.connections import ConnectionType
from ibm_watsonx_orchestrate.run import connections as orch_connections
from io import BytesIO
import requests



@tool(
    name="extract_tables",
    description="extract tables using Docling Serve",
    permission=ToolPermission.ADMIN,
        expected_credentials=[{
        "app_id": "docling",
        "type": ConnectionType.KEY_VALUE
    }]
)


def upload_and_extract_tables(file_bytes: bytes) -> dict:
    """
    extracts tables via docling-serve.
    """

    conn = orch_connections.key_value("docling")
    # ---- ENV ----
    DOCLING_SERVE_URL = conn["DOCLING_SERVE_URL"]
    
    file_stream = BytesIO(file_bytes)

    # -------------------------------------------------------
    # 3. Send stream to docling-serve
    # -------------------------------------------------------
    files = {
        "files": ("uploaded.pdf", file_stream, "application/pdf")
    }

    data = {
        "to_formats": ["json"],
        "do_table_structure": True,
        "table_mode": "accurate",
        "pipeline": "standard"
    }

    dl_response = requests.post(
        f"{DOCLING_SERVE_URL}/v1/convert/file",
        files=files,
        data=data,
        timeout=180
    )

    dl_response.raise_for_status()
    payload = dl_response.json()

    json_content = payload["document"]["json_content"]

    # -------------------------------------------------------
    # 4. Extract tables
    # -------------------------------------------------------
    tables = []
    for i, table in enumerate(json_content.get("tables", []), start=1):
        tables.append({
            "table_index": i,
            "rows": table["data"]
        })

    return {
        "num_tables": len(tables),
        "tables": tables
    }
