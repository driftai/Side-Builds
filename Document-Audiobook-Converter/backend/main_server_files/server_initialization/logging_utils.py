"""
Timestamped Logging Utility for GeminiEngine Server

This module provides timestamped logging functionality that can be used throughout the application.
All log messages will be prefixed with timestamps in the format: [YYYY-MM-DD HH:MM:SS.mmm]
"""

import sys
from datetime import datetime

class TimestampedLogger:
    """A logger that adds timestamps to all messages"""

    def __init__(self):
        self.original_stdout = sys.stdout

    def write(self, message):
        """Override stdout write to add timestamps"""
        if message.strip():  # Only add timestamp to non-empty messages
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            # Remove any trailing newline and add our formatted timestamp
            message = message.rstrip('\n')
            self.original_stdout.write(f"[{timestamp}] {message}\n")
        else:
            # Write empty messages as-is
            self.original_stdout.write(message)

    def flush(self):
        """Flush the underlying stdout"""
        self.original_stdout.flush()

# Global logger instance
timestamped_logger = TimestampedLogger()

def enable_timestamped_logging():
    """Enable timestamped logging by replacing sys.stdout"""
    sys.stdout = timestamped_logger

def disable_timestamped_logging():
    """Disable timestamped logging by restoring original stdout"""
    sys.stdout = timestamped_logger.original_stdout

def log(message):
    """Log a message with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] {message}")

# For backward compatibility
def log_with_timestamp(message):
    """Alias for log() function"""
    log(message)