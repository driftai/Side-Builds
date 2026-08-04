"""
Server initialization package.
Provides functionality for server setup and lifecycle management.
"""

from .main_entry import run_main_server, initialize_main_server, get_current_time
from .server_lifecycle_manager import manage_server_lifecycle, cleanup_server
from .server_config import CLEANUP_INTERVAL_SEC, CHAT_HISTORY_FILE
from .logging_utils import enable_timestamped_logging, disable_timestamped_logging, log

__all__ = [
    'run_main_server',
    'initialize_main_server',
    'get_current_time',
    'manage_server_lifecycle',
    'cleanup_server',
    'CLEANUP_INTERVAL_SEC',
    'CHAT_HISTORY_FILE',
    'enable_timestamped_logging',
    'disable_timestamped_logging',
    'log'
] 