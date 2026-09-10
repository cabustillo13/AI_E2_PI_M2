import re
from typing import List, Dict, Any


class BaseChunker:
    """Clase base para estrategias de chunking."""
    def chunk_text(self, text: str, source_doc: str) -> List[Dict[str, Any]]:
        raise NotImplementedError


class FixedSizeChunker(BaseChunker):
    """Estrategia A: Chunking por tamaño fijo de palabras con overlap."""
    def __init__(self, chunk_size: int = 35, overlap: int = 8):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk_text(self, text: str, source_doc: str) -> List[Dict[str, Any]]:
        words = text.split()
        chunks = []
        start = 0
        chunk_idx = 0

        while start < len(words):
            end = start + self.chunk_size
            chunk_words = words[start:end]
            chunk_content = " ".join(chunk_words)
            
            chunks.append({
                "chunk_id": f"{source_doc}_fixed_{chunk_idx}",
                "content": chunk_content,
                "metadata": {
                    "source": source_doc,
                    "strategy": "fixed",
                    "word_count": len(chunk_words),
                    "chunk_index": chunk_idx
                }
            })
            chunk_idx += 1
            start += (self.chunk_size - self.overlap)
            if start >= len(words) and len(chunk_words) < self.chunk_size:
                break
        return chunks


class HeaderStructuralChunker(BaseChunker):
    """
    Estrategia B: Chunking estructural guiado por encabezados (H2).

    Cada sección de nivel 2 ("## ...") se mantiene como UNA unidad semántica
    completa (header + cuerpo), en lugar de partirse por cada párrafo o ítem
    de lista. Esto evita la sobre-fragmentación (chunks de una sola línea sin
    contexto) que tenía la versión anterior del chunker.

    Si el cuerpo de una sección supera `max_section_words`, recién ahí se
    subdivide en sub-chunks balanceados agrupando bloques (párrafos/ítems),
    repitiendo el header en cada sub-chunk para no perder el contexto de a
    qué sección pertenece.

    El título H1 del documento (preámbulo antes del primer "##") no genera
    un chunk propio: no aporta información consultable por sí solo.
    """

    def __init__(self, max_section_words: int = 55):
        self.max_section_words = max_section_words

    def chunk_text(self, text: str, source_doc: str) -> List[Dict[str, Any]]:
        # Se secciona únicamente por headers H2 ("## "); el H1 queda como preámbulo descartable
        sections = re.split(r'\n(?=##\s+)', text)
        chunks: List[Dict[str, Any]] = []
        chunk_idx = 0

        for section in sections:
            section_str = section.strip()
            if not section_str or not section_str.startswith("##"):
                # Preámbulo (título H1 del documento): no se indexa como chunk
                continue

            lines = section_str.split("\n")
            header = lines[0]
            body = "\n".join(lines[1:]).strip()
            header_clean = header.replace("#", "").strip()

            if not body:
                continue

            word_count = len(body.split())

            if word_count <= self.max_section_words:
                content = f"{header}\n{body}"
                chunks.append(self._make_chunk(source_doc, chunk_idx, header_clean, content))
                chunk_idx += 1
                continue

            # Sección larga: subdividir agrupando bloques (párrafos / ítems de lista)
            blocks = [p.strip() for p in re.split(r'\n\n|\n(?=\d+\.|\-|\*)', body) if p.strip()]
            batches = self._batch_blocks(blocks, self.max_section_words)

            for batch in batches:
                content = f"{header}\n{batch}"
                chunks.append(self._make_chunk(source_doc, chunk_idx, header_clean, content))
                chunk_idx += 1

        return chunks

    def _batch_blocks(self, blocks: List[str], max_words: int) -> List[str]:
        """Agrupa bloques consecutivos de una sección hasta acercarse a max_words por sub-chunk."""
        batches = []
        current: List[str] = []
        current_words = 0

        for block in blocks:
            block_words = len(block.split())
            if current and current_words + block_words > max_words:
                batches.append("\n".join(current))
                current, current_words = [], 0
            current.append(block)
            current_words += block_words

        if current:
            batches.append("\n".join(current))

        return batches

    def _make_chunk(self, source_doc: str, chunk_idx: int, header_clean: str, content: str) -> Dict[str, Any]:
        return {
            "chunk_id": f"{source_doc}_struct_{chunk_idx}",
            "content": content,
            "metadata": {
                "source": source_doc,
                "header": header_clean,
                "strategy": "structural",
                "chunk_index": chunk_idx
            }
        }