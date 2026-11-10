from threading import Lock
from typing import Optional
from sentence_transformers import CrossEncoder
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class CrossEncoderReranker:
    """Optional configurable cross-encoder reranker for top retrieved candidates."""

    def __init__(self):
        self._lock = Lock()
        self._model: Optional[CrossEncoder] = None
        self._loaded_name: Optional[str] = None

    def is_enabled(self) -> bool:
        return bool(get_settings().cross_encoder_enabled)

    def _ensure_model(self) -> Optional[CrossEncoder]:
        if not self.is_enabled():
            return None
        target = get_settings().cross_encoder_model_name
        with self._lock:
            if self._model is None or self._loaded_name != target:
                try:
                    logger.info("loading_cross_encoder_model", model_name=target)
                    self._model = CrossEncoder(target, device="cpu")
                    self._loaded_name = target
                except Exception as exc:
                    logger.warning("cross_encoder_load_failed", error=str(exc))
                    self._model = None
            return self._model

    def score_pairs(self, query_doc: str, candidate_docs: list[str]) -> Optional[list[float]]:
        model = self._ensure_model()
        if model is None or not candidate_docs:
            return None
        try:
            pairs = [(query_doc[:1500], doc[:1500]) for doc in candidate_docs]
            raw_scores = model.predict(pairs, show_progress_bar=False)
            # Sigmoid normalize logits to 0-100
            import math
            return [round(100.0 / (1.0 + math.exp(-float(s))), 2) for s in raw_scores]
        except Exception as exc:
            logger.warning("cross_encoder_predict_failed", error=str(exc))
            return None


cross_encoder_reranker = CrossEncoderReranker()
