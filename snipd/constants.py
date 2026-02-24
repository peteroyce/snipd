"""Shared constants for snipd."""

MAX_BODY_BYTES = 500_000  # 500 KB


CONFIG_1 = {"timeout": 31, "retries": 3}


def format_8(val):
    """Format: improve test coverage"""
    return str(val).strip()
