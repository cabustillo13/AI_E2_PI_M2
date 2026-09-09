# Nubbix Assist: Asistente de Conocimiento Interno (RAG)

Nubbix Assist es un chatbot de respuestas sobre documentación oficial corporativa (Políticas de HR, Manual de IT y Procesos Financieros) construido sobre un pipeline RAG (Retrieval-Augmented Generation) con búsqueda híbrida y citas navegables.

---

## Arquitectura y Decisiones Técnicas

- **Ingesta Reproducible**: Un pipeline modular que lee los Markdown en `/data/corpus`, aplica el parser de chunking configurado, obtiene embeddings vía OpenAI (`text-embedding-3-small`) e indexa en ChromaDB local.

- **Rechazo Honesto (Out-of-Scope Handling)**: Mediante instrucciones estrictas en el prompt del sistema (`prompts/rag_v1.yaml`), si la pregunta no se fundamenta en los chunks recuperados o está fuera del ámbito corporativo, el modelo responde con un rechazo explícito medido en las evals.

- **LLM-as-a-Judge**: La groundedness se evalúa de manera automatizada utilizando un prompt evaluador (`prompts/judge_v1.yaml`) que compara la coherencia entre el contexto recuperado y la respuesta generada.

---

## Estructura del Repositorio

```text
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
├── data/
│   └── corpus/
│       ├── hr_policies.md
│       ├── it_manual.md
│       └── finance_processes.md
├── ingest/
│   ├── chunking.py
│   └── ingest.py
├── prompts/
│   ├── rag_v1.yaml
│   └── judge_v1.yaml
├── evals/
│   ├── dataset.jsonl
│   └── runner.py
└── src/
    ├── __init__.py
    ├── llm_client.py
    ├── metrics.py
    ├── models.py
    ├── vector_store.py
    ├── hybrid_retriever.py
    ├── service.py
    └── main.py
```

---

## Instalación y Configuración

### 1. Crear entorno virtual

```bash
python -m venv venv

# En Windows (PowerShell):
venv\Scripts\activate
# En Linux/macOS:
source venv/bin/activate
```

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 3. Configurar variables de entorno

Copia el archivo `.env.example` como `.env` y asigna tus claves API:

```bash
cp .env.example .env
```

Contenido del `.env`:

```env
OPENAI_API_KEY=sk-proj-...
EMBEDDING_MODEL=text-embedding-3-small
CHROMA_PERSIST_DIR=./data/chroma_db
```

---

## Ingesta de Documentos y Evaluaciones

### 1. Ingesta de Datos Reproducible

La ingesta es totalmente reproducible y permite alternar entre las dos estrategias de chunking:

```bash
# Ingesta con estrategia estructural por headers (Recomendada)
python -m ingest.ingest --strategy structural

# Ingesta con estrategia de tamaño fijo
python -m ingest.ingest --strategy fixed
```

### 2. Ejecutar la Suite de Evaluaciones

```bash
# Evaluación de la estrategia estructural
python -m evals.runner --strategy structural

# Evaluación de la estrategia de tamaño fijo
python -m evals.runner --strategy fixed
```

---

## Comparación de Estrategias de Chunking

Se evaluaron dos estrategias de procesamiento sobre el mismo corpus original utilizando la suite de evaluaciones (`evals/runner.py`) sobre 28 casos de prueba:

- **Fixed Size Chunking (Estrategia A)**: División por bloques fijos de 35 palabras con 8 palabras de overlap.
- **Header Structural Chunking (Estrategia B)**: División basada en la estructura de encabezados Markdown (`#`, `##`) combinada con fragmentación por bloques de párrafos/listas.

| Métrica | Fixed Size (Estrategia A) | Header Structural (Estrategia B) |
| :--- | :---: | :---: |
| **Total Chunks Generados** | **24** | **23** |
| **Precision@k** | **0.7273** | 0.0909 |
| **Recall@k** | **1.0000** | 0.2727 |
| **Hit Rate** | **1.0000** | 0.2727 |
| **Groundedness Score** | **1.0000** | **1.0000** |
| **Refusal Accuracy** | **1.0000** | **1.0000** |

### Justificación de Resultados y Decisiones

