#!/usr/bin/env python3
"""
Script to export/import data from/to an Astra DB collection to/from JSON files, including embeddings.
"""

import os
import json
import argparse
from typing import List, Dict, Any
from astrapy import DataAPIClient
from dotenv import load_dotenv
import numpy as np


class ArrayEncoder(json.JSONEncoder):
    """Custom JSON encoder that properly handles arrays and numpy arrays."""
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, (np.integer, np.floating)):
            return obj.item()
        elif isinstance(obj, (list, tuple)):
            # Ensure all elements in lists/tuples are properly serialized
            return [self.default(item) if isinstance(item, (np.ndarray, np.integer, np.floating)) else item for item in obj]
        return super().default(obj)



def export_collection(
    astra_db_token: str,
    astra_db_api_endpoint: str,
    collection_name: str,
    output_file: str,
    include_embeddings: bool = True,
    embedding_field: str = "$vector"
) -> None:
    """
    Export all documents from an Astra DB collection to a JSON file.
    
    Args:
        astra_db_token: Astra DB application token
        astra_db_api_endpoint: Astra DB API endpoint URL
        database_name: Name of the database
        collection_name: Name of the collection to export
        output_file: Path to the output JSON file
        include_embeddings: Whether to include embedding vectors in the export
        embedding_field: Name of the field containing embeddings (default: "$vector")
    """
    # Initialize the client
    client = DataAPIClient()
    db = client.get_database(
        astra_db_api_endpoint,
        token=astra_db_token)
    collection = db.get_collection(collection_name)
    
    print(f"Connected to collection: {collection_name}")
    print(f"Fetching all documents...")
    
    # Fetch all documents
    # Using find() with empty filter to get all documents
    documents = []
    #cursor = collection.find({}, include_similarity=False,projection={"content": 1, "metadata": 1, "_id": 1, "$vector": 1}, limit=2)
    cursor = collection.find({}, include_similarity=False,projection={"content": 1, "metadata": 1, "_id": 1, "$vector": 1})
    
    count = 0
    for doc in cursor:
        # Convert the document to a dictionary
        doc_dict = doc if isinstance(doc, dict) else dict(doc)
        
        # Ensure vector is properly converted to a list
        if "$vector" in doc_dict:
            vec = doc_dict["$vector"]
            # Convert numpy arrays or other array-like objects to list
            if isinstance(vec, np.ndarray):
                doc_dict["$vector"] = vec.tolist()
            elif not isinstance(vec, list):
                # Convert any iterable to list to ensure proper serialization
                doc_dict["$vector"] = list(vec) if hasattr(vec, '__iter__') else vec
        
        documents.append(doc_dict)
        count += 1
        
        if count % 100 == 0:
            print(f"  Processed {count} documents...")
    
    print(f"Total documents fetched: {count}")
    
    # Prepare export data
    export_data = documents
    
    # Write to JSON file
    print(f"Writing to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False, cls=ArrayEncoder)
    
    print(f"Export completed! {count} documents saved to {output_file}")
    
    # Print summary
    if include_embeddings:
        docs_with_embeddings = sum(1 for doc in documents if embedding_field in doc)
        print(f"  - Documents with embeddings: {docs_with_embeddings}")
        print(f"  - Documents without embeddings: {count - docs_with_embeddings}")


def import_collection(
    astra_db_token: str,
    astra_db_api_endpoint: str,
    collection_name: str,
    input_file: str,
    batch_size: int = 100
) -> None:
    """
    Import documents from a JSON file into an Astra DB collection.
    
    Args:
        astra_db_token: Astra DB application token
        astra_db_api_endpoint: Astra DB API endpoint URL
        collection_name: Name of the collection to import into
        input_file: Path to the input JSON file
        batch_size: Number of documents to insert per batch (default: 100)
    """
    # Initialize the client
    client = DataAPIClient()
    db = client.get_database(
        astra_db_api_endpoint,
        token=astra_db_token)
    collection = db.get_collection(collection_name)
    
    print(f"Connected to collection: {collection_name}")
    print(f"Reading from {input_file}...")
    
    # Read JSON file
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Handle different JSON structures
    if isinstance(data, dict):
        # If it's a dict with a "documents" key, extract that
        if "documents" in data:
            documents = data["documents"]
        else:
            # Otherwise, treat the whole dict as a single document
            documents = [data]
    elif isinstance(data, list):
        documents = data
    else:
        raise ValueError(f"Unexpected JSON structure: expected list or dict, got {type(data)}")
    
    total_docs = len(documents)
    print(f"Found {total_docs} documents to import")
    
    # Insert documents in batches
    inserted_count = 0
    for i in range(0, total_docs, batch_size):
        batch = documents[i:i + batch_size]
        
        # Prepare documents for insertion
        prepared_batch = []
        for doc in batch:
            # Ensure _id is handled correctly (Astra DB will generate if not present)
            doc_copy = dict(doc)
            # Convert vector lists to proper format if needed
            if "$vector" in doc_copy and isinstance(doc_copy["$vector"], list):
                # Ensure vector is a list of numbers
                doc_copy["$vector"] = [float(x) for x in doc_copy["$vector"]]
            prepared_batch.append(doc_copy)
        
        # Insert batch
        try:
            result = collection.insert_many(prepared_batch)
            inserted_count += len(prepared_batch)
            print(f"  Inserted batch: {inserted_count}/{total_docs} documents...")
        except Exception as e:
            print(f"  Error inserting batch starting at index {i}: {e}")
            # Try inserting one by one to identify problematic documents
            for j, doc in enumerate(prepared_batch):
                try:
                    collection.insert_one(doc)
                    inserted_count += 1
                except Exception as doc_error:
                    print(f"    Failed to insert document at index {i+j}: {doc_error}")
                    print(f"    Document keys: {list(doc.keys())}")
    
    print(f"Import completed! {inserted_count}/{total_docs} documents imported into {collection_name}")
    
    # Print summary
    docs_with_embeddings = sum(1 for doc in documents if "$vector" in doc)
    print(f"  - Documents with embeddings: {docs_with_embeddings}")
    print(f"  - Documents without embeddings: {total_docs - docs_with_embeddings}")


def main():
    load_dotenv(override=True)
    parser = argparse.ArgumentParser(
        description="Export/Import data from/to an Astra DB collection to/from JSON, including embeddings"
    )
    
    # Add subparsers for export and import commands
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export collection to JSON')
    export_parser.add_argument(
        "--token",
        type=str,
        help="Astra DB application token (or set ASTRA_DB_TOKEN env var)",
        default=os.getenv("ASTRA_DB_APPLICATION_TOKEN")
    )
    export_parser.add_argument(
        "--endpoint",
        type=str,
        help="Astra DB API endpoint (or set ASTRA_DB_API_ENDPOINT env var)",
        default=os.getenv("ASTRA_DB_API_ENDPOINT")
    )
    export_parser.add_argument(
        "--collection",
        type=str,
        required=True,
        help="Collection name (or set ASTRA_DB_COLLECTION env var)",
        default=os.getenv("ASTRA_DB_COLLECTION")
    )
    export_parser.add_argument(
        "--output",
        type=str,
        default="export.json",
        help="Output JSON file path (default: export.json)"
    )
    export_parser.add_argument(
        "--no-embeddings",
        action="store_true",
        help="Exclude embeddings from the export"
    )
    export_parser.add_argument(
        "--embedding-field",
        type=str,
        default="$vector",
        help="Name of the embedding field (default: $vector)"
    )
    
    # Import command
    import_parser = subparsers.add_parser('import', help='Import collection from JSON')
    import_parser.add_argument(
        "--token",
        type=str,
        help="Astra DB application token (or set ASTRA_DB_TOKEN env var)",
        default=os.getenv("ASTRA_DB_APPICATION_TOKEN")
    )
    import_parser.add_argument(
        "--endpoint",
        type=str,
        help="Astra DB API endpoint (or set ASTRA_DB_API_ENDPOINT env var)",
        default=os.getenv("ASTRA_DB_API_ENDPOINT")
    )
    import_parser.add_argument(
        "--collection",
        type=str,
        required=True,
        help="Collection name (or set ASTRA_DB_COLLECTION env var)",
        default=os.getenv("ASTRA_DB_COLLECTION")
    )
    import_parser.add_argument(
        "--file",
        type=str,
        required=True,
        help="Input JSON file path"
    )
    import_parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of documents to insert per batch (default: 100)"
    )
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Validate common arguments
    if not args.token:
        parser.error("Astra DB token is required (--token or ASTRA_DB_TOKEN env var)")
    if not args.endpoint:
        parser.error("Astra DB endpoint is required (--endpoint or ASTRA_DB_API_ENDPOINT env var)")
    
    try:
        if args.command == 'export':
            if not args.collection:
                parser.error("Collection name is required (--collection or ASTRA_DB_COLLECTION env var)")
            export_collection(
                astra_db_token=args.token,
                astra_db_api_endpoint=args.endpoint,
                collection_name=args.collection,
                output_file=args.output,
                include_embeddings=not args.no_embeddings,
                embedding_field=args.embedding_field
            )
        elif args.command == 'import':
            if not args.collection:
                parser.error("Collection name is required (--collection or ASTRA_DB_COLLECTION env var)")
            if not args.file:
                parser.error("Input file is required (--file)")
            import_collection(
                astra_db_token=args.token,
                astra_db_api_endpoint=args.endpoint,
                collection_name=args.collection,
                input_file=args.file,
                batch_size=args.batch_size
            )
    except Exception as e:
        print(f"Error: {e}")
        raise


if __name__ == "__main__":
    main()

