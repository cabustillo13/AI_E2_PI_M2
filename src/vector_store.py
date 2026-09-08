import os
import chromadb
from typing import List, Dict, Any


class VectorStoreManager:
    def __init__(self):
        persist_dir = os.getenv("CHROMA_PERSIST_DIR", "./data/chroma_db")
        self.client = chromadb.PersistentClient(path=persist_dir)

    def index_chunks(self, collection_name: str, chunks: List[Dict[str, Any]], embeddings: List[List[float]]):
        try:
            self.client.delete_collection(name=collection_name)
        except Exception:
            pass

        collection = self.client.create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )

        ids = [c["chunk_id"] for c in chunks]
        documents = [c["content"] for c in chunks]
        metadatas = [c["metadata"] for c in chunks]

        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas
        )

    def search_vectorial(self, collection_name: str, query_embedding: List[float], top_k: int = 10) -> List[Dict[str, Any]]:
        collection = self.client.get_collection(name=collection_name)
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"]
        )

        retrieved = []
        if results and results["ids"]:
            for i in range(len(results["ids"][0])):
                retrieved.append({
                    "chunk_id": results["ids"][0][i],
                    "content": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "score": 1.0 - results["distances"][0][i]  # Cosine similarity approx
                })
        return retrieved

    def get_all_chunks(self, collection_name: str) -> List[Dict[str, Any]]:
        collection = self.client.get_collection(name=collection_name)
        data = collection.get(include=["documents", "metadatas"])
        chunks = []
        for i in range(len(data["ids"])):
            chunks.append({
                "chunk_id": data["ids"][i],
                "content": data["documents"][i],
                "metadata": data["metadatas"][i]
            })
        return chunks