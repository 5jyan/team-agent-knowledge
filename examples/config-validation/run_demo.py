"""Show the before/after configuration validation behavior."""

from __future__ import annotations

from config_checker import validate_config, validate_config_before


def display_input(config: dict[str, object]) -> str:
    """Show only the input shape so example output never echoes a value."""

    if "model" in config:
        return "{'model': '<redacted>'}"
    return "{}"


def show_case(label: str, config: dict[str, object]) -> None:
    print(f"{label} input: {display_input(config)}")
    print(f"  before: {validate_config_before(config)}")
    print(f"  after: {validate_config(config)}")


def main() -> None:
    show_case("missing-model", {})
    show_case("model-present", {"model": "demo-model"})


if __name__ == "__main__":
    main()
