# --------------------------------------------------
# config.py
# --------------------------------------------------
# This file loads all environment-based configuration for the service.
# It ensures the backend follows the 12-factor app pattern:
#   - DATABASE_URL (SQLite file location)
#   - WEBHOOK_SECRET (HMAC signature validation)
#   - LOG_LEVEL (INFO, DEBUG, etc.)
#
# No values are hard-coded — defaults are only fallback values
# for development inside Docker.
# --------------------------------------------------

import os


class SimpleSettings:
    """
    Minimal settings loader for environment configuration.
    Values are read once at startup and used across the application.
    """

    # Expected format: sqlite:////absolute/path/to/file.db
    DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:////data/app.db")

    # Secret used to generate/validate HMAC signatures on inbound webhooks.
    WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")

    # Logging verbosity — defaults to INFO unless overridden.
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")


# Global settings instance used throughout the application.
settings = SimpleSettings()
