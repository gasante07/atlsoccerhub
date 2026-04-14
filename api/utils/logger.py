"""
Logging configuration and utilities
Provides structured logging for the application
"""
import os
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

# Create logs directory if it doesn't exist
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# Log file paths
APP_LOG_FILE = LOG_DIR / "app.log"
ERROR_LOG_FILE = LOG_DIR / "error.log"
ACCESS_LOG_FILE = LOG_DIR / "access.log"

# Maximum log file size (10MB)
MAX_BYTES = 10 * 1024 * 1024
# Number of backup files to keep
BACKUP_COUNT = 5

# Log format
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(log_level: Optional[str] = None) -> None:
    """
    Configure application-wide logging
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
                   Defaults to INFO in production, DEBUG in development
    """
    # Determine log level
    if log_level is None:
        env = os.getenv("ENV", "production").lower()
        log_level = "DEBUG" if env == "development" else "INFO"
    
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()
    
    # Console handler (always show INFO and above)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler for all logs
    file_handler = RotatingFileHandler(
        APP_LOG_FILE,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    # Error-only file handler
    error_handler = RotatingFileHandler(
        ERROR_LOG_FILE,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8"
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_formatter)
    root_logger.addHandler(error_handler)
    
    # Suppress noisy loggers
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    logging.info(f"Logging configured - Level: {log_level}, Logs directory: {LOG_DIR.absolute()}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a module
    
    Args:
        name: Logger name (typically __name__)
    
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


def log_request(request, response=None, duration_ms: Optional[float] = None) -> None:
    """
    Log HTTP request details
    
    Args:
        request: Flask request object
        response: Flask response object (optional)
        duration_ms: Request duration in milliseconds (optional)
    """
    logger = get_logger("access")
    
    # Get client IP
    ip = request.environ.get("HTTP_X_FORWARDED_FOR", request.remote_addr)
    if ip:
        ip = ip.split(",")[0].strip()
    
    # Build log message
    log_data = {
        "method": request.method,
        "path": request.path,
        "ip": ip,
        "user_agent": request.headers.get("User-Agent", "Unknown"),
        "status": response.status_code if response else None,
        "duration_ms": duration_ms
    }
    
    # Format log message
    msg_parts = [
        f"{log_data['method']} {log_data['path']}",
        f"IP: {log_data['ip']}",
    ]
    
    if log_data['status']:
        msg_parts.append(f"Status: {log_data['status']}")
    
    if log_data['duration_ms']:
        msg_parts.append(f"Duration: {log_data['duration_ms']:.2f}ms")
    
    logger.info(" | ".join(msg_parts))


def log_error(error: Exception, context: Optional[str] = None, **kwargs) -> None:
    """
    Log an error with context
    
    Args:
        error: Exception instance
        context: Additional context string
        **kwargs: Additional context data
    """
    logger = get_logger("error")
    
    context_str = f" [{context}]" if context else ""
    extra_data = f" | {kwargs}" if kwargs else ""
    
    logger.error(
        f"Error{context_str}: {str(error)}{extra_data}",
        exc_info=True
    )


def log_database_operation(operation: str, table: str, success: bool, **kwargs) -> None:
    """
    Log database operations
    
    Args:
        operation: Operation type (SELECT, INSERT, UPDATE, DELETE)
        table: Table name
        success: Whether operation succeeded
        **kwargs: Additional context
    """
    logger = get_logger("database")
    
    status = "SUCCESS" if success else "FAILED"
    extra = f" | {kwargs}" if kwargs else ""
    
    logger.debug(f"DB {operation} on {table} - {status}{extra}")
