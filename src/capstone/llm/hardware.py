"""Hardware-aware model tier selection.

At first run we sniff system RAM (and VRAM where detectable) and pick a
model that fits. The user can always override.
"""

from __future__ import annotations

import logging
import platform
import shutil
import subprocess
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class HardwareTier:
    tier: int  # 1..4
    ram_gb: float
    vram_gb: float
    model: str
    notes: str


# Recommended models per tier — kept close to the spec.
TIER_MODELS = {
    1: ("phi4-mini:3.8b", "LLM used only for short explanations."),
    2: ("phi4:14b", "Good reasoning per GB."),
    3: ("qwen3:30b-a3b", "Default for 24 GB+: fast MoE."),
    4: ("gemma3:27b", "Maximum quality for 32 GB+ machines."),
}


def _total_ram_gb() -> float:
    """Best-effort detection of total system RAM (in GB)."""
    try:
        import psutil

        return psutil.virtual_memory().total / (1024**3)
    except ImportError:
        pass

    # Linux: /proc/meminfo
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal"):
                    kb = int(line.split()[1])
                    return kb / (1024**2)
    except OSError:
        pass

    # macOS: sysctl
    try:
        out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True)
        return int(out.strip()) / (1024**3)
    except (subprocess.SubprocessError, OSError):
        pass

    return 8.0  # Fallback — pick the conservative tier


def _vram_gb() -> float:
    """Detect dedicated GPU VRAM where possible. Returns 0 if none/unknown."""
    if shutil.which("nvidia-smi"):
        try:
            out = subprocess.check_output(
                [
                    "nvidia-smi",
                    "--query-gpu=memory.total",
                    "--format=csv,noheader,nounits",
                ],
                text=True,
            )
            mb = max(int(x.strip()) for x in out.splitlines() if x.strip())
            return mb / 1024
        except (subprocess.SubprocessError, ValueError):
            pass
    # Apple Silicon: unified memory == RAM; report 0 so RAM tier dominates.
    return 0.0


def detect_hardware_tier() -> HardwareTier:
    """Return the recommended hardware tier for this machine."""
    ram = _total_ram_gb()
    vram = _vram_gb()
    is_apple_silicon = platform.system() == "Darwin" and platform.machine() == "arm64"

    # Pick tier by max(RAM, VRAM)
    effective = max(ram, vram)
    if effective <= 8:
        tier = 1
    elif effective < 16:
        tier = 2
    elif effective < 32:
        tier = 3
    else:
        tier = 4

    model, notes = TIER_MODELS[tier]
    if is_apple_silicon:
        notes += " Apple Silicon detected — MLX backend is available for ~2x speedup."

    return HardwareTier(tier=tier, ram_gb=ram, vram_gb=vram, model=model, notes=notes)


def recommend_model() -> str:
    return detect_hardware_tier().model
