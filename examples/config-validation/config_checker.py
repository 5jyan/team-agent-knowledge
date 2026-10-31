"""A tiny, external-service-free configuration validation example."""

from __future__ import annotations

from collections.abc import Mapping


def validate_config_before(config: Mapping[str, object]) -> str:
    """Reproduce the old behavior for a missing required ``model`` key."""

    if "model" not in config:
        return "설정 오류"
    return "설정 정상"


def validate_config(config: Mapping[str, object]) -> str:
    """Report all missing required keys without exposing configuration values."""

    missing = [key for key in ("model", "version") if key not in config]
    if missing:
        return f"설정 오류: {', '.join(missing)} 항목이 없습니다"
    return "설정 정상"
