import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
import numpy as np
import threading

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    SparseVectorParams,
    SparseIndexParams,
    PointStruct,
    SparseVector,
    NamedSparseVector,
    PayloadSchemaType,
    Filter,
    FieldCondition,
    MatchValue,
    FilterSelector,
)
from parsers import ParsedDocument
import splade_encoder
from path_env import DB_DIR

os.makedirs(DB_DIR, exist_ok=True)

COLLECTION_NAME = "documents"

# Initialize Qdrant local client with thread safety check disabled for concurrent in-process access
client = QdrantClient(path=DB_DIR, force_disable_check_same_thread=True)

# Per-path lock striping: prevents concurrent mutations on the same file path
# Uses RLock for re-entrancy (upsert_document calls delete_path internally)
_NUM_PATH_LOCKS = 64
_path_locks = [threading.RLock() for _ in range(_NUM_PATH_LOCKS)]

def _get_path_lock(path: str) -> threading.RLock:
    """Return a striped lock for the given path to bound memory usage."""
    return _path_locks[hash(os.path.abspath(path)) % _NUM_PATH_LOCKS]

def backfill_vocabulary_if_needed():
    import spelling_db
    vocab = spelling_db.get_all_vocabulary()
    if len(vocab) > 0:
        return
        
    print("Spelling database vocabulary is empty. Checking Qdrant for existing documents to backfill...")
    try:
        offset = None
        doc_texts = {}
        while True:
            records, offset = client.scroll(
                collection_name=COLLECTION_NAME,
                limit=1000,
                with_payload=["path", "chunk_text"],
                with_vectors=False,
                offset=offset
            )
            for record in records:
                p = record.payload.get("path")
                text = record.payload.get("chunk_text", "")
                if p:
                    if p not in doc_texts:
                        doc_texts[p] = []
                    doc_texts[p].append(text)
            if offset is None:
                break
                
        if not doc_texts:
            print("No existing documents found in Qdrant. No backfill needed.")
            return
            
        print(f"Found {len(doc_texts)} existing documents in Qdrant. Backfilling spelling database...")
        for path, chunks in doc_texts.items():
            full_text = " ".join(chunks)
            spelling_db.update_document_vocabulary(path, full_text)
            
        print("Spelling database backfill completed successfully!")
    except Exception as e:
        print(f"Error backfilling spelling database from Qdrant: {e}")

def init_db():
    # Initialize spelling vocabulary database
    try:
        import spelling_db
        spelling_db.init_vocab_db()
    except Exception as e:
        print(f"Error initializing spelling database: {e}")

    # Check if collection exists, if not create it
    collections = client.get_collections().collections
    exists = any(c.name == COLLECTION_NAME for c in collections)
    
    if not exists:
        print(f"Creating Qdrant collection '{COLLECTION_NAME}'...")
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config={},  # No dense vectors initially
            sparse_vectors_config={
                "text-sparse": SparseVectorParams(
                    index=SparseIndexParams(
                        on_disk=True
                    )
                )
            }
        )
        
        # Create indexes for metadata payload
        print("Creating payload indexes...")
        client.create_payload_index(COLLECTION_NAME, "path", PayloadSchemaType.KEYWORD)
        client.create_payload_index(COLLECTION_NAME, "size", PayloadSchemaType.INTEGER)
        client.create_payload_index(COLLECTION_NAME, "file_type", PayloadSchemaType.KEYWORD)
        client.create_payload_index(COLLECTION_NAME, "created_at", PayloadSchemaType.KEYWORD)
        client.create_payload_index(COLLECTION_NAME, "updated_at", PayloadSchemaType.KEYWORD)
        client.create_payload_index(COLLECTION_NAME, "open_count", PayloadSchemaType.INTEGER)
        client.create_payload_index(COLLECTION_NAME, "last_opened_at", PayloadSchemaType.KEYWORD)

    # Backfill spelling database if needed
    try:
        backfill_vocabulary_if_needed()
    except Exception as e:
        print(f"Error checking/backfilling spelling database: {e}")

def get_point_id(filepath: str, chunk_index: int = 0) -> str:
    # Generate a deterministic UUID based on absolute path and chunk index
    abs_path = os.path.abspath(filepath)
    unique_key = f"{abs_path}#chunk_{chunk_index}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, unique_key))

