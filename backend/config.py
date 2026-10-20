"""Environment-based configuration; credentials never belong in source control."""

import os


def load_config():
    return {
        "DB_HOST": os.getenv("DB_HOST", "127.0.0.1"),
        "DB_PORT": int(os.getenv("DB_PORT", "3307")),
        "DB_NAME": os.getenv("DB_NAME", "foodwise"),
        "DB_USER": os.getenv("DB_USER", "root"),
        "DB_PASSWORD": os.getenv("DB_PASSWORD"),
        "DB_CONNECT_TIMEOUT": int(os.getenv("DB_CONNECT_TIMEOUT", "10")),
        "MAX_CONTENT_LENGTH": 16 * 1024,
    }
