import json
import yaml
import argparse
from typing import List, Dict, Any

from src.service import RAGService
from src.llm_client import LLMClient

# Cargar variables de entorno desde .env
from dotenv import load_dotenv
load_dotenv()


class RAGEvaluator:
    def __init__(self, strategy: str = "structural"):
        self.strategy = strategy
        collection_name = f"nubbix_docs_{strategy}"
        self.rag_service = RAGService(collection_name=collection_name)
        self.llm_client = LLMClient()
        self.judge_prompt = self._load_judge_prompt()

    def _load_judge_prompt(self) -> str:
        with open("prompts/judge_v1.yaml", "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data.get("system_prompt", "")

    def evaluate_groundedness(self, question: str, answer: str, chunks: List[str]) -> float:
        context_text = "\n".join(chunks)
        user_p = f"CONTEXTO PROVISTO:\n{context_text}\n\nPREGUNTA: {question}\n\nRESPUESTA EVALUADA:\n{answer}"
        
        try:
            res = self.llm_client.get_completion(self.judge_prompt, user_p)
            cleaned = res["content"].strip().replace("```json", "").replace("```", "")
            data = json.loads(cleaned)
            return float(data.get("score", 0.0))
        except Exception:
            return 0.5

    def run_suite(self, dataset_path: str = "evals/dataset.jsonl", top_k: int = 3) -> Dict[str, Any]:
        with open(dataset_path, "r", encoding="utf-8") as f:
            test_cases = [json.loads(line) for line in f]

        total_cases = len(test_cases)
        hits = 0
        precisions = []
        recalls = []
        groundedness_scores = []
        honest_refusals = 0
        out_of_scope_cases = 0

        print(f"\n--- Corriendo Suite de Evals [Estrategia: {self.strategy.upper()}] ---")

        for tc in test_cases:
            q = tc["question"]
            expected_ids = set(tc["expected_chunk_ids"])
            is_oos = tc.get("is_out_of_scope", False)

            rag_res = self.rag_service.answer_question(q, top_k=top_k)
            retrieved_ids = [c.chunk_id for c in rag_res.chunks_related]
            retrieved_set = set(retrieved_ids)

            # Métrica de Retrieval
            if not is_oos:
                intersection = expected_ids.intersection(retrieved_set)
                precision = len(intersection) / len(retrieved_ids) if retrieved_ids else 0.0
                recall = len(intersection) / len(expected_ids) if expected_ids else 0.0
                hit = 1.0 if len(intersection) > 0 else 0.0

                precisions.append(precision)
                recalls.append(recall)
                if hit: hits += 1
            else:
                out_of_scope_cases += 1
                if "no se encuentra disponible" in rag_res.system_answer.lower():
                    honest_refusals += 1

            # Métrica de Generación (Groundedness)
            chunk_contents = [c.content for c in rag_res.chunks_related]
            g_score = self.evaluate_groundedness(q, rag_res.system_answer, chunk_contents)
            groundedness_scores.append(g_score)

        avg_precision = sum(precisions) / len(precisions) if precisions else 0.0
        avg_recall = sum(recalls) / len(recalls) if recalls else 0.0
        hit_rate = hits / (total_cases - out_of_scope_cases) if (total_cases - out_of_scope_cases) > 0 else 0.0
        avg_groundedness = sum(groundedness_scores) / len(groundedness_scores) if groundedness_scores else 0.0
        refusal_accuracy = honest_refusals / out_of_scope_cases if out_of_scope_cases > 0 else 1.0

        metrics = {
            "strategy": self.strategy,
            "total_test_cases": total_cases,
            "precision_at_k": round(avg_precision, 4),
            "recall_at_k": round(avg_recall, 4),
            "hit_rate": round(hit_rate, 4),
            "avg_groundedness": round(avg_groundedness, 4),
            "refusal_accuracy": round(refusal_accuracy, 4)
        }

        print(json.dumps(metrics, indent=2, ensure_ascii=False))
        return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Runner de Evaluaciones RAG.")
    parser.add_argument("--strategy", choices=["fixed", "structural"], default="structural")
    args = parser.parse_args()
    
    evaluator = RAGEvaluator(strategy=args.strategy)
    evaluator.run_suite()