import logging
from logging.config import dictConfig


def configure_logging() -> None:
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(levelname)s：%(asctime)s %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "access": {
                "format": "%(levelname)s：%(asctime)s %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "default": {
                "class": "logging.StreamHandler",
                "formatter": "default",
            },
            "access": {
                "class": "logging.StreamHandler",
                "formatter": "access",
            },
        },
        "loggers": {
            "uvicorn": {"handlers": ["default"], "level": "INFO", "propagate": False},
            "uvicorn.error": {"handlers": ["default"], "level": "INFO", "propagate": False},
            "uvicorn.access": {"handlers": ["access"], "level": "INFO", "propagate": False},
        },
        "root": {"handlers": ["default"], "level": "INFO"},
    }

    dictConfig(config)
    logging.captureWarnings(True)
