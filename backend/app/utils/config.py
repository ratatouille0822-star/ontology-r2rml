import os


def get_setting(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name, default)
    return value


def is_truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.lower() in {"1", "true", "yes", "on"}
