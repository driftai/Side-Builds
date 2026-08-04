import asyncio
from functools import partial
from typing import Tuple, Any, Callable, Coroutine
from websockets.server import WebSocketServer
from .server_initializer import initialize_main_server

async def initialize_and_run_server(
    handler: Callable,
    cleanup_interval_sec: int
) -> Tuple[WebSocketServer, asyncio.Task]:
    """
    Initialize and run the main server with the provided handler and cleanup interval.
    
    Args:
        handler: The WebSocket handler function
        cleanup_interval_sec: Interval for running cleanup tasks
        
    Returns:
        Tuple containing the server instance and cleanup task
    """
    try:
        server, cleanup_task = await initialize_main_server(
            handler,
            cleanup_interval_sec=cleanup_interval_sec
        )
        if not server:
            raise RuntimeError("Failed to initialize server")
        return server, cleanup_task
    except Exception as e:
        print(f"\nError initializing server: {e}")
        raise

async def shutdown_server(server: WebSocketServer) -> None:
    """
    Safely shutdown the server.
    
    Args:
        server: The WebSocket server instance to shutdown
    """
    if server:
        print("\nClosing server...")
        server.close()
        await server.wait_closed()
        print("\nServer shutdown complete") 