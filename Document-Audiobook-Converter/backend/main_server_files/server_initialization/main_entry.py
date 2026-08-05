import asyncio
import traceback
import threading
import time
from datetime import datetime
from functools import partial

# Use absolute imports from main_server_files to avoid potential relative import issues
from main_server_files.api_configuration.api_client_manager import setup_api_environment
from main_server_files.api_configuration.gemini_config import MAIN_MODEL
from main_server_files.server_initialization.server_lifecycle_manager import manage_server_lifecycle, cleanup_server
from main_server_files.server_initialization.server_config import (
    CLEANUP_INTERVAL_SEC, DEFAULT_PORT, STATUS_PORT, FORCE_IPV4
)
from main_server_files.server_initialization.network_preference import force_ipv4, describe_local_ipv4
from main_server_files.server_initialization.logging_utils import enable_timestamped_logging
from main_server_files.websocket_server.gemini_session_handler import gemini_session_handler
from main_server_files.session_management.session_manager import (
    MAIN_MODEL_SESSION_LIMIT,
    periodic_cleanup,
    cleanup_resources,
    get_active_sessions
)
from main_server_files.status_monitoring.status_handler import start_status_server, set_circuit_breaker_ref
from main_server_files.status_monitoring.api_usage_monitor import start_monitoring_service
from main_server_files.port_management.port_handler import is_port_in_use, free_port

# Circuit breaker implementation for API protection
class CircuitBreaker:
    """Circuit breaker pattern implementation for API calls"""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN

    def can_call(self) -> bool:
        """Check if the service can be called"""
        if self.state == 'CLOSED':
            return True
        elif self.state == 'OPEN':
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = 'HALF_OPEN'
                return True
            return False
        elif self.state == 'HALF_OPEN':
            return True
        return False

    def on_success(self):
        """Call when operation succeeds"""
        self.failure_count = 0
        self.state = 'CLOSED'

    def on_failure(self):
        """Call when operation fails"""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = 'OPEN'
            print(f"🚨 Circuit breaker opened after {self.failure_count} failures")

    async def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        if not self.can_call():
            raise Exception("Circuit breaker is OPEN")

        try:
            result = await func(*args, **kwargs)
            self.on_success()
            return result
        except Exception as e:
            self.on_failure()
            raise e

# Global circuit breaker instance
api_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60
)

def get_current_time():
    """Get the current time in a formatted string."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

async def initialize_main_server():
    try:
        # Initialize API environment (no client creation needed)
        setup_api_environment()

        # Free the WebSocket port if it's in use
        if is_port_in_use(DEFAULT_PORT):
            print(f"\nWebSocket port {DEFAULT_PORT} is in use. Attempting to free it...")
            free_port(DEFAULT_PORT)
            await asyncio.sleep(2)  # Wait for port to be fully freed

        # Free the status server port if it's in use
        if is_port_in_use(STATUS_PORT):
            print(f"\nStatus server port {STATUS_PORT} is in use. Attempting to free it...")
            free_port(STATUS_PORT)
            await asyncio.sleep(2)  # Wait for port to be fully freed

        # Set circuit breaker reference for status monitoring
        set_circuit_breaker_ref(api_circuit_breaker)

        # Start the status monitoring server in a separate thread
        status_server = start_status_server(STATUS_PORT)
        status_thread = threading.Thread(
            target=status_server.serve_forever,
            daemon=True  # This ensures the thread will be killed when the main program exits
        )
        status_thread.start()

        # Start periodic cleanup
        # Note: periodic_cleanup is also started in initialize_websocket_server, 
        # but we start it here too just in case, or we could remove this one if it's redundant.
        # However, since initialize_websocket_server handles it, we might not need it here.
        # But to be safe and follow the original intent (if any), we'll keep it but ensure it has arguments.
        # Actually, let's rely on the one in websocket_server_handler to avoid double cleanup.
        # But we DO need to start the monitoring service.
        
        # Start API usage monitoring service
        print("Starting API usage monitoring service...")
        asyncio.create_task(start_monitoring_service(get_active_sessions()))

        # Use the handler directly (client will be created dynamically)
        handler = gemini_session_handler

        # Use the server lifecycle manager
        # This will BLOCK until the server stops because initialize_main_server in server_initializer.py
        # awaits asyncio.Future()
        server, cleanup_task = await manage_server_lifecycle(
            handler,
            cleanup_interval_sec=CLEANUP_INTERVAL_SEC
        )

        return server, cleanup_task, status_server
    finally:
        # If manage_server_lifecycle returns, the server is already stopped.
        # But we might need to clean up other resources.
        if 'server' in locals() and server:
            # Server object might be closed, but cleanup_server handles it safely
            await cleanup_server(server)
        
        await cleanup_resources()
        
        if 'status_server' in locals() and status_server:
            status_server.shutdown()
            status_server.server_close()

def run_main_server():
    try:
        # Enable timestamped logging for all console output
        enable_timestamped_logging()

        # Apply before any client is created, so every outbound call uses it.
        if force_ipv4(FORCE_IPV4):
            print(f"Outbound traffic pinned to IPv4 (LAN address {describe_local_ipv4()})")
            print("  An IP-restricted key should allowlist your public IPv4, not this one.")

        print(f"Session limit for {MAIN_MODEL}: {MAIN_MODEL_SESSION_LIMIT} concurrent session(s)")
        print(f"Maximum concurrent sessions: {MAIN_MODEL_SESSION_LIMIT}")

        # Run the main async function
        asyncio.run(initialize_main_server())
    except KeyboardInterrupt:
        print("\nServer stopped by user")
    except Exception as e:
        print(f"\n====== FATAL ERROR ======")
        print(f"Error details: {e}")
        print(f"Error type: {type(e).__name__}")
        traceback.print_exc()
    finally:
        print("\nServer process terminated")