def upsert_document(doc: ParsedDocument):
    lock = _get_path_lock(doc.path)
    with lock:
        # 1. Preserve existing personalization metrics if the document is being updated
        open_count = 0
        last_opened_at = None
        try:
            # Check base chunk (chunk 0) to retrieve existing metrics
            base_id = get_point_id(doc.path, 0)
            existing = client.retrieve(COLLECTION_NAME, [base_id])
            if existing and existing[0].payload:
                open_count = existing[0].payload.get("open_count", 0)
                last_opened_at = existing[0].payload.get("last_opened_at")
        except Exception:
            pass

        # 2. Delete all existing chunks/points associated with this file path
        delete_path(doc.path)

        # 3. Chunk text content
        text = doc.text_content or ""
        chunks = splade_encoder.chunk_text(text)
        if not chunks:
            chunks = [""]

        # 4. Build all points and upsert in a single batch for near-atomicity
        #    (minimizes the window between delete and re-insert)
        points = []
        for idx, chunk_text in enumerate(chunks):
            sparse_vector = splade_encoder.encode(chunk_text)
            point_id = get_point_id(doc.path, idx)

            # Build payload with metadata + chunk indexing properties
            payload = {
                "path": doc.path,
                "name": doc.name,
                "file_type": doc.file_type,
                "size": doc.size,
                "created_at": doc.created_at,
                "updated_at": doc.updated_at,
                "open_count": open_count,
                "last_opened_at": last_opened_at,
                "chunk_index": idx,
                "chunk_text": chunk_text,
                "total_chunks": len(chunks)
            }
            # Add other custom metadata fields
            if doc.metadata:
                for k, v in doc.metadata.items():
                    payload[f"meta_{k}"] = v

            points.append(PointStruct(
                id=point_id,
                vector={
                    "text-sparse": SparseVector(
                        indices=list(sparse_vector.keys()),
                        values=list(sparse_vector.values())
                    )
                },
                payload=payload
            ))

        client.upsert(COLLECTION_NAME, points)

        # Update spelling vocabulary database and sync in-memory service
        try:
            import spelling_db
            from spelling_service import spelling_service
            updated_vocab = spelling_db.update_document_vocabulary(doc.path, doc.text_content or "")
            spelling_service.update_vocab(updated_vocab)
        except Exception as e:
            print(f"Error updating vocabulary for spelling correction: {e}")

def delete_path(path: str) -> int:
    abs_path = os.path.abspath(path)
    lock = _get_path_lock(abs_path)
    with lock:
        deleted_count = 0

        # 1. First, delete vocabulary for this exact file path
        try:
            import spelling_db
            from spelling_service import spelling_service
            deleted_vocab = spelling_db.delete_document_vocabulary(abs_path)
            spelling_service.update_vocab(deleted_vocab)
        except Exception as e:
            print(f"Error deleting vocabulary for {abs_path}: {e}")

        # Fast path: filter-based deletion for exact path match (multi-chunk files)
        # Uses the KEYWORD index on 'path' for O(1) lookup instead of full O(n) scan
        try:
            client.delete(
                collection_name=COLLECTION_NAME,
                points_selector=FilterSelector(
                    filter=Filter(
                        must=[FieldCondition(key="path", match=MatchValue(value=abs_path))]
                    )
                )
            )
        except Exception as e:
            print(f"Error in filter-based deletion for {abs_path}: {e}")

        # Directory children: scroll to find and batch-delete all points under this prefix
        # Still O(n) but only needed for directory deletions (rare path)
        prefix = abs_path if abs_path.endswith("/") else abs_path + "/"
        try:
            offset = None
            to_delete = []
            distinct_child_paths = set()
            while True:
                records, offset = client.scroll(
                    collection_name=COLLECTION_NAME,
                    limit=5000,
                    with_payload=["path"],
                    with_vectors=False,
                    offset=offset
                )
                for r in records:
                    p = r.payload.get("path", "")
                    if p.startswith(prefix):
                        to_delete.append(r.id)
                        distinct_child_paths.add(p)
                if offset is None:
                    break

            if to_delete:
                for i in range(0, len(to_delete), 5000):
                    batch = to_delete[i:i+5000]
                    client.delete(COLLECTION_NAME, batch)
                deleted_count = len(to_delete)

                # Delete vocabulary for all child paths
                import spelling_db
                from spelling_service import spelling_service
                for child_path in distinct_child_paths:
                    try:
                        deleted_vocab = spelling_db.delete_document_vocabulary(child_path)
                        spelling_service.update_vocab(deleted_vocab)
                    except Exception as e:
                        print(f"Error deleting vocabulary for child {child_path}: {e}")
        except Exception as e:
            print(f"Error deleting children of {abs_path}: {e}")

        return deleted_count

