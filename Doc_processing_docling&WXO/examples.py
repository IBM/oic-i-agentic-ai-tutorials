from fastapi import FastAPI, UploadFile, File
from io import BytesIO
import base64
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import DocumentStream, InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from fastapi.concurrency import run_in_threadpool

app = FastAPI()

# Configure pipeline options for PDF (OCR + images + tables + full-page raster fallback)
pdf_options = PdfPipelineOptions(
    do_ocr=True,
    do_table_structure=True,
    # enable image generation for embedded pictures and page rasterization
    generate_picture_images=True,
    generate_page_images=True,
    # optional: you can scale up page images for better resolution
    images_scale=2.0
)

converter = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options)
    }
)


def extract_paragraphs(doc):
    paragraphs = []
    for i, block in enumerate(getattr(doc, "texts", []), start=1):
        text = getattr(block, "text", "").strip()
        if text:
            paragraphs.append({"index": i, "text": text})
    return paragraphs


def extract_tables(doc):
    tables = []
    for i, table in enumerate(getattr(doc, "tables", []), start=1):
        try:
            df = table.export_to_dataframe()
            rows = df.to_dict(orient="records")
        except Exception:
            rows = []
        tables.append({"table_index": i, "rows": rows})
    return tables


def extract_key_values(doc):
    extracted = []
    # Use structured items if present
    for item in getattr(doc, "key_value_items", []):
        try:
            tokens = item.export_to_document_tokens(
                doc, add_location=False, add_content=True
            )
        except Exception:
            tokens = []
        extracted.append({"type": "key_value", "tokens": tokens})

    for item in getattr(doc, "form_items", []):
        try:
            tokens = item.export_to_document_tokens(
                doc, add_location=False, add_content=True
            )
        except Exception:
            tokens = []
        extracted.append({"type": "form_field", "tokens": tokens})

    return extracted


def extract_images(doc):
    images = []
    for i, pic in enumerate(getattr(doc, "pictures", []), start=1):
        # First try embedded picture extraction
        try:
            pil_img = pic.get_image(doc)
        except Exception:
            pil_img = None

        # If no embedded image, fallback to rasterizing the page
        if pil_img is None:
            try:
                page_no = pic.prov[0].page_no if pic.prov else 1
                page = doc.get_page(page_no)
                pil_img = page.render_to_image(dpi=200)
            except Exception:
                pil_img = None

        if pil_img:
            buf = BytesIO()
            pil_img.save(buf, format="PNG")
            encoded = base64.b64encode(buf.getvalue()).decode("utf-8")
        else:
            encoded = None

        images.append({
            "index": i,
            "page": pic.prov[0].page_no if pic.prov else None,
            "base64": encoded,
            "status": "ok" if encoded else "failed"
        })
    return images


@app.post("/process")
async def process_document(file: UploadFile = File(...)):
    file_bytes = await file.read()
    stream = DocumentStream(name=file.filename, stream=BytesIO(file_bytes))

    # Run conversion in threadpool to avoid blocking the event loop
    result = await run_in_threadpool(converter.convert, stream)
    doc = result.document

    return {
        "filename": file.filename,
        "meta": {
            "pages": len(getattr(doc, "pages", [])),
            "tables": len(doc.tables),
            "images": len(getattr(doc, "pictures", [])),
            "key_value_items": len(doc.key_value_items),
            "form_items": len(doc.form_items),
        },
        "paragraphs": extract_paragraphs(doc),
        "tables": extract_tables(doc),
        "key_values": extract_key_values(doc),
        "images": extract_images(doc),
    }
