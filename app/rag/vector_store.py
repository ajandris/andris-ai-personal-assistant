"""FAISS vector store module for embeddings storage and similarity search.

Stores the vector index and document chunks in the configured RAG directory.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import faiss
import numpy as np

from app.core.config import settings


class FAISSVectorStore:
    """FAISS-based vector database for document embeddings."""

    def __init__(self, dimension: int = 1536, metric: str = "cosine") -> None:
        """Initialize FAISS index.

        Args:
            dimension: Dimensionality of embeddings (default: 1536 for OpenAI embeddings).
            metric: Distance metric ('cosine' for normalized inner product or 'l2').
        """
        self.dimension = dimension
        self.metric = metric
        if metric == "cosine":
            self.index = faiss.IndexFlatIP(dimension)
        else:
            self.index = faiss.IndexFlatL2(dimension)
        self.documents: List[Dict[str, Any]] = []

    def _normalize(self, vectors: np.ndarray) -> np.ndarray:
        """L2 normalize vectors for cosine similarity."""
        vectors = vectors.astype(np.float32)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return vectors / norms

    def add(
        self,
        vectors: Union[np.ndarray, List[List[float]]],
        documents: List[Union[str, Dict[str, Any]]],
    ) -> int:
        """Add vectors and their associated metadata/documents to the index.

        Args:
            vectors: 2D array or list of embedding vectors.
            documents: List of text strings or metadata dicts for each vector.

        Returns:
            Total count of vectors in the store.
        """
        arr = np.asarray(vectors, dtype=np.float32)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)

        if arr.shape[1] != self.dimension:
            raise ValueError(
                f"Vector dimension {arr.shape[1]} does not match store dimension {self.dimension}"
            )

        if len(documents) != arr.shape[0]:
            raise ValueError(
                f"Number of documents ({len(documents)}) does not match number of vectors ({arr.shape[0]})"
            )

        if self.metric == "cosine":
            arr = self._normalize(arr)

        self.index.add(arr)
        for doc in documents:
            if isinstance(doc, str):
                self.documents.append({"text": doc})
            else:
                self.documents.append(doc)

        return self.count()

    def search(
        self,
        query_vector: Union[np.ndarray, List[float]],
        top_k: int = 4,
    ) -> List[Dict[str, Any]]:
        """Search for top_k most similar documents.

        Args:
            query_vector: 1D or 2D vector for the query.
            top_k: Maximum number of results to return.

        Returns:
            List of result dicts with document data, distance/score, and vector id.
        """
        if self.count() == 0:
            return []

        q = np.asarray(query_vector, dtype=np.float32)
        if q.ndim == 1:
            q = q.reshape(1, -1)

        if q.shape[1] != self.dimension:
            raise ValueError(
                f"Query dimension {q.shape[1]} does not match store dimension {self.dimension}"
            )

        if self.metric == "cosine":
            q = self._normalize(q)

        k = min(top_k, self.count())
        distances, indices = self.index.search(q, k)

        results: List[Dict[str, Any]] = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1 or idx >= len(self.documents):
                continue
            doc_data = dict(self.documents[idx])
            doc_data["score"] = float(dist)
            doc_data["index"] = int(idx)
            results.append(doc_data)

        return results

    def count(self) -> int:
        """Return total number of vectors in the index."""
        return self.index.ntotal

    def save(self, directory: Optional[Union[str, Path]] = None) -> Path:
        """Persist index and document metadata to disk.

        Args:
            directory: Directory path to save to (defaults to settings.vector_db_path).

        Returns:
            Resolved Path where index was saved.
        """
        target_dir = Path(directory or settings.vector_db_path)
        target_dir.mkdir(parents=True, exist_ok=True)

        index_file = target_dir / "index.faiss"
        meta_file = target_dir / "chunks.json"

        faiss.write_index(self.index, str(index_file))
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "dimension": self.dimension,
                    "metric": self.metric,
                    "documents": self.documents,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

        return target_dir

    @classmethod
    def load(cls, directory: Optional[Union[str, Path]] = None) -> FAISSVectorStore:
        """Load persisted index and documents from disk.

        Args:
            directory: Directory containing index.faiss and chunks.json
                       (defaults to settings.vector_db_path).

        Returns:
            Loaded FAISSVectorStore instance.
        """
        source_dir = Path(directory or settings.vector_db_path)
        index_file = source_dir / "index.faiss"
        meta_file = source_dir / "chunks.json"

        if not index_file.exists() or not meta_file.exists():
            raise FileNotFoundError(
                f"FAISS database files not found in {source_dir}. "
                f"Expected {index_file} and {meta_file}"
            )

        with open(meta_file, "r", encoding="utf-8") as f:
            meta = json.load(f)

        store = cls(
            dimension=meta.get("dimension", 1536),
            metric=meta.get("metric", "cosine"),
        )
        store.index = faiss.read_index(str(index_file))
        store.documents = meta.get("documents", [])
        return store
