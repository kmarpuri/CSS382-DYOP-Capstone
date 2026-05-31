"""Pluggable LLM backend.

``LLMBackend`` is the abstract interface; ``OllamaBackend`` is the
local default and ``GroqBackend`` is the hosted free-tier option
(used when the app is deployed to a public website). The backend is
intentionally minimal — it just exposes a single ``generate_json``
method — so MLX, vLLM, or other runtimes can be swapped in without
touching ``LLMReasoner``.

Two backends, two privacy postures:

* ``OllamaBackend.requires_redaction = False`` — all inference is
  local, so the full transcript object can be reasoned over.
* ``GroqBackend.requires_redaction = True`` — payload is sent to a
  hosted API, so ``LLMReasoner`` strips PII via
  :func:`capstone.llm.redact.redact_for_external` before building
  the prompt.
"""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class LLMBackend(ABC):
    """Abstract LLM backend."""

    # Hosted backends override this to True so the reasoner knows to
    # scrub PII out of the transcript before building the prompt.
    requires_redaction: bool = False

    # Human-readable name for the UI's privacy banner.
    provider_name: str = "local"

    @property
    @abstractmethod
    def model(self) -> str: ...

    @abstractmethod
    def generate_json(
        self,
        system: str,
        prompt: str,
        schema: dict[str, Any] | None = None,
        max_retries: int = 2,
    ) -> dict[str, Any]:
        """Generate a JSON response. Raises if no valid JSON after retries."""
        ...


class GroqBackend(LLMBackend):
    """Hosted backend backed by Groq's free-tier inference API.

    Defaults to ``llama-3.3-70b-versatile`` because:
      * It's free on Groq's developer tier.
      * It supports OpenAI-style JSON mode (``response_format``).
      * Sub-second inference makes the UI feel local.
      * Groq's free-tier TOS does not claim training rights on your data.

    The API key is read from the ``GROQ_API_KEY`` environment variable
    (or a ``.env`` file in the project root) — it must NEVER be
    committed to the repo.
    """

    requires_redaction = True
    provider_name = "Groq (hosted)"

    DEFAULT_MODEL = "llama-3.3-70b-versatile"

    def __init__(self, model: str | None = None, api_key: str | None = None):
        try:
            from groq import Groq  # noqa: F401
        except ImportError as e:
            raise RuntimeError(
                "groq Python client not installed. "
                "Run: pip install 'capstone[llm]'"
            ) from e

        self._api_key = api_key or os.environ.get("GROQ_API_KEY")
        if not self._api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Add it to your .env file or export "
                "it before running. Never commit the key to the repo."
            )

        self._model = (
            model
            or os.environ.get("CAPSTONE_LLM_MODEL")
            or self.DEFAULT_MODEL
        )

    @property
    def model(self) -> str:
        return self._model

    def generate_json(
        self,
        system: str,
        prompt: str,
        schema: dict[str, Any] | None = None,
        max_retries: int = 2,
    ) -> dict[str, Any]:
        from groq import Groq

        client = Groq(api_key=self._api_key)
        last_err: Exception | None = None

        # Groq's response_format=json_object validator requires the word
        # "json" to appear somewhere in the messages. The real reasoner
        # prompt already does, but for safety we append a marker so any
        # future caller can't accidentally trip the 400.
        json_marker = "" if "json" in (system + prompt).lower() else (
            "\n\n(Respond in JSON only.)"
        )

        # Groq honors the OpenAI-style response_format. The model is
        # instructed to emit JSON via the system prompt; response_format
        # rejects non-JSON output server-side.
        for attempt in range(max_retries + 1):
            try:
                resp = client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": system + json_marker},
                        {"role": "user", "content": prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1,
                    max_tokens=2048,
                )
                content = resp.choices[0].message.content
                if not content:
                    raise ValueError("Groq returned empty content")
                return json.loads(content)
            except json.JSONDecodeError as e:
                last_err = e
                logger.warning(
                    f"Groq returned non-JSON (attempt {attempt + 1}): {e}"
                )
                continue
            except Exception as e:
                last_err = e
                logger.warning(f"Groq call failed (attempt {attempt + 1}): {e}")
                continue

        raise RuntimeError(f"Groq failed to produce valid JSON: {last_err}")


