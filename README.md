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

Si se desea habilitar el rerunk o hacer debugging de los resultados, adicionar los argumentos: `--rerank` y `--debug`.

```bash
# Evaluación de la estrategia estructural con rerank y debugging
python -m evals.runner --strategy structural --rerank --debug

# Evaluación de la estrategia de tamaño fijo con rerank y debugging
python -m evals.runner --strategy fixed --rerank --debug
```

---

## Comparación de Estrategias de Chunking

Se evaluaron dos estrategias sobre el mismo corpus (39 preguntas del golden dataset,
incluyendo 6 cross-documento y 7 hard negatives), con la MISMA fórmula de
precision/recall/hit-rate/MRR para ambas (ver `evals/runner.py`):

| Métrica                     | Structural (headers) | Fixed (35 palabras) |
|------------------------------|:---------------------:|:--------------------:|
| Chunks generados             | 21                    | 51                   |
| Precision@3                  | 0.3871                | 0.3226               |
| Recall@3                     | **0.9677**            | 0.7742               |
| Hit rate                     | **0.9677**            | 0.871                |
| MRR                          | **0.914**             | 0.7473               |
| Cross-document full hit rate | **1.0**               | 0.1667               |
| Hard-negative leakage rate   | 0.5714                | **0.2857**           |

**Decisión:** se adopta **chunking estructural por headers** como estrategia default.
Recall, hit-rate, MRR y sobre todo cross-document full hit rate (1.0 vs 0.17) son
sustancialmente mejores: los chunks de sección completa preservan el contexto necesario
para resolver preguntas que combinan dos políticas, mientras que el chunking de tamaño
fijo fragmenta la información a mitad de una idea con más frecuencia.

La única métrica donde fixed gana es hard-negative leakage (0.29 vs 0.57): al ser chunks
más chicos y granulares, hay menos superposición temática entre secciones vecinas, así
que un distractor tiene menos chance de colarse. Es un trade-off documentado, no una
razón para cambiar de estrategia (el costo de recall perdido es mayor que el beneficio).

## Retrieval Avanzado: Re-ranking con Cross-Encoder (extra credit)

Se implementó re-ranking opcional con `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`
(multilingüe) detrás del flag `enable_rerank`, midiendo el delta contra el pipeline sin
rerank:

| Métrica                   | Structural OFF | Structural ON | Fixed OFF | Fixed ON |
|-----------------------------|:--------------:|:-------------:|:---------:|:--------:|
| Recall@3                    | 0.9677         | 0.9677        | 0.7742    | 0.9032   |
| MRR                          | 0.914          | 0.9355        | 0.7473    | 0.8602   |
| Hard-negative leakage rate   | 0.5714         | 0.5714        | 0.2857    | 0.4286   |

**Decisión:** el rerank NO entra al alcance mínimo por defecto. Con la estrategia
recomendada (structural) el corpus ya es lo bastante chico como para que la búsqueda
híbrida sature el hit-rate/recall; el rerank solo mueve el MRR levemente (+2.4%
relativo) sin justificar el costo de latencia y la dependencia adicional. Con fixed sí
mejora recall y MRR de forma notoria, pero a costa de aumentar en +50% relativo la
contaminación por hard negatives (el pool más amplio que necesita el cross-encoder para
poder reordenar también le da más chances al distractor de entrar en el top-k). Queda
implementado y medido como extra credit, activable con `--rerank` / `enable_rerank=true`.

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