def log_click(path: str):
    abs_path = os.path.abspath(path)
    lock = _get_path_lock(abs_path)
    with lock:
        # Retrieve all chunks for this file using filtered scroll (uses KEYWORD index)
        to_update = []
        open_count = 0
        try:
            offset = None
            while True:
                records, offset = client.scroll(
                    collection_name=COLLECTION_NAME,
                    scroll_filter=Filter(
                        must=[FieldCondition(key="path", match=MatchValue(value=abs_path))]
                    ),
                    limit=5000,
                    with_payload=["open_count"],
                    with_vectors=False,
                    offset=offset
                )
                for r in records:
                    to_update.append(r.id)
                    open_count = max(open_count, r.payload.get("open_count", 0))
                if offset is None:
                    break
        except Exception:
            pass

        if to_update:
            client.set_payload(
                collection_name=COLLECTION_NAME,
                payload={
                    "open_count": open_count + 1,
                    "last_opened_at": datetime.now().isoformat()
                },
                points=to_update
            )

def search_documents(sparse_query: Dict[int, float], limit: int = 50) -> List[Dict[str, Any]]:
    if not sparse_query:
        return []
        
    # Query Qdrant for candidates
    res = client.query_points(
        collection_name=COLLECTION_NAME,
        query=SparseVector(
            indices=list(sparse_query.keys()),
            values=list(sparse_query.values())
        ),
        using="text-sparse",
        limit=limit * 4  # Retrieve more candidates because multiple chunks might match the same file
    )
    hits = res.points
    
    # Perform Personalized Re-ranking and Grouping by File Path
    now = datetime.now()
    ranked_results = {}
    
    for hit in hits:
        payload = hit.payload
        score = hit.score
        path = payload.get("path")
        
        if not path:
            continue
            
        # 1. Access Frequency Boost: multiplier based on open_count
        open_count = payload.get("open_count", 0)
        frequency_boost = 1.0 + 0.3 * np.log1p(open_count)
        
        # 2. Access Recency Boost: decay based on last_opened_at
        recency_boost = 1.0
        last_opened = payload.get("last_opened_at")
        if last_opened:
            try:
                dt = datetime.fromisoformat(last_opened)
                delta_days = (now - dt).total_seconds() / (3600 * 24)
                # Exponential decay over time (halves every 7 days)
                recency_boost += 0.5 * (0.5 ** (delta_days / 7.0))
            except Exception:
                pass
                
        # 3. Modification Recency Boost: decay based on updated_at
        mod_boost = 1.0
        updated = payload.get("updated_at")
        if updated:
            try:
                dt = datetime.fromisoformat(updated)
                delta_days = (now - dt).total_seconds() / (3600 * 24)
                # Exponential decay over time (halves every 14 days)
                mod_boost += 0.3 * (0.5 ** (delta_days / 14.0))
            except Exception:
                pass

        # Calculate final personalized score
        final_score = score * frequency_boost * recency_boost * mod_boost
        
        # Group and deduplicate by path, keeping the passage chunk with the highest score
        if path not in ranked_results or final_score > ranked_results[path]["score"]:
            ranked_results[path] = {
                "id": hit.id,
                "score": final_score,
                "path": path,
                "name": payload.get("name"),
                "file_type": payload.get("file_type"),
                "size": payload.get("size"),
                "created_at": payload.get("created_at"),
                "updated_at": payload.get("updated_at"),
                "open_count": open_count,
                "last_opened_at": last_opened,
                "chunk_index": payload.get("chunk_index"),
                "chunk_text": payload.get("chunk_text"),
                "metadata": {k: v for k, v in payload.items() if k.startswith("meta_")}
            }
            
    # Sort results by final score descending and slice to limit
    sorted_results = list(ranked_results.values())
    sorted_results.sort(key=lambda x: -x["score"])
    return sorted_results[:limit]

# Initialize Database on load
init_db()

if __name__ == "__main__":
    print("Testing local_db...")
    # Add dummy document
    dummy_doc = ParsedDocument(
        path="/Users/adam/Documents/test_local_db.txt",
        name="test_local_db.txt",
        file_type="text/plain",
        size=1024,
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
        text_content="This is dummy text representing a local database search verification."
    )
    upsert_document(dummy_doc)
    print("Dummy document upserted.")
    
    # Check if exists
    point_id = get_point_id(dummy_doc.path, 0)
    res = client.retrieve(COLLECTION_NAME, [point_id])
    print("Retrieved document chunk 0:", res[0].payload)
    
    # Test click logging
    print("Logging click...")
    log_click(dummy_doc.path)
    res = client.retrieve(COLLECTION_NAME, [point_id])
    print("After click:", res[0].payload)
    
    # Test search
    print("Searching...")
    sparse_query = splade_encoder.encode("local database search")
    results = search_documents(sparse_query)
    print("Search results:", results)
    
    # Delete
    print("Deleting...")
    delete_path(dummy_doc.path)
    res = client.retrieve(COLLECTION_NAME, [point_id])
    print("After delete (should be empty):", res)
