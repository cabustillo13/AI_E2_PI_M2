import hashlib
from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv

from src.models import TicketRequest, TicketResponse
from src.service import process_ticket
from src.llm_client import LLMProvider


# Cargar variables de entorno (.env)
load_dotenv()

app = FastAPI(title="Nubbix AI Triage Service")
provider = LLMProvider(provider_name="openai") # Cambiar a "anthropic" para probar el otro proveedor

# Memoria caché básica (Extra Credit)
response_cache = {}

def get_cache_key(text: str) -> str:
    return hashlib.md5(text.lower().strip().encode()).hexdigest()


@app.post("/api/triage", response_model=TicketResponse)
async def triage_endpoint(request: TicketRequest):
    try:
        cache_key = get_cache_key(request.ticket)
        
        # EXTRA CREDIT: Caché de respuestas
        if cache_key in response_cache:
            # Retorna instantáneamente sin costo LLM
            return response_cache[cache_key]

        # Procesar con el LLM
        response = process_ticket(request, provider)
        
        # Guardar en caché
        response_cache[cache_key] = response
        
        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)