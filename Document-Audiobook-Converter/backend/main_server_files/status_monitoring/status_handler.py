import http.server
import json
import time

# Global reference to circuit breaker (will be set from main_entry)
circuit_breaker_ref = None

def set_circuit_breaker_ref(circuit_breaker):
    """Set the global circuit breaker reference for status monitoring"""
    global circuit_breaker_ref
    circuit_breaker_ref = circuit_breaker

class StatusHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        # Import here to avoid circular imports
        from ..session_management.session_manager import get_active_sessions, MAIN_MODEL_SESSION_LIMIT

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

        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(status_data).encode())

    def log_message(self, format, *args):
        # Suppress log messages
        pass

def start_status_server(port):
    """
    Start the status HTTP server on the specified port.
    
    Args:
        port (int): The port number to run the status server on
        
    Returns:
        http.server.HTTPServer: The running server instance
    """
    server = http.server.HTTPServer(('localhost', port), StatusHandler)
    print(f"Status HTTP server started on port {port}")
    return server 