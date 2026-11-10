import hashlib
from threading import Lock
from typing import Optional
import numpy as np
from sentence_transformers import SentenceTransformer
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class EmbeddingService:
    """Thread-safe Sentence Transformers embedding generator and similarity calculator."""

    def __init__(self):
        self._lock = Lock()
        self._model: Optional[SentenceTransformer] = None
        self._loaded_model_name: Optional[str] = None

    def get_active_model_name(self) -> str:
        return get_settings().embedding_model_name

    def get_model_version(self) -> str:
        name = self.get_active_model_name()
        return f"{name}@sentence-transformers-3.3.1"

    def _ensure_model(self, model_name: Optional[str] = None) -> SentenceTransformer:
        target = model_name or self.get_active_model_name()
        with self._lock:
            if self._model is None or self._loaded_model_name != target:
                logger.info("loading_embedding_model", model_name=target)
                self._model = SentenceTransformer(target, device="cpu")
                self._loaded_model_name = target
            return self._model

    @staticmethod
    def compute_doc_hash(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def encode_text(self, text: str, model_name: Optional[str] = None) -> list[float]:
        model = self._ensure_model(model_name)
        vec = model.encode(
            [text or ""],
            normalize_embeddings=True,
            show_progress_bar=False,
        )[0]
        return [float(x) for x in vec.tolist()]

    def encode_batch(self, texts: list[str], model_name: Optional[str] = None) -> list[list[float]]:
        if not texts:
            return []
        model = self._ensure_model(model_name)
        matrix = model.encode(
            [t or "" for t in texts],
            batch_size=32,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [[float(x) for x in row.tolist()] for row in matrix]

    @staticmethod
    def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
        a = np.asarray(vec_a, dtype=np.float32)
        b = np.asarray(vec_b, dtype=np.float32)
        denom = float(np.linalg.norm(a) * np.linalg.norm(b))
        if denom <= 1e-12:
            return 0.0
        return float(np.dot(a, b) / denom)

    @staticmethod
    def normalize_cosine_to_100(cosine_sim: float) -> float:
        return round(max(0.0, min(100.0, cosine_sim * 100.0)), 2)


embedding_service = EmbeddingService()
