import re
from typing import List, Dict, Any


class BaseChunker:
    """Clase base para estrategias de chunking."""
    def chunk_text(self, text: str, source_doc: str) -> List[Dict[str, Any]]:
        raise NotImplementedError


class FixedSizeChunker(BaseChunker):
    """Estrategia A: Chunking por tamaño fijo de palabras con overlap."""
    def __init__(self, chunk_size: int = 45, overlap: int = 10):
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
    """Estrategia B: Chunking estructural guiado por encabezados de Markdown y párrafos."""
    def __init__(self, max_words_per_chunk: int = 40):
        self.max_words_per_chunk = max_words_per_chunk

    def chunk_text(self, text: str, source_doc: str) -> List[Dict[str, Any]]:
        sections = re.split(r'\n(?=#{1,3}\s+)', text)
        chunks = []
        chunk_idx = 0

        for section in sections:
            section_str = section.strip()
            if not section_str:
                continue
            
            lines = section_str.split("\n")
            header = lines[0] if lines[0].startswith("#") else f"# {source_doc}"
            body = "\n".join(lines[1:]).strip() if lines[0].startswith("#") else section_str

            if not body:
                chunks.append({
                    "chunk_id": f"{source_doc}_struct_{chunk_idx}",
                    "content": section_str,
                    "metadata": {
                        "source": source_doc,
                        "header": header.replace("#", "").strip(),
                        "strategy": "structural",
                        "chunk_index": chunk_idx
                    }
                })
                chunk_idx += 1
                continue

            paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]

            if len(body.split()) > self.max_words_per_chunk and len(paragraphs) > 1:
                for para in paragraphs:
                    chunks.append({
                        "chunk_id": f"{source_doc}_struct_{chunk_idx}",
                        "content": f"{header}\n\n{para}",
                        "metadata": {
                            "source": source_doc,
                            "header": header.replace("#", "").strip(),
                            "strategy": "structural",
                            "chunk_index": chunk_idx
                        }
                    })
                    chunk_idx += 1
            else:
                chunks.append({
                    "chunk_id": f"{source_doc}_struct_{chunk_idx}",
                    "content": section_str,
                    "metadata": {
                        "source": source_doc,
                        "header": header.replace("#", "").strip(),
                        "strategy": "structural",
                        "chunk_index": chunk_idx
                    }
                })
                chunk_idx += 1

        return chunks