import os
import sys
import numpy as np
from tokenizers import Tokenizer
import onnxruntime as ort
from huggingface_hub import hf_hub_download

# Local paths to cache models
MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "splade")
os.makedirs(MODEL_DIR, exist_ok=True)

print("Initializing SPLADE ONNX models (downloading if not present)...")
try:
    onnx_path = hf_hub_download(repo_id="castorini/splade-v3-onnx", filename="splade-v3-8bit.onnx", local_dir=MODEL_DIR)
    tokenizer_path = hf_hub_download(repo_id="distilbert-base-uncased", filename="tokenizer.json", local_dir=MODEL_DIR)
except Exception as e:
    print(f"Error downloading SPLADE model: {e}", file=sys.stderr)
    raise e

# Initialize Tokenizer and ONNX Runtime session
tokenizer = Tokenizer.from_file(tokenizer_path)
tokenizer.enable_truncation(max_length=512)

# Set CPUExecutionProvider for local inference
session = ort.InferenceSession(onnx_path, providers=['CPUExecutionProvider'])
input_names = [i.name for i in session.get_inputs()]
output_names = [o.name for o in session.get_outputs()]

def encode(text: str, threshold: float = 0.05, top_k: int = 150) -> dict[int, float]:
    if not text.strip():
        return {}

    # Tokenize input
    encoding = tokenizer.encode(text)
    input_ids = np.array([encoding.ids], dtype=np.int64)
    attention_mask = np.array([encoding.attention_mask], dtype=np.int64)
    
    # Dynamically build feed dict based on ONNX inputs
    feed_dict = {}
    if "input_ids" in input_names:
        feed_dict["input_ids"] = input_ids
    if "attention_mask" in input_names:
        feed_dict["attention_mask"] = attention_mask
    if "token_type_ids" in input_names:
        feed_dict["token_type_ids"] = np.array([encoding.type_ids], dtype=np.int64)

    # Run inference
    outputs = session.run(None, feed_dict)
    indices = outputs[0]  # shape: (sparse_len,)
    weights = outputs[1]  # shape: (sparse_len,)
    
    # Filter by weight threshold
    mask = weights > threshold
    filtered_indices = indices[mask]
    filtered_weights = weights[mask]
    
    # Sort indices by descending weight and select top_k
    sort_mask = np.argsort(-filtered_weights)[:top_k]
    final_indices = filtered_indices[sort_mask]
    final_weights = filtered_weights[sort_mask]
    
    # Return as {index: weight}
    return {int(idx): float(w) for idx, w in zip(final_indices, final_weights)}

def chunk_text(text: str, chunk_size: int = 256, overlap: int = 32, max_chunks: int = 1000) -> list[str]:
    if not text.strip():
        return []
        
    # Process text in character blocks to avoid tokenizer OOM on huge files
    SAFE_CHAR_BLOCK = 50000 
    char_overlap = 1000
    
    chunks = []
    
    # If it's small, fast path without block logic
    if len(text) <= SAFE_CHAR_BLOCK:
        encoding = tokenizer.encode(text)
        tokens = encoding.tokens
        if len(tokens) <= chunk_size:
            return [text]
            
        offsets = encoding.offsets
        step = chunk_size - overlap
        for i in range(0, len(tokens), step):
            if len(chunks) >= max_chunks:
                break
            chunk_offsets = offsets[i:i + chunk_size]
            if not chunk_offsets:
                continue
            non_zero_offsets = [off for off in chunk_offsets if off != (0, 0)]
            if not non_zero_offsets:
                continue
            start_char = non_zero_offsets[0][0]
            end_char = non_zero_offsets[-1][1]
            chunks.append(text[start_char:end_char])
            if i + chunk_size >= len(tokens):
                break
        return chunks

    # Block-wise processing for large files
    char_step = SAFE_CHAR_BLOCK - char_overlap
    for char_idx in range(0, len(text), char_step):
        if len(chunks) >= max_chunks:
            break
            
        text_block = text[char_idx:char_idx + SAFE_CHAR_BLOCK]
        encoding = tokenizer.encode(text_block)
        tokens = encoding.tokens
        offsets = encoding.offsets
        
        step = chunk_size - overlap
        for i in range(0, len(tokens), step):
            if len(chunks) >= max_chunks:
                break
            
            chunk_offsets = offsets[i:i + chunk_size]
            if not chunk_offsets:
                continue
                
            non_zero_offsets = [off for off in chunk_offsets if off != (0, 0)]
            if not non_zero_offsets:
                continue
                
            start_char = non_zero_offsets[0][0]
            end_char = non_zero_offsets[-1][1]
            
            # Avoid duplicating chunks from the overlap region
            if start_char >= char_step and char_idx + SAFE_CHAR_BLOCK < len(text):
                break
                
            chunks.append(text_block[start_char:end_char])
            
            if i + chunk_size >= len(tokens):
                break
                
    return chunks

if __name__ == "__main__":
    print("Testing SPLADE encoding...")
    test_text = "What is a python parser database search?"
    vectors = encode(test_text)
    print(f"Generated sparse vector with {len(vectors)} non-zero weights.")
    # Show top 10 terms
    vocab = tokenizer.get_vocab()
    inv_vocab = {v: k for k, v in vocab.items()}
    sorted_vec = sorted(vectors.items(), key=lambda x: -x[1])[:10]
    print("Top 10 terms with weights:")
    for idx, w in sorted_vec:
        print(f"  {inv_vocab.get(idx, f'#{idx}')}: {w:.4f}")

    print("\nTesting chunk_text...")
    long_text = " ".join(["word"] * 500)
    text_chunks = chunk_text(long_text, chunk_size=100, overlap=10)
    print(f"Split {len(long_text)} characters into {len(text_chunks)} chunks.")
    for idx, c in enumerate(text_chunks):
        c_tokens = tokenizer.encode(c).tokens
        # Filter CLS/SEP from length check
        c_len = len([t for t in c_tokens if t not in ('[CLS]', '[SEP]')])
        print(f"  Chunk {idx}: token count = {c_len}, character length = {len(c)}")

