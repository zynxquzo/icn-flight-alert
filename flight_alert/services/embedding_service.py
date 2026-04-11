# flight_alert/services/embedding_service.py
"""OpenAI 임베딩 (text-embedding-3-small, 1536차원)"""

import logging
import os

from dotenv import load_dotenv
from openai import AsyncOpenAI, OpenAI

load_dotenv()

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"


def _api_key() -> str | None:
    return os.getenv("OPENAI_API_KEY")


async def generate_embedding(text: str) -> list[float]:
    """비동기 임베딩 생성."""
    key = _api_key()
    if not key:
        raise RuntimeError("OPENAI_API_KEY가 설정되지 않았습니다")
    client = AsyncOpenAI(api_key=key)
    text_clean = (text or "").strip()
    if not text_clean:
        text_clean = " "
    response = await client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text_clean,
    )
    return list(response.data[0].embedding)


def generate_embedding_sync(text: str) -> list[float]:
    """동기 임베딩 (스크립트·동기 컨텍스트용)."""
    key = _api_key()
    if not key:
        raise RuntimeError("OPENAI_API_KEY가 설정되지 않았습니다")
    client = OpenAI(api_key=key)
    text_clean = (text or "").strip()
    if not text_clean:
        text_clean = " "
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text_clean,
    )
    return list(response.data[0].embedding)