- **Desempeño de Retrieval**: La Estrategia Fija (Estrategia A) alcanzó un **Hit Rate = 1.0000** y **Recall@k = 1.0000** al recuperar consistentemente el contexto correcto por documento fuente. En la Estrategia Estructural (Estrategia B), la subdivisión fina por listas y párrafos atomizó el contenido, distribuyendo la información en chunks más reducidos que requieren un `top_k` mayor o re-ranking para concentrar todas las citas exactas.

- **Fidelidad y Rechazo Honesto**: Ambas estrategias obtuvieron un **Groundedness Score de 1.0000** y un **Refusal Accuracy de 1.0000**. Esto confirma que el prompt del sistema (`prompts/rag_v1.yaml`) restringe la generación estrictamente al contexto recuperado, evitando alucinaciones y rechazando con precisión las consultas fuera de alcance (*out-of-scope*).

- **Búsqueda Híbrida (BM25 + Vectorial)**: La integración de búsqueda léxica y vectorial mediante Reciprocal Rank Fusion (RRF) garantizó la localización de términos exactos (como canales de Slack o correos de soporte) así como coincidencias semánticas.

---

## Ejecución del Servicio

Para iniciar el servidor de desarrollo FastAPI o la CLI interactiva:

```bash
# Modo API REST (FastAPI)
python -m src.main

# Modo Interactivo CLI
python -m src.main --cli
```

El servicio estará disponible en `http://localhost:8000`. La documentación interactiva Swagger se encuentra en `http://localhost:8000/docs`.

### Ejemplo de Petición HTTP (`curl`)

```bash
curl -X 'POST' \
  'http://localhost:8000/api/v1/query' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "question": "¿A quién debo avisar si pierdo mi MacBook de la empresa?",
  "top_k": 3,
  "enable_rerank": false
}'
```

### Respuesta del Servicio (Contrato JSON Validado)

```json
{
  "user_question": "¿A quién debo avisar si pierdo mi MacBook de la empresa?",
  "system_answer": "Si pierdes tu MacBook de la empresa, debes notificar inmediatamente al canal de Slack #it-ops y enviar un email a it@nubbix.com. Además, si se trata de un robo fuera del domicilio, es necesario presentar la denuncia policial correspondiente dentro de las 48 horas [it_manual.md_struct_2].",
  "chunks_related": [
    {
      "chunk_id": "it_manual.md_struct_2",
      "source": "it_manual.md",
      "header": "Equipos de Trabajo y Hardware",
      "content": "## Equipos de Trabajo y Hardware\nA cada nuevo integrante se le asigna una MacBook Pro M2/M3 o un Dell XPS de gama alta con 32GB RAM.\nLa renovación de equipos de cómputo se realiza cada 3 años.\nEn caso de pérdida, robo o daño grave del equipo corporativo, el colaborador debe:\n1. Notificar inmediatamente al canal de Slack #it-ops y enviar un email a it@nubbix.com.\n2. Presentar la denuncia policial correspondiente dentro de las 48 horas en caso de robo fuera del domicilio.",
      "score": 0.0328
    },
    {
      "chunk_id": "it_manual.md_struct_3",
      "source": "it_manual.md",
      "header": "Políticas de Contraseñas y MFA",
      "content": "## Políticas de Contraseñas y MFA\nTodos los colaboradores deben activar Autenticación de Dos Factores (MFA) vía aplicación Google Authenticator o 1Password en todas las cuentas corporativas.\nLas contraseñas de Google Workspace expiran cada 90 días y deben poseer un mínimo de 16 caracteres.\nEstá estrictamente prohibido compartir credenciales corporativas a través de Slack o correo electrónico.",
      "score": 0.0313
    },
    {
      "chunk_id": "it_manual.md_struct_1",
      "source": "it_manual.md",
      "header": "Solicitud de Accesos y Permisos",
      "content": "## Solicitud de Accesos y Permisos\nLos accesos a sistemas (GitHub, AWS, VPN, GCP, Jira) deben solicitarse mediante ticket en la mesa de ayuda de IT.\nEl tiempo estándar de resolución para permisos de lectura es de 4 horas hábiles. Accesos con permisos de Administrador o Producción requieren doble aprobación: el Tech Lead del equipo y el CISO de Nubbix.",
      "score": 0.0313
    }
  ],
  "latency_seconds": 1.784,
  "estimated_cost_usd": 0.000125
}
```

---

## (EXTRA) Guía de Migración a pgvector

Dejo documentado el paso a paso para hacerlo en [docs/guia_migracion_pgvector.md](docs/guia_migracion_pgvector.md).