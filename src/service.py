import os
import yaml
from src.hybrid_retriever import HybridRetriever
from src.llm_client import LLMClient
from src.metrics import MetricsTracker
from src.models import RAGQueryResponse, ChunkRelated


class RAGService:
    def __init__(self, collection_name: str = "nubbix_docs_structural"):
        self.retriever = HybridRetriever(collection_name=collection_name)
        self.llm_client = LLMClient()
        self.metrics = MetricsTracker()
        self.prompt_template = self._load_prompt()

    def _load_prompt(self) -> str:
        prompt_path = "prompts/rag_v1.yaml"
        if os.path.exists(prompt_path):
            with open(prompt_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                return data.get("system_prompt", "")
        return "Responde utilizando únicamente el contexto provisto."

    def answer_question(self, question: str, top_k: int = 3) -> RAGQueryResponse:
        # Step 1: Retrieval Híbrido
        retrieved_chunks = self.retriever.hybrid_search(question, top_k=top_k)

        # Step 2: Formatear contexto para el LLM
        context_str = ""
        chunks_response = []
        for idx, chunk in enumerate(retrieved_chunks):
            context_str += f"\n--- ID CHUNK: {chunk['chunk_id']} ---\n{chunk['content']}\n"
            chunks_response.append(
                ChunkRelated(
                    chunk_id=chunk["chunk_id"],
                    source=chunk["metadata"].get("source", "unknown"),
                    header=chunk["metadata"].get("header", None),
                    content=chunk["content"],
                    score=chunk["score"]
                )
            )

        user_prompt = f"PREGUNTA DEL EMPLEADO:\n{question}\n\nDOCUMENTACIÓN OFICIAL DISPONIBLE:\n{context_str}"

        # Step 3: Generación con LLM
        llm_out = self.llm_client.get_completion(
            system_prompt=self.prompt_template,
            user_prompt=user_prompt
        )

        response = RAGQueryResponse(
            user_question=question,
            system_answer=llm_out["content"],
            chunks_related=chunks_response,
            latency_seconds=round(llm_out["latency"], 3),
            estimated_cost_usd=round(llm_out["cost"], 6)
        )

        # Métrica logging
        self.metrics.log_event("rag_query", {
            "question": question,
            "chunks_count": len(chunks_response),
            "latency": response.latency_seconds,
            "cost": response.estimated_cost_usd
        })

        return response