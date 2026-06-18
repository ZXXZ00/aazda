import sys
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Any, Dict

import os
import splade_encoder
import local_db
import watch
import parsers
from path_env import HOME_DIRECTORY

# Watcher configuration (can be customized via environment variables)
WATCH_DIR = os.getenv("WATCH_DIR", HOME_DIRECTORY)
WATCH_INTERVAL = int(os.getenv("WATCH_INTERVAL", "10"))  # Default to 10s for responsiveness

app = FastAPI(title="Local Semantic Search API")

@app.on_event("startup")
def startup_event():
    # Start the watcher in-process
    watch.start_watcher(WATCH_DIR, WATCH_INTERVAL)
    # Lazy load spelling vocabulary into SymSpell in a background thread to keep startup instant
    import threading
    from spelling_service import spelling_service
    threading.Thread(target=spelling_service.load_if_needed, daemon=True).start()

@app.on_event("shutdown")
def shutdown_event():
    # Stop the watcher cleanly
    watch.stop_watcher()
    # Close Qdrant client cleanly to flush all writes to disk
    try:
        local_db.client.close()
        print("Qdrant client closed cleanly.")
    except Exception as e:
        print(f"Error closing Qdrant client: {e}", file=sys.stderr)

# Enable CORS so the Electron app can query this API from the frontend
# Note: allowing credentials with wildcard origin is a security risk.
# For local Electron apps, specify exactly the local origin like 'http://localhost:3000' or similar, 
# or disable credentials if not using cookies.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SearchQuery(BaseModel):
    query: str
    limit: Optional[int] = 20

class ClickLog(BaseModel):
    path: str

@app.post("/search")
async def search(request: SearchQuery):
    if not request.query.strip():
        return {"results": [], "corrected_query": request.query}
    
    try:
        # Correct spelling typos in the query using spelling_service
        from spelling_service import spelling_service
        corrected_query = spelling_service.correct_query(request.query)
        
        # Generate SPLADE sparse vector representation of query
        sparse_query = splade_encoder.encode(corrected_query)
        
        # Search Qdrant and apply personalized re-ranking
        results = local_db.search_documents(sparse_query, limit=request.limit)
        return {"results": results, "corrected_query": corrected_query}
    except Exception as e:
        print(f"Error executing search query: {e}", file=sys.stderr)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/click")
async def log_click(request: ClickLog):
    if not request.path.strip():
        raise HTTPException(status_code=400, detail="Path cannot be empty.")
    
    try:
        # Increment open count and update last_opened_at in Qdrant
        local_db.log_click(request.path)
        return {"status": "success"}
    except Exception as e:
        print(f"Error logging click event: {e}", file=sys.stderr)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status")
async def status():
    try:
        info = local_db.client.get_collection(local_db.COLLECTION_NAME)
        return {
            "status": "healthy",
            "collection": local_db.COLLECTION_NAME,
            "points_count": info.points_count,
            "indexed_vectors": info.indexed_vectors_count
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)}

from fastapi.concurrency import run_in_threadpool

@app.get("/content")
async def get_document_content(path: str):
    if not path.strip():
        raise HTTPException(status_code=400, detail="Path cannot be empty.")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found.")
    try:
        # Run synchronous parse_file in a background thread to prevent blocking the async event loop
        doc = await run_in_threadpool(parsers.parse_file, path, preview_mode=True)
        if doc is None:
            return {"content": ""}  # Junk file, no content to preview
        return {"content": doc.text_content or ""}
    except Exception as e:
        print(f"Error reading file content for preview: {e}", file=sys.stderr)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
