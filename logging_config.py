# -*- coding: utf-8 -*-
"""
Centralized Structured Logging Configuration using structlog with Log Rotation
"""
import logging
import sys
import os
import logging.handlers
import structlog

def setup_logging(log_level="INFO", log_to_file=True, log_dir="logs", max_bytes=10485760, backup_count=5):
    """
    Configure structured logging for the entire application.
    """
    handlers = [logging.StreamHandler(sys.stdout)]

    if log_to_file:
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        log_file = os.path.join(log_dir, "app.log")
        # Global variable to expose the log file path for external modules
        global LOG_FILE_PATH
        LOG_FILE_PATH = log_file
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=max_bytes, backupCount=backup_count, encoding='utf-8'
        )
        handlers.append(file_handler)

    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        handlers=handlers,
    )

    # As per the approved proposal
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,         # Filter logs by level
            structlog.stdlib.add_logger_name,         # Add logger name
            structlog.stdlib.add_log_level,          # Add log level (e.g., info, error)
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"), # ISO format timestamp
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,       # Adds exception info
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()         # Render logs as JSON
        ],
        context_class=dict, # Use a standard dict for context
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Get a logger for this setup message
    logger = structlog.get_logger("logging_setup")
    logger.info("✅ Structured logging configured", log_level=log_level, log_to_file=log_to_file)

def get_logger(name=None):
    """Returns a structlog logger."""
    return structlog.get_logger(name)
