# Nubbix AI Triage Service

Servicio de triaje automatizado para el soporte de primer nivel de Nubbix (SaaS de gestión para PyMEs en LATAM). El sistema clasifica automáticamente las consultas entrantes en texto libre, sugiere respuestas breves y determina acciones recomendadas para los agentes de soporte, garantizando salidas estructuradas, observabilidad de costos/latencia y protección contra usos maliciosos.

---

## Arquitectura y Decisiones Técnicas

* **Framework API:** FastAPI con validación estricta de datos mediante Pydantic v2.
* **Soporte Multi-proveedor:** Abstracción unificada mediante `LLMProvider` compatible con OpenAI (`gpt-4o-mini`, `gpt-4o`) y Anthropic (`claude-3-haiku-20240307`, `claude-3-5-sonnet`).
* **Salidas Estructuradas & Robustez:** Uso de *Structured Outputs* de OpenAI y *Tool Calling* de Anthropic. Incluye **Mecanismo de Retry Automático** (máximo 2 intentos) ante errores de llamada o parsing.
* **Versionado de Prompts:** Prompts almacenados de forma independiente en archivos YAML dentro de `/prompts`.
* **Guardrails de Seguridad:** 
  * *Entrada:* Detección heurística de patrones de Prompt Injection / Jailbreak + OpenAI Moderation API.
  * *Prompt-level:* Reglas defensivas e instrucciones de aislamiento de datos en el `system_prompt`.
* **Observabilidad & Métricas:** Log estructurado por request en `data/metrics.jsonl` (timestamp ISO-8601 UTC, preludio del ticket, categoría, latencia, tokens in/out y costo en USD).
* **Extra Credits Implementados:**
  * **Caché de Respuestas:** Almacenamiento en memoria mediante *hashes* MD5 del texto de consulta para retornos inmediatos a costo $0.
  * **LLM-as-Judge en Runtime:** Escalado condicional a modelos superiores (`gpt-4o` / `claude-3-5-sonnet`) cuando la primera respuesta devuelve un nivel de confianza bajo (`confidence: low`).

---

## Estructura del Repositorio

```text
├── data/                  # Logs de métricas (metrics.jsonl)
├── evals/                 # Suite de evals
│   ├── dataset.jsonl      # Dataset funcional (36 casos)
│   ├── adversarial.jsonl  # Dataset adversarial (15 casos)
│   ├── runner.py          # Runner de evals de exactitud y calidad
│   └── runner_security.py # Runner de pruebas de seguridad
├── prompts/               # Prompts versionados en YAML
│   ├── triage_v1.yaml
│   ├── triage_v2.yaml
│   ├── triage_v3.yaml     # Prompt utilizado en producción
│   └── judge_v1.yaml      # Prompt para LLM-as-Judge
├── src/                   # Código fuente de la aplicación
│   ├── main.py            # Servidor FastAPI y caché
│   ├── models.py          # Esquemas Pydantic
│   ├── service.py         # Lógica de triaje, retries y juez
│   ├── llm_client.py      # Cliente unificado OpenAI/Anthropic
│   └── metrics.py         # Registro de métricas operativas
├── .env.example           # Plantilla de variables de entorno
├── requirements.txt       # Dependencias del proyecto
└── README.md              # Documentación principal
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
ANTHROPIC_API_KEY=sk-ant-... # Opcional
```

---

## Ejecución del Servicio

Para iniciar el servidor de desarrollo FastAPI:

```bash
python -m src.main
```

El servicio estará disponible en `http://localhost:8000`. La documentación interactiva Swagger se encuentra en `http://localhost:8000/docs`.

### Ejemplo de Petición HTTP (`curl`)

```bash
curl -X POST "http://localhost:8000/api/triage" \
     -H "Content-Type: application/json" \
     -d '{
       "ticket": "Hola, me cobraron dos veces la suscripción de este mes, necesito un reintegro."
     }'
```

### Respuesta del Servicio (Contrato JSON Validado)

```json
{
  "category": "billing",
  "confidence": "high",
  "answer": "Puedo ayudarte a revisar el cobro duplicado de tu suscripción y gestionar la solicitud de reintegro.",
  "actions": [
    "Revisar el historial de pagos del cliente",
    "Verificar los cargos aplicados en la pasarela de pago",
    "Iniciar el proceso de reembolso si corresponde"
  ]
}
```

---

## Evaluación y Context Engineering

Se construyó una suite de evaluaciones automatizada (`evals/runner.py`) respaldada por un dataset etiquetado de **36 casos funcionales** (`evals/dataset.jsonl`).

```bash
python -m evals.runner
```

### Comparativa de Prompts Iterativos

| Versión Prompt | Técnica Aplicada | Exact Match (Categoría) | Score Calidad (Judge 1-5) | Justificación |
| --- | --- | --- | --- | --- |
| **`triage_v1`** | Zero-shot con instrucciones claras y concisas | **100.0% (36/36)** | **3.8 / 5.0** | Alta precisión y respuestas concisas y naturales. |
| **`triage_v2`** | Few-shot con ejemplos de demostración | **100.0% (36/36)** | 2.9 / 5.0 | Los ejemplos condicionaron al modelo a respuestas rígidas y cortas. |
| **`triage_v3`** | Zero-shot + Reglas de Seguridad Explicitadas | **97.2% (35/36)** | **3.2 / 5.0** | **Seleccionado para Producción:** Mantiene alta precisión incorporando barreras de seguridad. |

### Justificación de Elección

Se seleccionó **`triage_v3`** para el entorno productivo debido a que añade un bloque explícito de seguridad contra inyecciones e instrucciones maliciosas en el `system`, sacrificando marginalmente precisión en favor de resistencia adversarial.

---

## Suite de Pruebas de Seguridad (Adversarial Evals)

Se evaluó la resistencia del sistema contra **15 ataques adversariales** (Prompt Injections, Jailbreaks, Exfiltración de prompts) mediante `evals/runner_security.py`.

```bash
python -m evals.runner_security
```

### Resultados de Seguridad:

* **Filtro Preventivo en Entrada (Heurística + Moderación):** 10/15 ataques bloqueados antes de llamar al LLM (66.7%).
* **Protección en Capa de Prompt (`triage_v3` System Rules):** Los ataques restantes fueron contenidos por el prompt o clasificados de forma segura como `other`, evitando la exfiltración de instrucciones del sistema.
