"""Pinecone vector store wrapper with namespace-per-sector isolation."""

from typing import Optional
from pinecone import Pinecone, ServerlessSpec

from config.settings import get_settings


class VectorStore:
    def __init__(self):
        settings = get_settings()
        self.pc = Pinecone(api_key=settings.pinecone_api_key)
        self.index_name = settings.pinecone_index_name
        self.dimensions = settings.embedding_dimensions
        self._index = None

    @property
    def index(self):
        if self._index is None:
            self._index = self.pc.Index(self.index_name)
        return self._index

    def ensure_index(self):
        """Create the Pinecone index if it doesn't exist.
        If it exists with the wrong dimension, delete and recreate it."""
        existing = {idx.name: idx for idx in self.pc.list_indexes()}

        if self.index_name in existing:
            # Check if dimension matches — if not, we must recreate
            index_info = self.pc.describe_index(self.index_name)
            current_dim = index_info.dimension
            if current_dim != self.dimensions:
                print(f"[vector_store] Index '{self.index_name}' has dim={current_dim} "
                      f"but config requests dim={self.dimensions}. Recreating...")
                self.pc.delete_index(self.index_name)
                self._index = None  # Reset cached handle
            else:
                return self.index  # Already correct

        self.pc.create_index(
            name=self.index_name,
            dimension=self.dimensions,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
        # Wait for index to be ready
        import time
        for _ in range(30):
            info = self.pc.describe_index(self.index_name)
            if info.status.get("ready", False):
                break
            time.sleep(2)

        self._index = None  # Force fresh connection
        return self.index


    def upsert(
        self,
        vectors: list[dict],
        namespace: Optional[str] = None,
    ):
        """
        Upsert vectors into Pinecone.

        vectors: list of {"id": str, "values": list[float], "metadata": dict}
        namespace: sector name or custom namespace for isolation
        """
        batch_size = 100
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i:i + batch_size]
            self.index.upsert(vectors=batch, namespace=namespace)

    def query(
        self,
        vector: list[float],
        top_k: int = 10,
        namespace: Optional[str] = None,
        filter: Optional[dict] = None,
        include_metadata: bool = True,
    ) -> list[dict]:
        """
        Query for similar vectors.

        Returns list of {"id", "score", "metadata"} dicts.
        """
        results = self.index.query(
            vector=vector,
            top_k=top_k,
            namespace=namespace,
            filter=filter,
            include_metadata=include_metadata,
        )

        return [
            {
                "id": match.id,
                "score": match.score,
                "metadata": match.metadata if include_metadata else {},
            }
            for match in results.matches
        ]

    def delete(
        self,
        ids: Optional[list[str]] = None,
        namespace: Optional[str] = None,
        delete_all: bool = False,
        filter: Optional[dict] = None,
    ):
        """Delete vectors by ID, filter, or clear entire namespace."""
        if delete_all:
            self.index.delete(delete_all=True, namespace=namespace)
        elif ids:
            self.index.delete(ids=ids, namespace=namespace)
        elif filter:
            self.index.delete(filter=filter, namespace=namespace)

    def get_stats(self, namespace: Optional[str] = None) -> dict:
        """Get index statistics."""
        stats = self.index.describe_index_stats()
        if namespace:
            ns_stats = stats.namespaces.get(namespace, {})
            return {"namespace": namespace, "vector_count": getattr(ns_stats, "vector_count", 0)}
        return {
            "total_vector_count": stats.total_vector_count,
            "namespaces": {
                ns: {"vector_count": data.vector_count}
                for ns, data in stats.namespaces.items()
            },
        }

    def list_namespaces(self) -> list[str]:
        """List all namespaces (sectors) in the index."""
        stats = self.index.describe_index_stats()
        return list(stats.namespaces.keys())
