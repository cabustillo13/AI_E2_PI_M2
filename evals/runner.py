import json
import os
import sys
import yaml
import argparse
from typing import List, Dict, Any

from src.service import RAGService
from src.llm_client import LLMClient

# Cargar variables de entorno desde el .env
from dotenv import load_dotenv
load_dotenv()


class RAGEvaluator:
    """
    Corre la suite de evals sobre una estrategia de chunking (structural o fixed).

    IMPORTANTE: la fórmula de precision/recall/hit-rate es EXACTAMENTE LA MISMA
    para las dos estrategias (intersección contra `expected_chunk_ids[strategy]`).
    El golden dataset trae, para cada pregunta, el/los chunk_id correcto(s) YA calculados
    para cada estrategia (ver evals/dataset.jsonl), así que no hace falta
    ninguna heurística por estrategia acá.
    """

    def __init__(self, strategy: str = "structural", enable_rerank: bool = False, debug: bool = False):
        self.strategy = strategy
        self.enable_rerank = enable_rerank
        self.debug = debug
        collection_name = f"nubbix_docs_{strategy}"
        self.rag_service = RAGService(collection_name=collection_name)
        self.llm_client = LLMClient()
        self.judge_prompt = self._load_judge_prompt()

    def _load_judge_prompt(self) -> str:
        with open("prompts/judge_v1.yaml", "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data.get("system_prompt", "")

    def evaluate_groundedness(self, question: str, answer: str, chunks: List[str], case_id: str = "") -> float:
        context_text = "\n".join(chunks)
        user_p = f"CONTEXTO PROVISTO:\n{context_text}\n\nPREGUNTA: {question}\n\nRESPUESTA EVALUADA:\n{answer}"
        
        try:
            res = self.llm_client.get_completion(self.judge_prompt, user_p)
            cleaned = res["content"].strip().replace("```json", "").replace("```", "")
            data = json.loads(cleaned)
            return float(data.get("score", 0.0))
        except Exception as e:
            # Esto podría ser un error silencioso devolviendo 0.5 siempre.
            # Por eso se loguea a stderr para poder diagnosticar QUÉ pregunta
            # rompe el parseo del judge y por qué (con --debug se ve el raw output).
            print(f"[WARN] Judge parsing falló en '{case_id}': {e}", file=sys.stderr)
            if self.debug:
                print(f"[DEBUG] Raw judge output para '{case_id}': {res.get('content', '<sin respuesta>')!r}",
                      file=sys.stderr)
            return 0.5

    def run_suite(self, dataset_path: str = "evals/dataset.jsonl", top_k: int = 3) -> Dict[str, Any]:
        with open(dataset_path, "r", encoding="utf-8") as f:
            test_cases = [json.loads(line) for line in f]

        total_cases = len(test_cases)
        hits = 0
        precisions: List[float] = []
        recalls: List[float] = []
        groundedness_scores: List[float] = []
        honest_refusals = 0
        out_of_scope_cases = 0

        cross_doc_recalls: List[float] = []
        cross_doc_full_hits: List[float] = []
        cross_doc_cases = 0

        hard_negative_leaks: List[float] = []
        hard_negative_cases = 0

        reciprocal_ranks: List[float] = []

        debug_rows: List[Dict[str, Any]] = []

        rerank_label = "ON" if self.enable_rerank else "OFF"
        print(f"\n--- Corriendo Suite de Evals [Estrategia: {self.strategy.upper()} | Rerank: {rerank_label}] ---")

        for tc in test_cases:
            q = tc["question"]
            expected_ids = set(tc["expected_chunk_ids"][self.strategy])
            hard_negative_ids = set(tc.get("hard_negative_chunk_ids", {}).get(self.strategy, []))
            is_oos = tc.get("is_out_of_scope", False)
            is_cross_document = tc.get("is_cross_document", False)
            is_hard_negative_case = tc.get("is_hard_negative_case", False)

            rag_res = self.rag_service.answer_question(q, top_k=top_k, enable_rerank=self.enable_rerank)
            retrieved_ids = [c.chunk_id for c in rag_res.chunks_related]
            retrieved_set = set(retrieved_ids)

            # --- Métrica de Retrieval (misma fórmula para las dos estrategias) ---
            precision = recall = hit = None
            if not is_oos:
                intersection = expected_ids.intersection(retrieved_set)
                precision = len(intersection) / len(retrieved_ids) if retrieved_ids else 0.0
                recall = len(intersection) / len(expected_ids) if expected_ids else 0.0
                hit = 1.0 if len(intersection) > 0 else 0.0

                precisions.append(precision)
                recalls.append(recall)
                if hit:
                    hits += 1

                # MRR: a diferencia de hit/precision/recall (que solo miran si el chunk
                # correcto ENTRÓ al top-k), esto premia que haya quedado PRIMERO.
                # Es la métrica que expone si el rerank mejora o empeora el orden real,
                # cosa que las métricas de conjunto no pueden ver.
                rr = 0.0
                for rank, cid in enumerate(retrieved_ids, start=1):
                    if cid in expected_ids:
                        rr = 1.0 / rank
                        break
                reciprocal_ranks.append(rr)

                if is_cross_document:
                    cross_doc_cases += 1
                    cross_doc_recalls.append(recall)
                    # Métrica más estricta: ¿recuperó los chunks de LOS DOS documentos, no solo uno?
                    full_hit = 1.0 if expected_ids.issubset(retrieved_set) else 0.0
                    cross_doc_full_hits.append(full_hit)
            else:
                out_of_scope_cases += 1
                if "no se encuentra disponible" in rag_res.system_answer.lower():
                    honest_refusals += 1

            # --- Hard negatives: ¿se coló el chunk distractor en el top-k? ---
            leaked = None
            if is_hard_negative_case and hard_negative_ids:
                hard_negative_cases += 1
                leaked = 1.0 if hard_negative_ids.intersection(retrieved_set) else 0.0
                hard_negative_leaks.append(leaked)

            # --- Métrica de Generación (Groundedness) ---
            chunk_contents = [c.content for c in rag_res.chunks_related]
            g_score = self.evaluate_groundedness(q, rag_res.system_answer, chunk_contents, case_id=tc["id"])
            groundedness_scores.append(g_score)

            if self.debug:
                debug_rows.append({
                    "id": tc["id"],
                    "question": q,
                    "expected_ids": sorted(expected_ids),
                    "retrieved_ids": retrieved_ids,
                    "chunk_scores": [c.score for c in rag_res.chunks_related],
                    "precision": precision,
                    "recall": recall,
                    "hit": hit,
                    "hard_negative_leaked": leaked,
                    "groundedness": g_score,
                })

        avg_precision = sum(precisions) / len(precisions) if precisions else 0.0
        avg_recall = sum(recalls) / len(recalls) if recalls else 0.0
        hit_rate = hits / (total_cases - out_of_scope_cases) if (total_cases - out_of_scope_cases) > 0 else 0.0
        avg_groundedness = sum(groundedness_scores) / len(groundedness_scores) if groundedness_scores else 0.0
        refusal_accuracy = honest_refusals / out_of_scope_cases if out_of_scope_cases > 0 else 1.0

        avg_cross_doc_recall = sum(cross_doc_recalls) / len(cross_doc_recalls) if cross_doc_recalls else 0.0
        cross_doc_full_hit_rate = sum(cross_doc_full_hits) / len(cross_doc_full_hits) if cross_doc_full_hits else 0.0

        hard_negative_leakage_rate = (
            sum(hard_negative_leaks) / len(hard_negative_leaks) if hard_negative_leaks else 0.0
        )

        metrics = {
            "strategy": self.strategy,
            "rerank_enabled": self.enable_rerank,
            "total_test_cases": total_cases,
            "precision_at_k": round(avg_precision, 4),
            "recall_at_k": round(avg_recall, 4),
            "hit_rate": round(hit_rate, 4),
            "mrr": round(sum(reciprocal_ranks) / len(reciprocal_ranks), 4) if reciprocal_ranks else 0.0,
            "avg_groundedness": round(avg_groundedness, 4),
            "groundedness_score_distribution": sorted(set(groundedness_scores)),
            "refusal_accuracy": round(refusal_accuracy, 4),
            "cross_document_cases": cross_doc_cases,
            "cross_document_recall_at_k": round(avg_cross_doc_recall, 4),
            "cross_document_full_hit_rate": round(cross_doc_full_hit_rate, 4),
            "hard_negative_cases": hard_negative_cases,
            "hard_negative_leakage_rate": round(hard_negative_leakage_rate, 4),
        }

        print(json.dumps(metrics, indent=2, ensure_ascii=False))
        self._save_results(metrics)
        if self.debug:
            self._save_debug(debug_rows)
        return metrics

    def _save_results(self, metrics: Dict[str, Any]):
        """Persiste el resultado de la corrida para poder diffear rerank ON vs OFF y estrategia A vs B."""
        os.makedirs("evals/results", exist_ok=True)
        rerank_suffix = "rerank_on" if self.enable_rerank else "rerank_off"
        out_path = f"evals/results/{self.strategy}__{rerank_suffix}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2, ensure_ascii=False)

    def _save_debug(self, debug_rows: List[Dict[str, Any]]):
        """Guarda el detalle pregunta-por-pregunta para auditar retrieval y groundedness."""
        os.makedirs("evals/results", exist_ok=True)
        rerank_suffix = "rerank_on" if self.enable_rerank else "rerank_off"
        out_path = f"evals/results/{self.strategy}__{rerank_suffix}__debug.jsonl"
        with open(out_path, "w", encoding="utf-8") as f:
            for row in debug_rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"[DEBUG] Detalle por pregunta guardado en {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Runner de Evaluaciones RAG.")
    parser.add_argument("--strategy", choices=["fixed", "structural"], default="structural")
    parser.add_argument("--rerank", action="store_true",
                         help="Habilita re-ranking con cross-encoder para medir el delta vs. sin rerank")
    parser.add_argument("--debug", action="store_true",
                         help="Guarda el detalle pregunta-por-pregunta y el raw output del judge ante fallos de parseo")
    args = parser.parse_args()

    evaluator = RAGEvaluator(strategy=args.strategy, enable_rerank=args.rerank, debug=args.debug)
    evaluator.run_suite()