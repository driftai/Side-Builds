"""
API Usage Monitor - Real-time tracking and diagnostics for API usage patterns
Helps identify quota limits, deadline error patterns, and connection issues
"""
import asyncio
import json
import time
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from ..api_configuration.gemini_config import usage_monitor, TimeoutConfig
from ..error_handling.api_error_handler import api_error_handler

class APIUsageTracker:
    """Enhanced API usage tracking with real-time diagnostics"""
    
    def __init__(self):
        self.session_start_time = time.time()
        self.request_history: List[Dict] = []
        self.error_history: List[Dict] = []
        self.deadline_error_history: List[Dict] = []
        self.connection_metrics: Dict[str, Dict] = {}
        self.performance_metrics = {
            "average_response_time": 0.0,
            "peak_response_time": 0.0,
            "successful_requests": 0,
            "failed_requests": 0,
            "timeout_requests": 0
        }
        
    def log_request_start(self, connection_id: str, request_type: str = "chat"):
        """Log the start of a new request"""
        timestamp = time.time()
        request_data = {
            "connection_id": connection_id,
            "request_type": request_type,
            "start_time": timestamp,
            "status": "pending"
        }
        self.request_history.append(request_data)
        
        # Initialize connection metrics if needed
        if connection_id not in self.connection_metrics:
            self.connection_metrics[connection_id] = {
                "requests": 0,
                "errors": 0,
                "deadline_errors": 0,
                "last_request": timestamp,
                "average_response_time": 0.0
            }
        
        self.connection_metrics[connection_id]["requests"] += 1
        self.connection_metrics[connection_id]["last_request"] = timestamp
        
        return len(self.request_history) - 1  # Return index for completion tracking
    
    def log_request_completion(self, request_index: int, success: bool = True, response_time: float = 0.0):
        """Log the completion of a request"""
        if 0 <= request_index < len(self.request_history):
            request = self.request_history[request_index]
            request["end_time"] = time.time()
            request["response_time"] = response_time or (request["end_time"] - request["start_time"])
            request["status"] = "success" if success else "failed"
            
            # Update performance metrics
            if success:
                self.performance_metrics["successful_requests"] += 1
                # Update average response time
                total_successful = self.performance_metrics["successful_requests"]
                current_avg = self.performance_metrics["average_response_time"]
                self.performance_metrics["average_response_time"] = (
                    (current_avg * (total_successful - 1) + request["response_time"]) / total_successful
                )
                # Update peak response time
                if request["response_time"] > self.performance_metrics["peak_response_time"]:
                    self.performance_metrics["peak_response_time"] = request["response_time"]
            else:
                self.performance_metrics["failed_requests"] += 1
                
            # Update connection metrics
            connection_id = request["connection_id"]
            if connection_id in self.connection_metrics:
                if not success:
                    self.connection_metrics[connection_id]["errors"] += 1
                
                # Update connection average response time
                conn_requests = self.connection_metrics[connection_id]["requests"]
                conn_avg = self.connection_metrics[connection_id]["average_response_time"]
                self.connection_metrics[connection_id]["average_response_time"] = (
                    (conn_avg * (conn_requests - 1) + request["response_time"]) / conn_requests
                )
    
    def log_error(self, connection_id: str, error_type: str, error_message: str, is_deadline_error: bool = False):
        """Log an API error with detailed information"""
        timestamp = time.time()
        error_data = {
            "connection_id": connection_id,
            "error_type": error_type,
            "error_message": error_message,
            "timestamp": timestamp,
            "is_deadline_error": is_deadline_error
        }
        
        self.error_history.append(error_data)
        
        if is_deadline_error:
            self.deadline_error_history.append(error_data)
            if connection_id in self.connection_metrics:
                self.connection_metrics[connection_id]["deadline_errors"] += 1
    
    def log_timeout(self, connection_id: str, timeout_duration: float):
        """Log a timeout event"""
        self.performance_metrics["timeout_requests"] += 1
        self.log_error(connection_id, "timeout", f"Request timed out after {timeout_duration}s", False)
    
    def get_current_stats(self) -> Dict:
        """Get current comprehensive statistics"""
        current_time = time.time()
        session_duration = current_time - self.session_start_time
        
        # Get usage monitor stats
        usage_stats = usage_monitor.get_stats()
        
        # Calculate error rates
        total_requests = len(self.request_history)
        total_errors = len(self.error_history)
        deadline_errors = len(self.deadline_error_history)
        
        # Get circuit breaker status
        circuit_breaker_status = api_error_handler.get_circuit_breaker_status()
        
        # Recent activity (last 5 minutes)
        recent_cutoff = current_time - 300  # 5 minutes
        recent_requests = [r for r in self.request_history if r["start_time"] > recent_cutoff]
        recent_errors = [e for e in self.error_history if e["timestamp"] > recent_cutoff]
        recent_deadline_errors = [e for e in self.deadline_error_history if e["timestamp"] > recent_cutoff]
        
        return {
            "session_info": {
                "duration_seconds": session_duration,
                "duration_formatted": self._format_duration(session_duration),
                "start_time": datetime.fromtimestamp(self.session_start_time).isoformat()
            },
            "request_stats": {
                "total_requests": total_requests,
                "successful_requests": self.performance_metrics["successful_requests"],
                "failed_requests": self.performance_metrics["failed_requests"],
                "timeout_requests": self.performance_metrics["timeout_requests"],
                "success_rate": (self.performance_metrics["successful_requests"] / max(total_requests, 1)) * 100
            },
            "error_stats": {
                "total_errors": total_errors,
                "deadline_errors": deadline_errors,
                "error_rate": (total_errors / max(total_requests, 1)) * 100,
                "deadline_error_rate": (deadline_errors / max(total_requests, 1)) * 100
            },
            "performance_metrics": self.performance_metrics.copy(),
            "recent_activity": {
                "requests_last_5min": len(recent_requests),
                "errors_last_5min": len(recent_errors),
                "deadline_errors_last_5min": len(recent_deadline_errors)
            },
            "circuit_breaker_status": circuit_breaker_status,
            "connection_metrics": self.connection_metrics.copy(),
            "timeout_config": {
                "response_timeout": TimeoutConfig.RESPONSE_TIMEOUT,
                "response_timeout_extended": TimeoutConfig.RESPONSE_TIMEOUT_EXTENDED,
                "websocket_ping_timeout": TimeoutConfig.WEBSOCKET_PING_TIMEOUT,
                "circuit_breaker_cooldown": TimeoutConfig.CIRCUIT_BREAKER_COOLDOWN,
                "max_deadline_errors": TimeoutConfig.MAX_CONSECUTIVE_DEADLINE_ERRORS
            }
        }
    
    def get_diagnostic_report(self) -> str:
        """Generate a human-readable diagnostic report"""
        stats = self.get_current_stats()
        
        report = []
        report.append("=== API Usage Diagnostic Report ===")
        report.append(f"Session Duration: {stats['session_info']['duration_formatted']}")
        report.append(f"Started: {stats['session_info']['start_time']}")
        report.append("")
        
        # Request statistics
        request_stats = stats['request_stats']
        report.append("Request Statistics:")
        report.append(f"  Total Requests: {request_stats['total_requests']}")
        report.append(f"  Successful: {request_stats['successful_requests']} ({request_stats['success_rate']:.1f}%)")
        report.append(f"  Failed: {request_stats['failed_requests']}")
        report.append(f"  Timeouts: {request_stats['timeout_requests']}")
        report.append("")
        
        # Error statistics
        error_stats = stats['error_stats']
        report.append("Error Statistics:")
        report.append(f"  Total Errors: {error_stats['total_errors']} ({error_stats['error_rate']:.1f}%)")
        report.append(f"  Deadline Errors: {error_stats['deadline_errors']} ({error_stats['deadline_error_rate']:.1f}%)")
        report.append("")
        
        # Performance metrics
        perf = stats['performance_metrics']
        report.append("Performance Metrics:")
        report.append(f"  Average Response Time: {perf['average_response_time']:.2f}s")
        report.append(f"  Peak Response Time: {perf['peak_response_time']:.2f}s")
        report.append("")
        
        # Recent activity
        recent = stats['recent_activity']
        report.append("Recent Activity (Last 5 minutes):")
        report.append(f"  Requests: {recent['requests_last_5min']}")
        report.append(f"  Errors: {recent['errors_last_5min']}")
        report.append(f"  Deadline Errors: {recent['deadline_errors_last_5min']}")
        report.append("")
        
        # Circuit breaker status
        cb_status = stats['circuit_breaker_status']
        if cb_status:
            report.append("Circuit Breaker Status:")
            for model, status in cb_status.items():
                if status['active']:
                    report.append(f"  {model}: ACTIVE (cooldown: {status['remaining_cooldown']:.0f}s)")
                else:
                    report.append(f"  {model}: INACTIVE")
            report.append("")
        
        # Recommendations
        report.append("Recommendations:")
        if error_stats['deadline_error_rate'] > 10:
            report.append("  ⚠️  High deadline error rate detected - Google backend may be overloaded")
        if error_stats['error_rate'] > 20:
            report.append("  ⚠️  High overall error rate - check network connectivity")
        if perf['average_response_time'] > 30:
            report.append("  ⚠️  Slow response times - consider increasing timeouts")
        if not cb_status or not any(status['active'] for status in cb_status.values()):
            report.append("  ✅ No circuit breakers active")
        if error_stats['deadline_error_rate'] < 5 and error_stats['error_rate'] < 10:
            report.append("  ✅ System operating within normal parameters")
        
        return "\n".join(report)
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration in a human-readable format"""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}m"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}h"
    
    def export_logs(self, filepath: str):
        """Export all logs to a JSON file for analysis"""
        export_data = {
            "session_info": {
                "start_time": self.session_start_time,
                "export_time": time.time()
            },
            "request_history": self.request_history,
            "error_history": self.error_history,
            "deadline_error_history": self.deadline_error_history,
            "connection_metrics": self.connection_metrics,
            "performance_metrics": self.performance_metrics,
            "stats": self.get_current_stats()
        }
        
        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=2, default=str)

# Global tracker instance
api_usage_tracker = APIUsageTracker()

async def start_monitoring_service(websocket_connections):
    """Start the monitoring service that periodically logs diagnostics"""
    while True:
        await asyncio.sleep(300)  # Every 5 minutes
        
        try:
            # Generate diagnostic report
            report = api_usage_tracker.get_diagnostic_report()
            print("\n" + "="*50)
            print(report)
            print("="*50 + "\n")
            
            # Send status to connected clients
            stats = api_usage_tracker.get_current_stats()
            status_message = {
                "type": "system_status",
                "stats": stats,
                "timestamp": time.time()
            }
            
            # Send to all connected clients (if any)
            if websocket_connections:
                for connection_id, connection_data in websocket_connections.items():
                    if hasattr(connection_data, 'websocket') and connection_data.websocket:
                        try:
                            await connection_data.websocket.send(json.dumps({
                                "text": f"System Status Update: {stats['request_stats']['success_rate']:.1f}% success rate, {stats['error_stats']['deadline_errors']} deadline errors",
                                "is_system_message": True,
                                "stats": stats
                            }))
                        except Exception as e:
                            print(f"Failed to send status update to {connection_id}: {e}")
                            
        except Exception as e:
            print(f"Error in monitoring service: {e}") 