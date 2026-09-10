import os
from typing import List, Dict, Any


class CrossEncoderReranker:
    """
    Re-ranking del pool de candidatos recuperados por HybridRetriever usando
    un cross-encoder (par pregunta-chunk evaluado conjuntamente, en vez de
    embeddings independientes). Es más preciso que la similaridad vectorial
    o RRF porque el modelo ve la pregunta y el chunk juntos, pero también
    más lento: por eso se deja detrás del flag `enable_rerank` en vez de
    aplicarse siempre (ver "buenas prácticas" de la consigna: medir el
    costo en latencia antes de adoptarlo por defecto).

    Carga perezosa (lazy): el modelo de sentence-transformers solo se
    descarga/instancia la primera vez que se pide un rerank real, para no
    penalizar el arranque del servicio cuando `enable_rerank=False`.
    """

    _instance = None  # singleton para no recargar el modelo en cada request

    def __init__(self):
        self.model_name = os.getenv("CROSS_ENCODER_MODEL", "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1")
        self._model = None

    @classmethod
    def get_instance(cls) -> "CrossEncoderReranker":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_model(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(self.model_name)
        return self._model

    def rerank(self, query: str, candidates: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
        """
        Reordena `candidates` (salida de HybridRetriever, ya con RRF aplicado)
        según el score del cross-encoder y devuelve los `top_k` mejores.
        El score original (RRF) se conserva en `rrf_score` por si se quiere
        auditar el cambio de orden.
        """
        if not candidates:
            return candidates

        model = self._load_model()
        pairs = [(query, c["content"]) for c in candidates]
        ce_scores = model.predict(pairs)

        reranked = []
        for candidate, ce_score in zip(candidates, ce_scores):
            item = dict(candidate)
            item["rrf_score"] = candidate.get("score")
            item["score"] = round(float(ce_score), 4)
            reranked.append(item)

        reranked.sort(key=lambda c: c["score"], reverse=True)
        return reranked[:top_k]