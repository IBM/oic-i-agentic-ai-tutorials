from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import ibm_boto3
from ibm_botocore.client import Config, ClientError
from docling.document_converter import DocumentConverter
from docling.datamodel.base_models import DocumentStream
import pandas as pd
import io, os
from pydantic import BaseModel
import uvicorn

from dotenv import load_dotenv

load_dotenv()

# ---- IBM COS Credentials ----
COS_ENDPOINT = os.getenv("COS_ENDPOINT")
COS_API_KEY_ID = os.getenv("COS_API_KEY_ID")
COS_INSTANCE_CRN = os.getenv("COS_INSTANCE_CRN")
BUCKET_NAME = os.getenv("BUCKET_NAME")


# -------------------------------------------------------
# INIT CLIENTS
# -------------------------------------------------------
app = FastAPI(title="Docling Table Extractor API", version="1.0")

cos = ibm_boto3.client(
    "s3",
    ibm_api_key_id=COS_API_KEY_ID,
    ibm_service_instance_id=COS_INSTANCE_CRN,
    config=Config(signature_version="oauth"),
    endpoint_url=COS_ENDPOINT
)

converter = DocumentConverter()


# -------------------------------------------------------
# HELPER FUNCTIONS
# -------------------------------------------------------

class ObjectBody(BaseModel):
    object_name: str


def get_file_stream(object_name: str):
    """Fetch file as stream from IBM COS."""
    try:
        response = cos.get_object(Bucket=BUCKET_NAME, Key=object_name)
        file_stream = io.BytesIO(response['Body'].read())
        print(f"File '{object_name}' fetched from COS.")
        return file_stream
    except ClientError as e:
        raise HTTPException(status_code=500, detail=f"Error reading file: {e}")


def extract_tables_from_docling(file_stream, file_name: str):
    """Run Docling to extract tables from the document."""
    doc_stream = DocumentStream(name=file_name, stream=file_stream)
    result = converter.convert(doc_stream)

    tables = []
    for i, table in enumerate(result.document.tables, start=1):
        df = table.export_to_dataframe()
        tables.append({
            "table_index": i,
            "rows": df.to_dict(orient="records")
        })

    return tables


# -------------------------------------------------------
# MAIN ENDPOINT
# -------------------------------------------------------

@app.post("/v1/chat", summary="extract tables")
async def upload_and_process(body: ObjectBody):
    try:
        file_name = body.object_name

        file_stream = get_file_stream(file_name)

        tables = extract_tables_from_docling(file_stream, file_name)

        if not tables:
            return JSONResponse(content={"message": "No tables found in document."})

        return JSONResponse(content={
            "file_name": file_name,
            "num_tables": len(tables),
            "tables": tables
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------------------------------------
# RUN LOCALLY (optional)
# -------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
