import asyncio
from functools import partial
from typing import Tuple, Any, Callable
from .server_core import initialize_and_run_server, shutdown_server
from websockets.server import WebSocketServer

async def manage_server_lifecycle(
    handler: Callable,
    cleanup_interval_sec: int
) -> Tuple[WebSocketServer, asyncio.Task]:
    """
    Manages the complete server lifecycle including initialization and cleanup.
    
    Args:
        handler: The WebSocket handler function
        cleanup_interval_sec: Interval for cleanup tasks
        
    Returns:
        Tuple containing the server instance and cleanup task
    """
    try:
        # Initialize and run server
        server, cleanup_task = await initialize_and_run_server(
            handler,
            cleanup_interval_sec=cleanup_interval_sec
        )
        
        return server, cleanup_task
        
    except Exception as e:
        print(f"Error in server lifecycle management: {e}")
        raise

async def cleanup_server(server: WebSocketServer) -> None:
    """
    Handles server cleanup and shutdown.
    
    Args:
        server: The server instance to shut down
    """
    if server:
        await shutdown_server(server) 