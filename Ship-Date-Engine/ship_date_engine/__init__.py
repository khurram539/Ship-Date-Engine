# Ship Date Engine initialization
"""
Ship Date Engine - Core logging and configuration
"""

from .config import Config
from .logging import setup_logging, logger as root_logger

# Initialize logging
setup_logging()

__version__ = "1.0.0"
__all__ = ["Config", "logger"]
