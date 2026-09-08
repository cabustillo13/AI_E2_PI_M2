import argparse
import uvicorn
from fastapi import FastAPI, HTTPException

from src.models import RAGQueryRequest, RAGQueryResponse
from src.service import RAGService

# Cargar variables de entorno desde el archivo .env
from dotenv import load_dotenv
load_dotenv()

app = FastAPI(
    title="Nubbix Assist - RAG API",
    description="Asistente de conocimiento interno con Retrieval Híbrido y Citas de Fuentes",
    version="2.0.0"
)

rag_service = None


@app.on_event("startup")
def startup_event():
    global rag_service
    rag_service = RAGService(collection_name="nubbix_docs_structural")


@app.post("/api/v1/query", response_model=RAGQueryResponse)
def query_endpoint(request: RAGQueryRequest):
    try:
        response = rag_service.answer_question(request.question, top_k=request.top_k)
        return response
    except Exception as e:
        raise HTTPException(status_status=500, detail=str(e))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ejecutar el servidor Nubbix Assist RAG.")
    parser.add_argument("--cli", action="store_true", help="Ejecutar en modo interactivo CLI")
    args = parser.parse_args()

    if args.cli:
        service = RAGService(collection_name="nubbix_docs_structural")
        print("\n=== Nubbix Assist - CLI Mode (Escribe 'salir' para finalizar) ===")
        while True:
            q = input("\nPregunta: ")
            if q.lower() in ["salir", "exit", "quit"]:
                break
            res = service.answer_question(q)
            print(f"\nRespuesta:\n{res.system_answer}\n")
            print("Fuentes citadas:")
            for c in res.chunks_related:
                print(f"- [{c.chunk_id}] ({c.source}) Score: {c.score}")
    else:
        uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)