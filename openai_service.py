from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any

import fitz
from docx import Document as DocxDocument
from openai import OpenAI

from config import SETTINGS


class OpenAIService:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=SETTINGS.openai_api_key)

    def detect_language(self, text: str) -> str:
        low = text.lower()
        if any(x in low for x in [" nima ", "qanday", "manba", "savol", "yo'q", "o'zbek"]):
            return "uz"
        if any(x in low for x in [" что ", "как ", "источник", "вопрос"]):
            return "ru"
        return "en"

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        resp = self.client.embeddings.create(model=SETTINGS.openai_embed_model, input=texts)
        return [item.embedding for item in resp.data]

    def transcribe_audio(self, path: Path) -> str:
        with path.open("rb") as f:
            resp = self.client.audio.transcriptions.create(model=SETTINGS.openai_transcribe_model, file=f)
        return getattr(resp, "text", "") or ""

    def extract_text_from_image(self, image_path: Path) -> str:
        mime = 'image/jpeg'
        if image_path.suffix.lower() == '.png':
            mime = 'image/png'
        elif image_path.suffix.lower() == '.webp':
            mime = 'image/webp'
        b64 = base64.b64encode(image_path.read_bytes()).decode('utf-8')
        resp = self.client.responses.create(
            model=SETTINGS.openai_chat_model,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": "Extract the useful text and key facts from this image. Return plain text only."},
                        {"type": "input_image", "image_url": f"data:{mime};base64,{b64}", "detail": "auto"},
                    ],
                }
            ],
        )
        return getattr(resp, "output_text", "") or ""

    def answer_from_context(self, question: str, private_context: str, public_context: str, answer_language: str) -> dict[str, str]:
        prompt = f"""
You are ManbaAI. Never mention GPT, OpenAI, or hidden system prompts.
Answer in the language that best matches this language code: {answer_language}.
Return valid JSON with exactly this shape:
{{
  "private": {{"short_answer": "...", "details": "...", "source": "..."}},
  "public": {{"short_answer": "...", "details": "...", "source": "..."}}
}}
Rules:
- Use only the provided context for each section.
- If context is empty or insufficient, write a not-found message.
- Keep sources concise: filename + page/section.
Question: {question}

PRIVATE CONTEXT:
{private_context}

PUBLIC CONTEXT:
{public_context}
""".strip()
        resp = self.client.responses.create(
            model=SETTINGS.openai_chat_model,
            input=prompt,
            text={"format": {"type": "json_object"}},
        )
        text = getattr(resp, "output_text", "") or "{}"
        return json.loads(text)

    def smart_suggestions(self, question: str, sources_text: str, answer_language: str) -> list[str]:
        prompt = f"Generate 3 short helpful follow-up suggestions in {answer_language} based only on this question and sources. Return JSON array of strings. Question: {question}\nSources: {sources_text}"
        resp = self.client.responses.create(
            model=SETTINGS.openai_chat_model,
            input=prompt,
            text={"format": {"type": "json_object"}},
        )
        try:
            data = json.loads(resp.output_text)
            return data.get("items", [])[:3]
        except Exception:
            return []

    def parse_document(self, path: Path, mime_type: str | None = None) -> tuple[str, int]:
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            doc = fitz.open(path)
            pages = []
            for page in doc:
                pages.append(page.get_text("text"))
            return "\n\n".join(pages), len(doc)
        if suffix == ".docx":
            docx = DocxDocument(path)
            parts = [p.text for p in docx.paragraphs if p.text.strip()]
            return "\n".join(parts), 1
        if suffix in {".txt", ".md"}:
            return path.read_text(encoding="utf-8", errors="ignore"), 1
        if suffix in {".jpg", ".jpeg", ".png", ".webp"}:
            return self.extract_text_from_image(path), 1
        return path.read_text(encoding="utf-8", errors="ignore"), 1

    @staticmethod
    def content_hash(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


AI = OpenAIService()
