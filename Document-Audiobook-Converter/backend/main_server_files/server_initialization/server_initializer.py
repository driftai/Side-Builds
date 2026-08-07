import argparse
import asyncio
import sys
import websockets
from ..websocket_server import initialize_websocket_server
from ..port_management.port_handler import is_port_in_use
from .server_config import DEFAULT_BIND_HOST, DEFAULT_PORT

async def _cleanup_server_tasks(cleanup_task):
    """Helper function to cleanup server tasks."""
    if cleanup_task:
        try:
            cleanup_task.cancel()
            await asyncio.wait([cleanup_task], timeout=5)
        except Exception as e:
            print(f"Error during cleanup task cancellation: {e}")

async def initialize_main_server(gemini_session_handler, cleanup_interval_sec=60):
    """
    Initialize the main server with command line arguments and proper setup.
    
    Args:
        gemini_session_handler (callable): The handler function for WebSocket connections
        cleanup_interval_sec (int): Interval for periodic cleanup in seconds
        
    Returns:
        tuple: (server, cleanup_task) or (None, None) on failure
    """
    try:
        print("\nStarting WebSocket server...")
        
        # Parse command line arguments
        parser = argparse.ArgumentParser(description='Start Main server on specified port')
        parser.add_argument(
            '--host',
            default=DEFAULT_BIND_HOST,
            help=(
                'Interface to bind (default: 127.0.0.1). Use 0.0.0.0 only '
                'for deliberate access from a trusted LAN.'
            ),
        )
        parser.add_argument('--port', type=int, default=DEFAULT_PORT, help='Port to run server on')
        args = parser.parse_args()

        host = args.host.strip()
        port = args.port

        if not host:
            print('Invalid empty host. Use 127.0.0.1 for local-only access.')
            return None, None
        
        # Validate port before proceeding
        if port < 1024 or port > 65535:
            print(f"Invalid port number: {port}. Port must be between 1024 and 65535.")
            return None, None
            
        if is_port_in_use(port):
            print(f"Port {port} is already in use. Please choose a different port.")
            return None, None
        
        # Initialize the WebSocket server using the component
        try:
            server, cleanup_task = await initialize_websocket_server(
                port,
                gemini_session_handler,
                cleanup_interval_sec,
                host=host,
            )
        except Exception as e:
            print(f"Failed to initialize WebSocket server: {e}")
            return None, None
        
        if server:
            try:
                async with server:
                    await asyncio.Future()  # run forever
            except asyncio.CancelledError:
                await _cleanup_server_tasks(cleanup_task)
                raise
            except Exception as e:
                print(f"Server runtime error: {e}")
                await _cleanup_server_tasks(cleanup_task)
                return None, None
        else:
            print("Failed to initialize WebSocket server")
            return None, None
            
        return server, cleanup_task
            
    except asyncio.CancelledError:
        raise
    except Exception as e:
        print(f"\nServer initialization error: {str(e)}")
        return None, None
