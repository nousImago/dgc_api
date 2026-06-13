import logging
import logging.handlers
import os
import sys

import structlog


def configure_logging(level: str = "INFO") -> None:
    """Configure structlog + stdlib logging.

    Renderer selection:
      - LOG_FORMAT=json       -> JSONRenderer (for K8s/cloud log aggregators)
      - LOG_FORMAT=console    -> ConsoleRenderer (colorful, dev-friendly)
      - unset                 -> auto: JSON if not a TTY, Console otherwise

    File output:
      - LOG_FILE=/path/to/app.log  -> also write JSON logs to that file
        (used by the Fluent Bit sidecar to ship logs to MinIO)
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]

    log_file = os.environ.get("LOG_FILE", "")
    if log_file:
        import pathlib
        pathlib.Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=50 * 1024 * 1024,  # 50 MB per file
            backupCount=3,
            encoding="utf-8",
        )
        handlers.append(file_handler)

    logging.basicConfig(
        format="%(message)s",
        handlers=handlers,
        level=log_level,
    )

    log_format = os.environ.get("LOG_FORMAT", "").lower()
    if log_format == "json":
        renderer = structlog.processors.JSONRenderer()
    elif log_format == "console":
        renderer = structlog.dev.ConsoleRenderer()
    else:
        renderer = (
            structlog.dev.ConsoleRenderer()
            if sys.stdout.isatty()
            else structlog.processors.JSONRenderer()
        )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        #logger_factory=structlog.PrintLoggerFactory(),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


logger = structlog.get_logger()
