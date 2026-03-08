from __future__ import annotations

import json
import math
from typing import Any

from db import DB
from services.openai_service import AI


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if not na or not nb:
        return 0.0
    return dot / (na * nb)


def search_scope(telegram_user_id: int, scope: str, question: str, top_k: int = 4) -> dict[str, Any]:
    docs = DB.list_documents_for_search(telegram_user_id, scope)
    doc_ids = [int(doc["id"]) for doc in docs]
    chunks = DB.list_chunks_for_document_ids(doc_ids)
    if not chunks:
        return {"context": "", "source": "topilmadi", "matches": []}

    q_emb = AI.embed_texts([question])[0]
    scored = []
    for chunk in chunks:
        emb = json.loads(chunk["embedding_json"]) if chunk["embedding_json"] else []
        score = cosine_similarity(q_emb, emb)
        if score > 0.15:
            scored.append((score, chunk))
    scored.sort(key=lambda x: x[0], reverse=True)
    selected = scored[:top_k]
    if not selected:
        return {"context": "", "source": "topilmadi", "matches": []}

    context_parts = []
    source_parts = []
    for _, chunk in selected:
        section = chunk["source_page"] or chunk["source_section"] or "chunk"
        context_parts.append(f"FILE: {chunk['file_name']} | PLACE: {section}\n{chunk['chunk_text']}")
        source_parts.append(f"{chunk['file_name']} — {section}")
    return {
        "context": "\n\n".join(context_parts),
        "source": "; ".join(dict.fromkeys(source_parts)),
        "matches": selected,
    }
