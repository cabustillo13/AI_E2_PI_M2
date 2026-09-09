# Guía de migración a pgvector

Para poder probarlo se requiere de Docker y DBeaver.

## Paso 1: Levantar PostgreSQL con pgvector

Para utilizar `pgvector`, la instancia de PostgreSQL debe tener la extensión instalada. La forma más rápida y limpia de probarlo localmente es usando Docker.

Ejecuta en tu terminal (PowerShell o CMD):

```bash
docker run --name postgres-pgvector -e POSTGRES_PASSWORD=postgres -p 5432:5432 -d pgvector/pgvector:pg16
```

---

## Paso 2: Conectar DBeaver a PostgreSQL

1. Abre **DBeaver**.
2. Ve al menú superior y selecciona **Database** > **New Database Connection** (o presiona `Alt + Shift + N`).
3. Selecciona **PostgreSQL** de la lista y haz clic en **Next**.
4. Completa los parámetros de conexión:
* **Host:** `localhost`
* **Port:** `5432`
* **Database:** `postgres`
* **Username:** `postgres`
* **Password:** `postgres`


5. Haz clic en el botón **Test Connection**. Si DBeaver te pide descargar los controladores JDBC de PostgreSQL, acepta la descarga automática.
6. Una vez que la prueba sea exitosa, haz clic en **Finish**.

---

## Paso 3: Abrir un Editor SQL

1. En el panel izquierdo (**Database Navigator**), despliega la conexión que acabas de crear.
2. Haz clic derecho sobre la base de datos `postgres`.
3. Selecciona **SQL Editor** > **Open SQL Script** (o presiona `F3`).

---

## Paso 4: Habilitar la Extensión y Crear la Tabla

Copia el siguiente bloque en el editor SQL de DBeaver y ejecútalo completamente (presiona `Alt + X` o el botón de *Execute Script*):

```sql
-- 1. Activar la extensión pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Crear la tabla de chunks con columna vector de 1536 dimensiones (para OpenAI text-embedding-3-small)
CREATE TABLE document_chunks (
    id VARCHAR(100) PRIMARY KEY,
    source_doc VARCHAR(255) NOT NULL,
    header VARCHAR(255),
    strategy VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Crear el índice HNSW para acelerar la búsqueda vectorial
CREATE INDEX idx_document_chunks_embedding 
ON document_chunks 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

```

> **Verificación:** Si expandes la tabla `document_chunks` en el panel izquierdo de DBeaver, verás la columna `embedding` con el tipo `vector`.

---

### Paso 5: Insertar Datos de Prueba (Mock Vectors)

Como la columna requiere exactamente 1536 dimensiones, puedes simular una inserción en SQL generando un vector de prueba directamente en el script:

```sql
-- Insertar un chunk de prueba con un vector dummy de 1536 dimensiones
INSERT INTO document_chunks (id, source_doc, header, strategy, content, embedding)
VALUES (
    'hr_policies_struct_0',
    'hr_policies.md',
    'Vacaciones',
    'structural',
    'Los empleados tienen derecho a 14 días corridos de vacaciones tras cumplir 1 año.',
    (SELECT array_agg(0.01)::vector FROM generate_series(1, 1536))
);

INSERT INTO document_chunks (id, source_doc, header, strategy, content, embedding)
VALUES (
    'it_manual_struct_1',
    'it_manual.md',
    'VPN y Accesos',
    'structural',
    'Es obligatorio el uso de la VPN de Nubbix al conectarse desde redes públicas.',
    (SELECT array_agg(0.05)::vector FROM generate_series(1, 1536))
);

```

Selecciona el bloque y ejecútalo (`Alt + X`).

---

### Paso 6: Ejecutar la Consulta de Similitud por Coseno

Prueba la búsqueda vectorial utilizando el operador de distancia coseno (`<=>`):

```sql
-- Consulta que simula la búsqueda de un vector query contra la base
SELECT 
    id, 
    source_doc, 
    header, 
    content, 
    1 - (embedding <=> (SELECT array_agg(0.01)::vector FROM generate_series(1, 1536))) AS similarity
FROM document_chunks
WHERE strategy = 'structural'
ORDER BY embedding <=> (SELECT array_agg(0.01)::vector FROM generate_series(1, 1536))
LIMIT 3;

```

### Resultado Esperado en DBeaver

En la grilla de resultados inferior verás las columnas `id`, `source_doc`, `header`, `content` y la métrica de similitud calculada (`similarity`), ordenadas por el fragmento más cercano vectorialmente.

| id                     | source_doc       | header        | content                                                                           | similarity |
| ---------------------- | ---------------- | ------------- | --------------------------------------------------------------------------------- | ---------: |
| `hr_policies_struct_0` | `hr_policies.md` | Vacaciones    | Los empleados tienen derecho a 14 días corridos de vacaciones tras cumplir 1 año. |        1.0 |
| `it_manual_struct_1`   | `it_manual.md`   | VPN y Accesos | Es obligatorio el uso de la VPN de Nubbix al conectarse desde redes públicas.     |        1.0 |
