"""A tiny, external-service-free configuration validation example."""

from __future__ import annotations

from collections.abc import Mapping


def validate_config_before(config: Mapping[str, object]) -> str:
    """Reproduce the old behavior for a missing required ``model`` key."""

    if "model" not in config:
        return "설정 오류"
    return "설정 정상"


def validate_config(config: Mapping[str, object]) -> str:
    """Report a missing ``model`` key without exposing configuration values."""

    if "model" not in config:
        return "설정 오류: model 항목이 없습니다"
    return "설정 정상"
