"""LLM backend + reasoning layer (Ollama-default, MLX-optional)."""

from capstone.llm.backend import LLMBackend, OllamaBackend, default_backend
from capstone.llm.hardware import detect_hardware_tier, recommend_model
from capstone.llm.reasoner import LLMReasoner

__all__ = [
    "LLMBackend",
    "OllamaBackend",
    "LLMReasoner",
    "default_backend",
    "detect_hardware_tier",
    "recommend_model",
]
