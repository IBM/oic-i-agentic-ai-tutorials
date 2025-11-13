#!/usr/bin/env python3
"""
Load documents into pgvector database for RAG
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import PGVector
from langchain_community.embeddings import OpenAIEmbeddings

# Load environment
load_dotenv()

# Try watsonx embeddings, fall back to OpenAI
try:
    from langchain_ibm import WatsonxEmbeddings
    USE_WATSONX = bool(os.getenv("WATSONX_API_KEY"))
except ImportError:
    USE_WATSONX = False


def get_embeddings():
    """Get embeddings model based on available credentials"""
    if USE_WATSONX:
        try:
            print("Attempting to use watsonx.ai embeddings...")
            return WatsonxEmbeddings(
                model_id="ibm/slate-125m-english-rtrvr",
                url="https://us-south.ml.cloud.ibm.com",
                project_id=os.getenv("WATSONX_PROJECT_ID"),
                apikey=os.getenv("WATSONX_API_KEY")
            )
        except Exception as e:
            print(f"⚠️  watsonx.ai credentials invalid: {str(e)}")
            print("Falling back to OpenAI embeddings...")
            if not os.getenv("OPENAI_API_KEY"):
                print("\n❌ Error: No valid API credentials found!")
                print("Please set either:")
                print("  - WATSONX_API_KEY and WATSONX_PROJECT_ID")
                print("  - OPENAI_API_KEY")
                print("\nIn your .env file")
                raise
            return OpenAIEmbeddings(
                model="text-embedding-3-small",
                openai_api_key=os.getenv("OPENAI_API_KEY")
            )
    else:
        if not os.getenv("OPENAI_API_KEY"):
            print("\n❌ Error: OPENAI_API_KEY not set in .env file")
            raise ValueError("Missing OpenAI API key")
        return OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )


def load_documents(data_dir: str = "data"):
    """Load and process documents"""
    documents = []
    data_path = Path(data_dir)
    
    if not data_path.exists():
        print(f"❌ Directory {data_dir} not found")
        return []
    
    # Load PDFs
    for pdf_file in data_path.glob("*.pdf"):
        print(f"📄 Loading {pdf_file.name}...")
        loader = PyPDFLoader(str(pdf_file))
        documents.extend(loader.load())
    
    # Load TXT files
    for txt_file in data_path.glob("*.txt"):
        print(f"📄 Loading {txt_file.name}...")
        loader = TextLoader(str(txt_file))
        documents.extend(loader.load())
    
    print(f"✅ Loaded {len(documents)} document(s)")
    return documents


def chunk_documents(documents):
    """Split documents into chunks"""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        length_function=len,
    )
    chunks = text_splitter.split_documents(documents)
    print(f"✅ Created {len(chunks)} chunks")
    return chunks


def main():
    print("🚀 Loading documents into pgvector...\n")
    
    # Configuration
    PGVECTOR_URL = os.getenv("PGVECTOR_URL")
    COLLECTION_NAME = os.getenv("COLLECTION_NAME", "documents")
    
    if not PGVECTOR_URL:
        print("❌ PGVECTOR_URL not set in .env")
        return
    
    # Load and chunk documents
    documents = load_documents()
    if not documents:
        print("❌ No documents found in data/ directory")
        return
    
    chunks = chunk_documents(documents)
    
    # Get embeddings
    print("\n🔧 Initializing embeddings...")
    embeddings = get_embeddings()
    embed_source = "watsonx.ai" if USE_WATSONX else "OpenAI"
    print(f"✅ Using {embed_source} embeddings")
    
    # Store in pgvector
    print(f"\n💾 Storing in pgvector (collection: {COLLECTION_NAME})...")
    PGVector.from_documents(
        documents=chunks,
        embedding=embeddings,
        collection_name=COLLECTION_NAME,
        connection_string=PGVECTOR_URL,
        pre_delete_collection=True
    )
    
    print("\n✅ Documents loaded successfully!")
    print(f"📊 Total chunks: {len(chunks)}")
    print(f"🔗 Collection: {COLLECTION_NAME}")
    print("\nReady to build your RAG flow in LangFlow!")


if __name__ == "__main__":
    main()
