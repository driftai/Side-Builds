import asyncio
import websockets
import sys
import traceback
import json
import time
from ..port_management.port_handler import is_port_in_use, free_port
from ..status_monitoring.status_handler import start_status_server
from ..session_management.session_manager import periodic_cleanup, get_active_sessions, MAIN_MODEL_SESSION_LIMIT
from ..api_configuration.gemini_config import TimeoutConfig

def create_combined_handler(gemini_session_handler):
    """
    Create a combined handler that can serve both WebSocket connections and HTTP status requests.
    """
    async def combined_handler(request):
        # Check if this is a WebSocket upgrade request
        if request.headers.get('upgrade', '').lower() == 'websocket':
            # Handle as WebSocket
            return await gemini_session_handler(request)
        else:
            # Handle as HTTP request
            if request.path == '/status':
                # Import here to avoid circular imports
                from ..error_handling.api_error_handler import APIErrorHandler
                from ..status_monitoring.status_handler import circuit_breaker_ref

                # Get circuit breaker status if available
                circuit_breaker_status = {}
                if circuit_breaker_ref:
                    circuit_breaker_status = {
                        "state": circuit_breaker_ref.state,
                        "failure_count": circuit_breaker_ref.failure_count,
                        "last_failure_time": circuit_breaker_ref.last_failure_time,
                        "can_call": circuit_breaker_ref.can_call()
                    }

                # Send status information as JSON
                status_data = {
                    "status": "running",
                    "active_sessions": len(get_active_sessions()),
                    "max_connections": MAIN_MODEL_SESSION_LIMIT,
                    "timestamp": time.time(),
                    "circuit_breaker": circuit_breaker_status,
                    "message": "WebSocket server is running"
                }

                # Create HTTP response
                response = f"""HTTP/1.1 200 OK\r
Content-Type: application/json\r
Access-Control-Allow-Origin: *\r
Access-Control-Allow-Methods: GET, OPTIONS\r
Access-Control-Allow-Headers: *\r
Content-Length: {len(json.dumps(status_data))}\r
\r
{json.dumps(status_data)}"""

                await request.writer.write(response.encode())
            else:
                # Return 404 for other paths
                response = """HTTP/1.1 404 Not Found\r
Content-Type: text/plain\r
Access-Control-Allow-Origin: *\r
Content-Length: 13\r
\r
Not Found"""
                await request.writer.write(response.encode())

    return combined_handler

async def initialize_websocket_server(port, gemini_session_handler, cleanup_interval_sec):
    """
    Initialize and start the WebSocket server with retries and enhanced configuration for deadline error handling.
    Enhanced timeout settings to reduce deadline expired errors and improve connection stability.
    
    Args:
        port (int): The port number to run the server on
        gemini_session_handler (callable): The handler function for WebSocket connections
        cleanup_interval_sec (int): Interval for periodic cleanup
        
    Returns:
        websockets.WebSocketServer: The running WebSocket server instance
    """
    try:
        print(f"\nAttempting to start WebSocket server on port {port}")

        # Check if port is already in use and kill the process if needed
        if is_port_in_use(port):
            print(f"\nPort {port} is already in use. Attempting to free it...")
            if free_port(port):
                print(f"Successfully freed port {port}")
                # Increased delay to ensure the port is fully released
                await asyncio.sleep(3)
            else:
                print(f"Failed to free port {port}. Please close the application using it manually.")
                sys.exit(1)
        
        # Try to start the server with retries
        max_retries = 3
        retry_count = 0
        server = None
        
        while retry_count < max_retries:
            try:
                # Create and start the WebSocket server with enhanced settings for deadline handling
                server = await websockets.serve(
                    gemini_session_handler,
                    "0.0.0.0",  # Listen on all interfaces, not just localhost
                    port,
                    ping_interval=5,   # More frequent pings for better connection monitoring
                    ping_timeout=TimeoutConfig.WEBSOCKET_PING_TIMEOUT,   # Use configurable timeout for backend delays
                    max_size=None,     # No limit on message size
                    max_queue=256,     # Larger queue for audio streaming stability
                    close_timeout=TimeoutConfig.WEBSOCKET_CLOSE_TIMEOUT,  # Use configurable close timeout
                    open_timeout=TimeoutConfig.WEBSOCKET_OPEN_TIMEOUT,   # Use configurable open timeout
                    compression=None,  # Disable compression to reduce complexity
                )
                
                if server:
                    print("\n=== WebSocket Server Details ===")
                    print("Status: Running")
                    print(f"Address: ws://localhost:{port}")
                    print(f"External Address: ws://0.0.0.0:{port}")
                    print("Enhanced Configuration for Deadline Error Prevention:")
                    print(f"  - Ping interval: 30s (heartbeat)")
                    print(f"  - Ping timeout: {TimeoutConfig.WEBSOCKET_PING_TIMEOUT}s (deadline handling)")
                    print(f"  - Open timeout: {TimeoutConfig.WEBSOCKET_OPEN_TIMEOUT}s")
                    print(f"  - Close timeout: {TimeoutConfig.WEBSOCKET_CLOSE_TIMEOUT}s")
                    print(f"  - Response timeout: {TimeoutConfig.RESPONSE_TIMEOUT}s (extendable to {TimeoutConfig.RESPONSE_TIMEOUT_EXTENDED}s)")
                    print(f"  - Circuit breaker cooldown: {TimeoutConfig.CIRCUIT_BREAKER_COOLDOWN}s")
                    print("  - Enhanced error recovery enabled")
                    print("  - API usage monitoring active")
                    print("Waiting for connections...")
                    print("\nPress Ctrl+C to stop the server")
                    
                    # Add status endpoint for health check
                    try:
                        # Start a simple HTTP server for status checks on a different port
                        status_port = port + 1
                        if not is_port_in_use(status_port):
                            # Start HTTP server in a separate thread
                            import threading
                            
                            def start_http_server():
                                server = start_status_server(status_port)
                                server.serve_forever()
                            
                            threading.Thread(target=start_http_server, daemon=True).start()
                            print(f"Status HTTP server started on port {status_port}")
                    except Exception as e:
                        print(f"Error starting status HTTP server: {e}")
                    
                    # Start the cleanup task
                    cleanup_task = asyncio.create_task(periodic_cleanup(cleanup_interval_sec))
                    
                    return server, cleanup_task
                    
                else:
                    print(f"Failed to create server instance on attempt {retry_count + 1}")
                    
            except OSError as e:
                if "address already in use" in str(e).lower() and retry_count < max_retries - 1:
                    retry_count += 1
                    print(f"\nPort {port} is still in use. Retrying ({retry_count}/{max_retries})...")
                    
                    # Try to free the port again
                    free_port(port)
                    await asyncio.sleep(3 * retry_count)  # Increased backoff
                else:
                    print(f"Failed to start server after {retry_count + 1} attempts: {e}")
                    raise
            except Exception as e:
                print(f"Unexpected error during server startup (attempt {retry_count + 1}): {e}")
                if retry_count < max_retries - 1:
                    retry_count += 1
                    await asyncio.sleep(2)
                else:
                    raise
                    
        return None, None
        
    except Exception as e:
        print(f"\nServer initialization error: {e}")
        traceback.print_exc()
        return None, None 