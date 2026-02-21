"""Local embedding generation for document vectorization.
Uses fastembed to generate embeddings completely locally without rate limits.
"""

from typing import Optional, List
from fastembed import TextEmbedding

# Module-level cache for embeddings to avoid redundant computation
_embedding_cache: dict[str, list[float]] = {}


class EmbeddingGenerator:
    def __init__(self):
        # Initialize fastembed TextEmbedding with a lightweight model
        # BAAI/bge-small-en-v1.5 has 384 dimensions and is very fast
        self.model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5", threads=2)
        self.dimensions = 384

    def embed_text(self, text: str) -> list[float]:
        """Generate embedding for a single text string."""
        cache_key = hash(text[:200])
        if cache_key in _embedding_cache:
            return _embedding_cache[cache_key]

        # TextEmbedding.embed returns a generator of arrays, we get the first one
        embedding_generator = self.model.embed([text])
        result = list(embedding_generator)[0].tolist()
        
        _embedding_cache[cache_key] = result
        return result

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts."""
        all_embeddings = []
        batch_size = 50

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            embedding_generator = self.model.embed(batch)
            all_embeddings.extend([emb.tolist() for emb in embedding_generator])

        return all_embeddings

    def embed_query(self, query: str) -> Optional[list[float]]:
        """Generate embedding for a search query."""
        cache_key = hash(f"query:{query[:200]}")
        if cache_key in _embedding_cache:
            return _embedding_cache[cache_key]

        try:
            # For query, you could prefix with "query: " but BAAI handles it well anyway
            embedding_generator = self.model.query_embed([query])
            result = list(embedding_generator)[0].tolist()
            
            _embedding_cache[cache_key] = result
            return result
        except Exception as e:
            print(f"[embeddings] Local embed_query failed: {e}")
            return None
