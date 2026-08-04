"""
Handles API-related errors, particularly quota limits and connection issues.
Enhanced for preview model stability, especially gemini-2.5-flash-preview-native-audio-dialog.
Added specific handling for "Deadline expired before operation could complete" errors.
Updated with configurable timeout settings and enhanced monitoring.
"""
import asyncio
import logging
import random
from typing import Optional, Tuple, Dict
from ..api_configuration.gemini_config import TimeoutConfig, usage_monitor

class APIErrorHandler:
    def __init__(self):
        self.quota_reset_time: Optional[float] = None
        self.consecutive_errors = 0
        self.error_counts: Dict[str, int] = {}
        self.last_error_time: Dict[str, float] = {}
        self.circuit_breaker: Dict[str, bool] = {}
        self.deadline_error_counts: Dict[str, int] = {}
        self.circuit_breaker_reset_time: Dict[str, float] = {}
        
        # Enhanced retry configuration using configurable timeouts
        self.MAX_RETRY_ATTEMPTS = 5  # Increased for preview models
        self.PREVIEW_MODEL_MAX_RETRIES = 7  # Even more for problematic preview models
        self.DEADLINE_ERROR_MAX_RETRIES = 8  # Special handling for deadline errors
        self.QUOTA_WAIT_TIME = 60  # seconds
        
        # Use configurable circuit breaker settings
        self.CIRCUIT_BREAKER_THRESHOLD = 8  # Reduced from 10 for faster activation
        self.CIRCUIT_BREAKER_COOLDOWN = TimeoutConfig.CIRCUIT_BREAKER_COOLDOWN
        self.DEADLINE_ERROR_THRESHOLD = TimeoutConfig.MAX_CONSECUTIVE_DEADLINE_ERRORS

    async def handle_api_error(self, error: Exception, connection_id: str, model_name: str = "") -> Tuple[bool, str]:
        """
        Handle API errors and determine if retry is possible
        
        Args:
            error: The exception that occurred
            connection_id: Unique identifier for the connection
            model_name: Name of the model being used
            
        Returns:
            Tuple[bool, str]: (should_retry, error_message)
        """
        error_msg = str(error).lower()
        current_time = asyncio.get_event_loop().time()
        
        # Track error count for this connection
        if connection_id not in self.error_counts:
            self.error_counts[connection_id] = 0
        self.error_counts[connection_id] += 1
        self.last_error_time[connection_id] = current_time

        # Check circuit breaker status (with auto-reset capability)
        if self._is_circuit_broken(model_name, current_time):
            remaining_time = self._get_circuit_breaker_remaining_time(model_name, current_time)
            return False, f"Circuit breaker active for {model_name}. Service temporarily unavailable. Please try again in {remaining_time:.0f} seconds."

        # Handle credential/permission errors first. These arrive wrapped in a
        # websocket close (1008 policy violation), so without this branch they
        # get misread as a transient connection error and retried forever with
        # a generic "API error" message that hides the real cause.
        if self._is_auth_error(error_msg):
            logging.error(f"API key rejected for connection {connection_id}: {error}")
            return False, f"API key rejected by Google - retrying will not help. {str(error)[:400]}"

        # Handle deadline expired errors specifically with enhanced logic
        if self._is_deadline_error(error_msg):
            logging.warning(f"Deadline expired error for connection {connection_id}: {error}")
            return await self._handle_deadline_error(error_msg, connection_id, model_name, current_time)

        # Determine if this is a preview model
        is_preview_model = any(keyword in model_name.lower() for keyword in ["preview", "experimental", "beta", "alpha"])
        is_native_audio_dialog = "native-audio-dialog" in model_name.lower()
        max_retries = self.PREVIEW_MODEL_MAX_RETRIES if is_preview_model else self.MAX_RETRY_ATTEMPTS

        # Handle actual quota exceeded errors
        if self._is_quota_error(error_msg):
            logging.warning(f"API quota exceeded for connection {connection_id}")

            # Check if this is the preview native audio dialog model
            is_native_audio_preview = "exp" in model_name or "experimental" in model_name

            if self.quota_reset_time is None:
                self.quota_reset_time = current_time + self.QUOTA_WAIT_TIME

            time_remaining = max(0, self.quota_reset_time - current_time)
            if time_remaining > 0:
                if is_native_audio_preview:
                    return False, f"❌ Google API quota exceeded for {model_name}. This preview model may require a paid Google Cloud plan or special access. Please check your Google Cloud Console billing settings and ensure you have access to preview models. Try again in {int(time_remaining)} seconds or switch to the default model."
                else:
                    return False, f"API quota exceeded for {model_name}. Please try again in {int(time_remaining)} seconds."

            self.quota_reset_time = None
            return True, "Retrying after quota reset"

        # Handle preview model specific connection issues
        if is_preview_model and self._is_connection_error(error_msg):
            logging.info(f"Preview model connection issue for {model_name} (connection {connection_id}): {error}")
            
            if self.error_counts[connection_id] <= max_retries:
                # Implement exponential backoff with jitter for preview models
                base_delay = 2 ** min(self.error_counts[connection_id] - 1, 5)  # Cap at 32 seconds
                jitter = random.uniform(0.5, 1.5)  # Add randomness to prevent thundering herd
                delay = base_delay * jitter
                
                await asyncio.sleep(delay)
                
                # Special handling for native-audio-dialog model
                if is_native_audio_dialog:
                    return True, f"Native audio dialog model connection issue (attempt {self.error_counts[connection_id]}/{max_retries}). These models are highly experimental and unstable. Retrying with exponential backoff..."
                else:
                    return True, f"Preview model connection issue (attempt {self.error_counts[connection_id]}/{max_retries}). Preview models can be unstable. Retrying..."
            else:
                self._activate_circuit_breaker(model_name, current_time)
                return False, f"Multiple connection failures for {model_name}. Preview model may be temporarily unavailable."

        # Handle general connection and networking issues
        if self._is_connection_error(error_msg):
            logging.info(f"Connection/network issue for connection {connection_id}: {error}")
            
            if self.error_counts[connection_id] <= max_retries:
                # Shorter delay for general connection issues
                delay = min(self.error_counts[connection_id] * 2, 10)  # Cap at 10 seconds
                await asyncio.sleep(delay)
                return True, f"Connection issue (attempt {self.error_counts[connection_id]}/{max_retries}). Retrying..."
            else:
                return False, "Multiple connection failures. Service may be temporarily unavailable."

        # Handle preview model specific issues
        if self._is_preview_model_error(error_msg) or is_preview_model:
            logging.info(f"Preview model specific issue for {model_name} (connection {connection_id}): {error}")
            
            if self.error_counts[connection_id] <= max_retries:
                # Longer delay for model-specific issues
                delay = min(3 * self.error_counts[connection_id], 15)  # Cap at 15 seconds
                await asyncio.sleep(delay)
                return True, f"Preview model issue (attempt {self.error_counts[connection_id]}/{max_retries}). Retrying..."
            else:
                return False, f"Preview model {model_name} appears to be having persistent issues. Please try again later."

        # Handle other API errors with exponential backoff
        if self.error_counts[connection_id] <= max_retries:
            delay = 2 ** min(self.error_counts[connection_id], 6)  # Exponential backoff, capped
            await asyncio.sleep(delay)
            return True, f"API error - retrying attempt {self.error_counts[connection_id]}/{max_retries}"
        
        return False, f"Maximum retry attempts reached for API error: {str(error)[:100]}..."

    async def _handle_deadline_error(self, error_msg: str, connection_id: str, model_name: str, current_time: float) -> Tuple[bool, str]:
        """
        Handle deadline expired errors with specialized retry logic.
        These are server-side timeout issues from Google's backend.
        """
        # Track deadline errors separately
        if connection_id not in self.deadline_error_counts:
            self.deadline_error_counts[connection_id] = 0
        self.deadline_error_counts[connection_id] += 1
        
        # Use special retry count for deadline errors
        deadline_count = self.deadline_error_counts[connection_id]
        
        # If we've had too many deadline errors, activate circuit breaker
        if deadline_count >= self.DEADLINE_ERROR_THRESHOLD:
            self._activate_circuit_breaker(model_name, current_time)
            return False, f"Multiple deadline errors detected ({deadline_count}/{self.DEADLINE_ERROR_THRESHOLD}). Google's backend appears overloaded. Circuit breaker activated for {model_name}."
        
        if deadline_count <= self.DEADLINE_ERROR_MAX_RETRIES:
            # Enhanced exponential backoff with jitter specifically for deadline errors
            # Use configurable base delay from TimeoutConfig
            base_delay = min(TimeoutConfig.DEADLINE_RETRY_BASE_DELAY * (2 ** (deadline_count - 1)), 90)  # Exponential up to 90 seconds
            jitter = random.uniform(0.8, 1.2)  # Add some randomness
            delay = base_delay * jitter
            
            logging.info(f"Deadline error retry {deadline_count}/{self.DEADLINE_ERROR_MAX_RETRIES} for connection {connection_id}, waiting {delay:.1f}s")
            
            # Update usage monitoring
            usage_monitor.increment_deadline_error()
            
            await asyncio.sleep(delay)
            
            return True, f"Google backend deadline error (attempt {deadline_count}/{self.DEADLINE_ERROR_MAX_RETRIES}). This is a server-side timeout, likely due to backend overload. Retrying with extended delay ({delay:.1f}s)..."
        else:
            # Activate circuit breaker after max retries
            self._activate_circuit_breaker(model_name, current_time)
            return False, f"Maximum deadline error retries reached ({self.DEADLINE_ERROR_MAX_RETRIES}). Google's backend appears to be experiencing persistent issues. Circuit breaker activated."

    def _is_deadline_error(self, error_msg: str) -> bool:
        """Check if the error is related to deadline expiration."""
        deadline_keywords = [
            "deadline expired before operation could complete",
            "deadline_exceeded",
            "deadline expired",
            "operation deadline exceeded",
            "backend deadline",
            "deadline timeout",
            "timeout waiting for",
            "request timed out"
        ]
        return any(keyword in error_msg for keyword in deadline_keywords)

    def _is_auth_error(self, error_msg: str) -> bool:
        """Check if the error is a credential/permission problem (never retryable)."""
        auth_keywords = [
            "ip address restriction", "api_key_ip_address_blocked",
            "api key not valid", "api_key_invalid", "invalid api key",
            "permission_denied", "permission denied", "unauthenticated",
            "api key expired", "referer restriction", "api_key_http_referrer_blocked",
            "has not been used in project", "caller does not have permission",
        ]
        return any(keyword in error_msg for keyword in auth_keywords)

    def _is_quota_error(self, error_msg: str) -> bool:
        """Check if the error is related to quota limits."""
        quota_keywords = [
            "quota exceeded", "requests per minute", "rate limit",
            "too many requests", "quota limit", "resource exhausted",
            "rate limited", "quota depleted",
            "you exceeded your current quota", "exceeded your current quota",
            "billing details", "check your plan and billing"
        ]
        return any(keyword in error_msg for keyword in quota_keywords)

    def _is_connection_error(self, error_msg: str) -> bool:
        """Check if the error is related to connection issues."""
        connection_keywords = [
            "connection", "timeout", "network", "unreachable", "refused", 
            "reset", "closed", "socket", "dns", "resolve", "ssl", "tls",
            "unavailable", "service temporarily", "server error", "internal error",
            "session creation failed", "stream", "websocket", "handshake",
            "connection reset", "connection aborted", "connection lost",
            "backend unavailable", "service down"
        ]
        return any(keyword in error_msg for keyword in connection_keywords)

    def _is_preview_model_error(self, error_msg: str) -> bool:
        """Check if the error is specific to preview models."""
        preview_keywords = [
            "preview", "experimental", "beta", "alpha", "unsupported", 
            "not available", "model not found", "invalid model",
            "model unavailable", "experimental feature"
        ]
        return any(keyword in error_msg for keyword in preview_keywords)

    def _is_circuit_broken(self, model_name: str, current_time: float) -> bool:
        """
        Check if circuit breaker is active for a model with auto-reset capability.
        """
        if model_name not in self.circuit_breaker:
            return False
            
        if not self.circuit_breaker[model_name]:
            return False
            
        # Check if cooldown period has passed
        if model_name in self.circuit_breaker_reset_time:
            if current_time >= self.circuit_breaker_reset_time[model_name]:
                # Auto-reset circuit breaker
                self.circuit_breaker[model_name] = False
                del self.circuit_breaker_reset_time[model_name]
                logging.info(f"Circuit breaker auto-reset for {model_name}")
                return False
                
        return True

    def _get_circuit_breaker_remaining_time(self, model_name: str, current_time: float) -> float:
        """Get remaining time until circuit breaker resets."""
        if model_name in self.circuit_breaker_reset_time:
            return max(0, self.circuit_breaker_reset_time[model_name] - current_time)
        return 0

    def _activate_circuit_breaker(self, model_name: str, current_time: float):
        """Activate circuit breaker for a model with configurable cooldown."""
        self.circuit_breaker[model_name] = True
        self.circuit_breaker_reset_time[model_name] = current_time + self.CIRCUIT_BREAKER_COOLDOWN
        
        # Log circuit breaker activation with usage stats
        stats = usage_monitor.get_stats()
        logging.warning(f"Circuit breaker activated for {model_name}. " +
                       f"Current session stats - Requests: {stats['requests']}, " +
                       f"Errors: {stats['errors']}, Deadline errors: {stats['deadline_errors']}")

    def reset_error_count(self, connection_id: str):
        """Reset error count for a connection."""
        if connection_id in self.error_counts:
            del self.error_counts[connection_id]
        if connection_id in self.deadline_error_counts:
            del self.deadline_error_counts[connection_id]
        if connection_id in self.last_error_time:
            del self.last_error_time[connection_id]

    def cleanup_connection(self, connection_id: str):
        """Clean up all tracking data for a connection."""
        self.reset_error_count(connection_id)

    def get_connection_stats(self, connection_id: str) -> Dict:
        """Get error statistics for a connection."""
        return {
            "error_count": self.error_counts.get(connection_id, 0),
            "deadline_error_count": self.deadline_error_counts.get(connection_id, 0),
            "last_error_time": self.last_error_time.get(connection_id, 0)
        }

    def get_circuit_breaker_status(self) -> Dict:
        """Get status of all circuit breakers."""
        current_time = asyncio.get_event_loop().time()
        status = {}
        
        for model_name in self.circuit_breaker:
            if self.circuit_breaker[model_name]:
                remaining_time = self._get_circuit_breaker_remaining_time(model_name, current_time)
                status[model_name] = {
                    "active": True,
                    "remaining_cooldown": remaining_time
                }
            else:
                status[model_name] = {
                    "active": False,
                    "remaining_cooldown": 0
                }
                
        return status

# Global error handler instance
api_error_handler = APIErrorHandler() 