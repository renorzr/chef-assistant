import hashlib
import json
import math
import os
import re
from typing import List
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from config import load_env_file

load_env_file()


class EmbeddingProviderError(Exception):
    pass


class BaseEmbeddingProvider:
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError


class OpenAICompatibleEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(self, base_url: str, api_key: str, model: str, timeout_seconds: float = 20.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        payload = {
            "model": self.model,
            "input": texts,
        }
        data = json.dumps(payload).encode("utf-8")
        req = Request(
            url=f"{self.base_url}/embeddings",
            data=data,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )

        try:
            with urlopen(req, timeout=self.timeout_seconds) as resp:
                body = resp.read().decode("utf-8", errors="ignore")
        except HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="ignore")
            raise EmbeddingProviderError(
                f"Embedding HTTP error {exc.code}: {err_body[:300]}"
            ) from exc
        except URLError as exc:
            raise EmbeddingProviderError(f"Embedding network error: {exc}") from exc
        except Exception as exc:
            raise EmbeddingProviderError(f"Embedding request failed: {exc}") from exc

        try:
            parsed = json.loads(body)
            rows = parsed.get("data", [])
            rows = sorted(rows, key=lambda x: x.get("index", 0))
            vectors = [row["embedding"] for row in rows]
        except Exception as exc:
            raise EmbeddingProviderError("Embedding response parse failed.") from exc

        if len(vectors) != len(texts):
            raise EmbeddingProviderError(
                f"Embedding count mismatch, expected {len(texts)}, got {len(vectors)}."
            )

        return vectors


class LocalHashEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(self, dim: int = 256):
        self.dim = dim

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r"[a-z0-9\u4e00-\u9fff]+", (text or "").lower())

    def _hash_to_index(self, token: str) -> int:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        return int.from_bytes(digest[:8], byteorder="big", signed=False) % self.dim

    def _embed_one(self, text: str) -> List[float]:
        vec = [0.0] * self.dim
        tokens = self._tokenize(text)
        for token in tokens:
            vec[self._hash_to_index(token)] += 1.0

        norm = math.sqrt(sum(v * v for v in vec))
        if norm == 0:
            return vec
        return [v / norm for v in vec]

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        return [self._embed_one(t) for t in texts]


_provider: BaseEmbeddingProvider | None = None


def get_embedding_provider() -> BaseEmbeddingProvider:
    global _provider
    if _provider is not None:
        return _provider

    provider_name = os.getenv("EMBEDDING_PROVIDER", "openai_compatible").strip().lower()

    if provider_name == "local_hash":
        dim = int(os.getenv("EMBEDDING_DIM", "256"))
        _provider = LocalHashEmbeddingProvider(dim=dim)
        return _provider

    if provider_name == "openai_compatible":
        base_url = os.getenv("EMBEDDING_BASE_URL", "").strip()
        api_key = os.getenv("EMBEDDING_API_KEY", "").strip()
        model = os.getenv("EMBEDDING_MODEL", "").strip()
        timeout_seconds = float(os.getenv("EMBEDDING_TIMEOUT_SECONDS", "20"))

        if not base_url:
            raise EmbeddingProviderError("Missing EMBEDDING_BASE_URL.")
        if not api_key:
            raise EmbeddingProviderError("Missing EMBEDDING_API_KEY.")
        if not model:
            raise EmbeddingProviderError("Missing EMBEDDING_MODEL.")

        _provider = OpenAICompatibleEmbeddingProvider(
            base_url=base_url,
            api_key=api_key,
            model=model,
            timeout_seconds=timeout_seconds,
        )
        return _provider

    raise EmbeddingProviderError(
        f"Unsupported EMBEDDING_PROVIDER '{provider_name}'. Use 'openai_compatible' or 'local_hash'."
    )
