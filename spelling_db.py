import os
import sqlite3
import re
from typing import Dict, List, Tuple
from path_env import DB_DIR

DB_PATH = os.path.join(DB_DIR, "vocab.sqlite")

def tokenize_words(text: str) -> List[str]:
    if not text:
        return []
    # Lowercase and match alphabetic words of length 2 to 20
    return re.findall(r"\b[a-z]{2,20}\b", text.lower())

def init_vocab_db():
    """Initialize the vocabulary database schema in WAL mode."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS document_words (
                    path TEXT,
                    word TEXT,
                    count INTEGER,
                    PRIMARY KEY (path, word)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_words_path ON document_words(path)")
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS vocabulary (
                    word TEXT PRIMARY KEY,
                    frequency INTEGER
                )
            """)
    finally:
        conn.close()

def update_document_vocabulary(path: str, text: str) -> Dict[str, int]:
    """
    Updates word frequencies for a document path.
    Returns a dictionary of {word: new_total_frequency} for all modified terms.
    """
    abs_path = os.path.abspath(path)
    words = tokenize_words(text)
    
    # Count frequencies in the new document content
    new_counts: Dict[str, int] = {}
    for w in words:
        new_counts[w] = new_counts.get(w, 0) + 1
        
    conn = sqlite3.connect(DB_PATH, timeout=10)
    updated_frequencies: Dict[str, int] = {}
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        with conn:
            # 1. Retrieve old counts
            cursor = conn.execute("SELECT word, count FROM document_words WHERE path = ?", (abs_path,))
            old_counts = {row[0]: row[1] for row in cursor.fetchall()}
            
            # 2. Compute deltas
            deltas: Dict[str, int] = {}
            for word, count in new_counts.items():
                deltas[word] = count - old_counts.get(word, 0)
            for word, count in old_counts.items():
                if word not in new_counts:
                    deltas[word] = -count
                    
            # 3. Apply deltas to vocabulary table
            for word, delta in deltas.items():
                if delta == 0:
                    continue
                conn.execute("""
                    INSERT INTO vocabulary (word, frequency)
                    VALUES (?, ?)
                    ON CONFLICT(word) DO UPDATE SET frequency = frequency + excluded.frequency
                """, (word, delta))
                
            # Clean up vocabulary entries that dropped to <= 0
            conn.execute("DELETE FROM vocabulary WHERE frequency <= 0")
            
            # 4. Refresh document_words table
            conn.execute("DELETE FROM document_words WHERE path = ?", (abs_path,))
            if new_counts:
                conn.executemany(
                    "INSERT INTO document_words (path, word, count) VALUES (?, ?, ?)",
                    [(abs_path, word, count) for word, count in new_counts.items()]
                )
                
            # 5. Fetch post-transaction total frequencies for all affected words
            for word in deltas.keys():
                cursor = conn.execute("SELECT frequency FROM vocabulary WHERE word = ?", (word,))
                row = cursor.fetchone()
                updated_frequencies[word] = row[0] if row else 0
    finally:
        conn.close()
        
    return updated_frequencies

def delete_document_vocabulary(path: str) -> Dict[str, int]:
    """
    Removes a document from the vocabulary database.
    Returns a dictionary of {word: new_total_frequency} for all affected terms.
    """
    abs_path = os.path.abspath(path)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    updated_frequencies: Dict[str, int] = {}
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        with conn:
            # 1. Retrieve old counts
            cursor = conn.execute("SELECT word, count FROM document_words WHERE path = ?", (abs_path,))
            old_counts = {row[0]: row[1] for row in cursor.fetchall()}
            
            if not old_counts:
                return {}
                
            # 2. Decrement vocabulary frequencies
            for word, count in old_counts.items():
                conn.execute(
                    "UPDATE vocabulary SET frequency = frequency - ? WHERE word = ?",
                    (count, word)
                )
                
            # Clean up vocabulary entries that dropped to <= 0
            conn.execute("DELETE FROM vocabulary WHERE frequency <= 0")
            
            # 3. Delete from document_words
            conn.execute("DELETE FROM document_words WHERE path = ?", (abs_path,))
            
            # 4. Fetch post-transaction total frequencies for all affected words
            for word in old_counts.keys():
                cursor = conn.execute("SELECT frequency FROM vocabulary WHERE word = ?", (word,))
                row = cursor.fetchone()
                updated_frequencies[word] = row[0] if row else 0
    finally:
        conn.close()
        
    return updated_frequencies

def get_all_vocabulary() -> Dict[str, int]:
    """Returns the entire global vocabulary table as a {word: frequency} mapping."""
    init_vocab_db()
    conn = sqlite3.connect(DB_PATH, timeout=10)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        cursor = conn.execute("SELECT word, frequency FROM vocabulary")
        return {row[0]: row[1] for row in cursor.fetchall()}
    finally:
        conn.close()
