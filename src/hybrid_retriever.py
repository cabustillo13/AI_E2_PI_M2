from typing import List, Dict, Any
from rank_bm25 import BM25Okapi
from src.vector_store import VectorStoreManager
from src.llm_client import LLMClient
from src.reranker import CrossEncoderReranker


class HybridRetriever:
    """Implementa búsqueda Híbrida (BM25 + Vectorial) combinada mediante RRF (Reciprocal Rank Fusion)."""
    def __init__(self, collection_name: str = "nubbix_docs_structural"):
        self.collection_name = collection_name
        self.vector_store = VectorStoreManager()
        self.llm_client = LLMClient()
        self.reranker = CrossEncoderReranker.get_instance()
        self._init_bm25()

    def _init_bm25(self):
        self.all_chunks = self.vector_store.get_all_chunks(self.collection_name)
        corpus_tokens = [c["content"].lower().split() for c in self.all_chunks]
        self.bm25 = BM25Okapi(corpus_tokens)

    def search_bm25(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        tokenized_query = query.lower().split()
        scores = self.bm25.get_scores(tokenized_query)
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        
        results = []
        for idx in top_indices:
            chunk = self.all_chunks[idx]
            results.append({
                "chunk_id": chunk["chunk_id"],
                "content": chunk["content"],
                "metadata": chunk["metadata"],
                "score": float(scores[idx])
            })
        return results

    def hybrid_search(self, query: str, top_k: int = 3, rrf_k: int = 60,
                       enable_rerank: bool = False, rerank_pool_size: int = 10) -> List[Dict[str, Any]]:
        # 1. Recuperación vectorial
        query_emb = self.llm_client.get_embeddings([query])[0]
        vec_results = self.vector_store.search_vectorial(self.collection_name, query_emb, top_k=10)

        # 2. Recuperación léxica BM25
        bm25_results = self.search_bm25(query, top_k=10)

        # 3. Reciprocal Rank Fusion (RRF)
        rrf_scores: Dict[str, float] = {}
        chunk_map: Dict[str, Dict[str, Any]] = {}

        for rank, item in enumerate(vec_results):
            cid = item["chunk_id"]
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (rrf_k + rank + 1))
            chunk_map[cid] = item

        for rank, item in enumerate(bm25_results):
            cid = item["chunk_id"]
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (rrf_k + rank + 1))
            chunk_map[cid] = item

        # El pool de candidatos que se lleva al re-ranking es más grande que top_k:
        # el cross-encoder necesita margen para poder promover un chunk que RRF
        # dejó afuera del top-k inicial, si no habría re-ranking real.
        pool_size = rerank_pool_size if enable_rerank else top_k
        sorted_chunks = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:pool_size]

        candidates = []
        for cid, score in sorted_chunks:
            item = chunk_map[cid]
            candidates.append({
                "chunk_id": cid,
                "content": item["content"],
                "metadata": item["metadata"],
                "score": round(score, 4)
            })

        # 4. Re-ranking opcional con cross-encoder (ver src/reranker.py)
        if enable_rerank:
            return self.reranker.rerank(query, candidates, top_k=top_k)

        return candidates[:top_k]