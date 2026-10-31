"""Show the before/after configuration validation behavior."""

from __future__ import annotations

from config_checker import validate_config, validate_config_before


def display_input(config: dict[str, object]) -> str:
    """Show only the input shape so example output never echoes a value."""

    return "{" + ", ".join(f"'{key}': '<redacted>'" for key in config) + "}"


def show_case(label: str, config: dict[str, object]) -> None:
    print(f"{label} input: {display_input(config)}")
    print(f"  before: {validate_config_before(config)}")
    print(f"  after: {validate_config(config)}")


def main() -> None:
    show_case("missing-model", {"version": "1"})
    show_case("missing-both", {})
    show_case("both-present", {"model": "demo-model", "version": "1"})


if __name__ == "__main__":
    main()
