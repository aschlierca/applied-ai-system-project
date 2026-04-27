from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

from logger_config import setup_logger

logger = setup_logger("rag.retriever")

_DOCS_DIR = Path(__file__).parent / "documents"


class Retriever:
    """
    Simple keyword-overlap retriever for the PawPal+ pet care knowledge base.

    Documents in rag/documents/*.txt are split into paragraph-level chunks at
    load time.  Retrieval scores each chunk by counting how many unique query
    tokens appear in it (frequency-weighted), then returns the top-k results.
    No external ML libraries are required.
    """

    def __init__(self, docs_dir: Optional[Path] = None) -> None:
        self.docs_dir = docs_dir or _DOCS_DIR
        self.chunks: List[Dict[str, str]] = []
        self._load_documents()
        logger.info(
            "Retriever ready: %d chunks from %d document(s)",
            len(self.chunks),
            len(sorted(self.docs_dir.glob("*.txt"))),
        )

    # ── document loading ───────────────────────────────────────────────────────

    def _load_documents(self) -> None:
        for path in sorted(self.docs_dir.glob("*.txt")):
            try:
                text = path.read_text(encoding="utf-8")
            except OSError as exc:
                logger.warning("Could not read %s: %s", path, exc)
                continue
            for para in re.split(r"\n{2,}", text):
                para = para.strip()
                if len(para) >= 80:
                    self.chunks.append({"source": path.stem, "text": para})
        logger.debug("Loaded %d total chunks", len(self.chunks))

    # ── scoring ────────────────────────────────────────────────────────────────

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return re.findall(r"\b[a-z]{3,}\b", text.lower())

    def _score(self, query_tokens: List[str], chunk_text: str) -> float:
        counts = Counter(self._tokenize(chunk_text))
        return float(sum(counts.get(tok, 0) for tok in set(query_tokens)))

    # ── public API ─────────────────────────────────────────────────────────────

    def retrieve(self, query: str, top_k: int = 3) -> List[str]:
        """Return the *top_k* most relevant document chunks for *query*."""
        tokens = self._tokenize(query)
        if not tokens:
            logger.warning("Empty query passed to retriever; returning no chunks")
            return []

        scored = sorted(
            self.chunks,
            key=lambda c: self._score(tokens, c["text"]),
            reverse=True,
        )
        top = scored[:top_k]
        results = [
            f"[{c['source'].replace('_', ' ').title()}]\n{c['text']}" for c in top
        ]
        top_score = self._score(tokens, top[0]["text"]) if top else 0.0
        logger.info(
            "Retrieved %d chunks for query %r (top score: %.0f)",
            len(results),
            query[:50],
            top_score,
        )
        return results
