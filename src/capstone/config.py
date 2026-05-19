"""Configuration loader for the Capstone application.

Reads config.yaml from the project root (or a user-specified path) and
provides typed access to all configuration values.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class ScraperConfig:
    """Settings that control the web scraper behaviour."""

    rate_limit_seconds: float = 1.0
    user_agent: str = "Capstone/1.0 (UWB Course Advisor)"
    stale_after_days: int = 30
    bothell_departments: list[str] = field(default_factory=lambda: ["css"])
    time_schedule_quarters: list[str] = field(
        default_factory=lambda: ["AUT2026"]
    )


@dataclass
class DatabaseConfig:
    """Settings for the SQLite database."""

    path: str = "project"

    def resolve_path(self, project_root: Path) -> Path:
        """Return the absolute path to the SQLite database file."""
        if self.path == "project":
            return project_root / "capstone.db"
        return Path(self.path).expanduser()


@dataclass
class RankingWeights:
    """Weights for the deterministic course-ranking algorithm."""

    criticality: float = 0.30
    availability: float = 0.20
    progress: float = 0.30
    synergy: float = 0.10
    balance_penalty: float = 0.10


@dataclass
class CreditLimits:
    """Credit load constraints."""

    default: int = 15
    hard_ceiling: int = 25


@dataclass
class AppConfig:
    """Top-level application configuration."""

    scraper: ScraperConfig = field(default_factory=ScraperConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    ranking_weights: RankingWeights = field(default_factory=RankingWeights)
    credit_limits: CreditLimits = field(default_factory=CreditLimits)


def _find_project_root() -> Path:
    """Walk upward from this file to find the directory containing config.yaml."""
    current = Path(__file__).resolve().parent
    for _ in range(10):
        if (current / "config.yaml").exists():
            return current
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    # Fallback: assume CWD
    return Path.cwd()


def load_config(config_path: Path | None = None) -> AppConfig:
    """Load and return the application configuration.

    Parameters
    ----------
    config_path:
        Explicit path to a YAML config file.  When *None*, the loader
        searches upward from the package directory for ``config.yaml``.
    """
    project_root = _find_project_root()
    if config_path is None:
        config_path = project_root / "config.yaml"

    if not config_path.exists():
        return AppConfig()

    with open(config_path) as f:
        raw = yaml.safe_load(f) or {}

    scraper_raw = raw.get("scraper", {})
    db_raw = raw.get("database", {})
    weights_raw = raw.get("ranking_weights", {})
    limits_raw = raw.get("credit_limits", {})

    return AppConfig(
        scraper=ScraperConfig(**{
            k: v for k, v in scraper_raw.items()
            if k in ScraperConfig.__dataclass_fields__
        }),
        database=DatabaseConfig(**{
            k: v for k, v in db_raw.items()
            if k in DatabaseConfig.__dataclass_fields__
        }),
        ranking_weights=RankingWeights(**{
            k: v for k, v in weights_raw.items()
            if k in RankingWeights.__dataclass_fields__
        }),
        credit_limits=CreditLimits(**{
            k: v for k, v in limits_raw.items()
            if k in CreditLimits.__dataclass_fields__
        }),
    )


# Module-level convenience: project root for DB path resolution, etc.
PROJECT_ROOT = _find_project_root()
