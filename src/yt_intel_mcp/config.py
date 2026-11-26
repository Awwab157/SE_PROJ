"""Loads the YAML configuration files in ``config/``."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR_ENV = "YT_INTEL_CONFIG_DIR"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def config_dir() -> Path:
    override = os.environ.get(CONFIG_DIR_ENV)
    return Path(override) if override else repo_root() / "config"


def _load(name: str, directory: Path | None) -> dict[str, Any]:
    path = (directory or config_dir()) / name
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{name} must contain a mapping")
    return data


def load_quota_config(directory: Path | None = None) -> dict[str, Any]:
    return _load("quota.yaml", directory)


def load_similarity_config(directory: Path | None = None) -> dict[str, Any]:
    return _load("similarity.yaml", directory)
