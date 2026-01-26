from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission
from ibm_watsonx_orchestrate.agent_builder.connections import ConnectionType
from ibm_watsonx_orchestrate.run import connections as orch_connections
from io import BytesIO
import ibm_boto3
from ibm_botocore.client import Config
import requests
import uuid




@tool(
    name="upload_and_extract_tables",
    description="Upload a document, store it in COS, and extract tables using Docling Serve",
    permission=ToolPermission.ADMIN,
        expected_credentials=[{
        "app_id": "docling",
        "type": ConnectionType.KEY_VALUE
    }]
)


def upload_and_extract_tables(file_bytes: bytes, file_name: str = "uploaded.pdf") -> dict:
    """
    Uploads a file to IBM COS, reads it back as a stream, and extracts tables via docling-serve.
    """

    conn = orch_connections.key_value("docling")
    # ---- ENV ----
    COS_ENDPOINT = conn["COS_ENDPOINT"]
    COS_API_KEY_ID = conn["COS_API_KEY_ID"]
    COS_INSTANCE_CRN = conn["COS_INSTANCE_CRN"]
    BUCKET_NAME = conn["BUCKET_NAME"]
    DOCLING_SERVE_URL = conn["DOCLING_SERVE_URL"]

    # ---- COS CLIENT (created once, reused) ----
    cos = ibm_boto3.client(
        "s3",
        ibm_api_key_id=COS_API_KEY_ID,
        ibm_service_instance_id=COS_INSTANCE_CRN,
        config=Config(signature_version="oauth"),
        endpoint_url=COS_ENDPOINT
    )

    # -------------------------------------------------------
    # 1. Upload to COS (unique key)
    # -------------------------------------------------------
    object_key = f"uploads/{uuid.uuid4()}-{file_name}"

    cos.put_object(
        Bucket=BUCKET_NAME,
        Key=object_key,
        Body=file_bytes,
        ContentType="application/pdf"
    )

    # -------------------------------------------------------
    # 2. Read back from COS as stream
    # -------------------------------------------------------
    response = cos.get_object(Bucket=BUCKET_NAME, Key=object_key)
    file_stream = BytesIO(response["Body"].read())
    file_stream.seek(0)

    # -------------------------------------------------------
    # 3. Send stream to docling-serve
    # -------------------------------------------------------
    files = {
        "files": (file_name, file_stream, "application/pdf")
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
        "cos_object": object_key,
        "num_tables": len(tables),
        "tables": tables
    }
