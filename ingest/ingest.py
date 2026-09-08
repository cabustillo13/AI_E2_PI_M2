import os
import argparse
import glob

from ingest.chunking import FixedSizeChunker, HeaderStructuralChunker
from src.vector_store import VectorStoreManager
from src.llm_client import LLMClient

# Cargar variables de entorno desde el archivo .env
from dotenv import load_dotenv
load_dotenv()


def run_ingestion(strategy: str = "structural"):
    corpus_dir = "data/corpus"
    files = glob.glob(os.path.join(corpus_dir, "*.md"))
    
    if not files:
        print(f"Error: No se encontraron archivos .md en {corpus_dir}")
        return

    print(f"--- Iniciando Ingesta [Estrategia: {strategy.upper()}] ---")
    
    chunker = FixedSizeChunker() if strategy == "fixed" else HeaderStructuralChunker()
    all_chunks = []

    for file_path in files:
        doc_name = os.path.basename(file_path)
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        chunks = chunker.chunk_text(content, doc_name)
        all_chunks.extend(chunks)

    print(f"Total de chunks generados: {len(all_chunks)}")

    llm_client = LLMClient()
    texts = [c["content"] for c in all_chunks]
    print("Generando embeddings con OpenAI...")
    embeddings = llm_client.get_embeddings(texts)

    vector_store = VectorStoreManager()
    collection_name = f"nubbix_docs_{strategy}"
    vector_store.index_chunks(collection_name, all_chunks, embeddings)
    print(f"Indexación exitosa en la colección ChromaDB: '{collection_name}'")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Script reproducible de ingesta de datos Nubbix.")
    parser.add_argument("--strategy", choices=["fixed", "structural"], default="structural",
                        help="Estrategia de chunking a utilizar (fixed o structural)")
    args = parser.parse_args()
    run_ingestion(args.strategy)