class OllamaBackend(LLMBackend):
    """Ollama wrapper. Requires the ``ollama`` Python client and an
    Ollama daemon running locally.

    Privacy posture: ``requires_redaction = False`` — all inference is
    local, so the reasoner can pass the full transcript through.

    Model resolution order:
    1. Explicit ``model=`` argument.
    2. ``CAPSTONE_LLM_MODEL`` environment variable.
    3. Hardware-tier recommendation, *if* that model is installed locally.
    4. Any already-installed Ollama model (prefers chat-capable ones,
       skipping embedding models).

    This means the backend never fails just because the tier-recommended
    model hasn't been pulled — it falls back to whatever is on disk.
    """

    provider_name = "Ollama (local)"

    # Embedding-only models we should never use for chat / JSON output.
    _EMBEDDING_MODEL_HINTS = ("embed", "embedding", "bge", "nomic-embed")

    # Preference order when picking from already-installed models.
    # Items earlier in the list are preferred. Matched as substring of
    # the model name (e.g., "qwen3" matches "qwen3:30b-a3b").
    _PREFERRED_FAMILIES = (
        "qwen3", "gemma3", "phi4", "llama3.3", "llama3.2",
        "qwen2.5", "gemma2", "llama3", "mistral",
    )

    def __init__(self, model: str | None = None, host: str | None = None):
        try:
            import ollama  # noqa: F401
        except ImportError as e:
            raise RuntimeError(
                "ollama Python client not installed. "
                "Run: pip install 'capstone[llm]'"
            ) from e

        from capstone.llm.hardware import recommend_model

        self._host = host or os.environ.get("OLLAMA_HOST")

        explicit = model or os.environ.get("CAPSTONE_LLM_MODEL")
        chosen = explicit or recommend_model()

        installed = self._installed_models()
        if not self._is_installed(chosen, installed):
            fallback = self._pick_fallback(installed, exclude=chosen)
            if fallback:
                logger.warning(
                    "Ollama model %r is not installed. Falling back to %r. "
                    "Pull the preferred model with: ollama pull %s",
                    chosen, fallback, chosen,
                )
                chosen = fallback
            else:
                # No usable model installed — keep `chosen` so the eventual
                # 404 from Ollama produces a clear error including the
                # exact model name we tried.
                logger.warning(
                    "Ollama model %r is not installed and no fallback is "
                    "available. Pull a model first: ollama pull %s",
                    chosen, chosen,
                )

        self._model = chosen

    # ── installed-model helpers ────────────────────────────────────

    def _installed_models(self) -> list[str]:
        """Return the names of models currently installed in Ollama.

        Empty list if Ollama isn't running or the call fails — callers
        treat that as "fall through to the configured model".
        """
        try:
            import ollama
            client = ollama.Client(host=self._host) if self._host else ollama
            data = client.list()
        except Exception as e:
            logger.debug(f"Could not list Ollama models: {e}")
            return []

        # `data` may be a `ListResponse` (newer client) or a plain dict.
        models = getattr(data, "models", None)
        if models is None and isinstance(data, dict):
            models = data.get("models", [])
        names: list[str] = []
        for entry in models or []:
            name = getattr(entry, "model", None) or getattr(entry, "name", None)
            if name is None and isinstance(entry, dict):
                name = entry.get("model") or entry.get("name")
            if name:
                names.append(name)
        return names

    @staticmethod
    def _is_installed(model: str, installed: list[str]) -> bool:
        """An Ollama model name may include an implicit ``:latest`` tag."""
        if not installed:
            return False
        if model in installed:
            return True
        # Match "qwen2.5:7b" against "qwen2.5:7b" exactly; also allow
        # "qwen2.5" to match any installed "qwen2.5:*".
        for name in installed:
            if name == model or name.split(":", 1)[0] == model:
                return True
            if ":" not in model and name.startswith(model + ":"):
                return True
        return False

    def _pick_fallback(self, installed: list[str], exclude: str) -> str | None:
        """Pick the best already-installed chat model."""
        candidates = [
            n for n in installed
            if not any(h in n.lower() for h in self._EMBEDDING_MODEL_HINTS)
            and n != exclude
        ]
        if not candidates:
            return None

        # Prefer known good families in order
        for family in self._PREFERRED_FAMILIES:
            for n in candidates:
                if family in n.lower():
                    return n
        # Otherwise return the first non-embedding model
        return candidates[0]

    @property
    def model(self) -> str:
        return self._model

    def generate_json(
        self,
        system: str,
        prompt: str,
        schema: dict[str, Any] | None = None,
        max_retries: int = 2,
    ) -> dict[str, Any]:
        import ollama

        client = ollama.Client(host=self._host) if self._host else ollama
        last_err: Exception | None = None

        for attempt in range(max_retries + 1):
            try:
                kwargs: dict[str, Any] = {
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    "options": {"temperature": 0.1},
                }
                if schema is not None:
                    kwargs["format"] = schema
                else:
                    kwargs["format"] = "json"

                resp = client.chat(**kwargs)
                content = resp["message"]["content"]
                return json.loads(content)
            except json.JSONDecodeError as e:
                last_err = e
                logger.warning(
                    f"LLM returned non-JSON (attempt {attempt + 1}): {e}"
                )
                continue
            except Exception as e:
                last_err = e
                logger.warning(f"LLM call failed (attempt {attempt + 1}): {e}")
                continue

        raise RuntimeError(f"LLM failed to produce valid JSON: {last_err}")


def default_backend() -> LLMBackend:
    """Return a sensible default backend.

    Resolution order:

    1. Explicit ``CAPSTONE_LLM_BACKEND`` env var ("ollama" or "groq").
    2. If ``GROQ_API_KEY`` is set, prefer Groq (we're probably deployed
       to a public website).
    3. Otherwise Ollama (we're running locally on a developer machine).
    """
    explicit = os.environ.get("CAPSTONE_LLM_BACKEND", "").lower()
    if explicit == "groq":
        return GroqBackend()
    if explicit in ("ollama", "default"):
        return OllamaBackend()
    if explicit:
        raise RuntimeError(f"Unknown LLM backend: {explicit!r}")

    # Auto: if a Groq key is set, use it. This is how the website
    # deployment selects the hosted backend without code changes.
    if os.environ.get("GROQ_API_KEY"):
        try:
            return GroqBackend()
        except Exception as e:
            logger.warning(f"GroqBackend init failed, falling back to Ollama: {e}")

    return OllamaBackend()
