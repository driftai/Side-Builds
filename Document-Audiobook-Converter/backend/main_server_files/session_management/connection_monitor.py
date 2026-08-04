import asyncio
import time
import websockets
import json

class ConnectionMonitor:
    def __init__(self, websocket, connection_id, update_activity_callback):
        self.websocket = websocket
        self.connection_id = connection_id
        self.connection_active = True
        self.last_activity_time = time.time()
        self.external_activity_updater = update_activity_callback

    def record_activity(self):
        """Records activity and updates relevant timestamps."""
        self.last_activity_time = time.time()
        if self.external_activity_updater:
            self.external_activity_updater()

    def is_websocket_open(self):
        """Check if the websocket connection is still open and valid."""
        try:
            if not self.connection_active:
                return False
            # Check the websocket state properly - don't use .closed property
            try:
                # For ServerConnection objects, we need to check if it's closed differently
                # The connection is closed if the state is CLOSED or CLOSING
                if self.websocket.state in (websockets.protocol.State.CLOSED, websockets.protocol.State.CLOSING):
                    print(f"WebSocket is closed (state: {self.websocket.state}) for connection {self.connection_id}")
                    self.connection_active = False
                    return False
                # Send a ping to verify the connection is still alive
                return True
            except Exception as e:
                print(f"Error checking websocket state for {self.connection_id}: {str(e)}")
                self.connection_active = False
                return False
        except Exception as e:
            print(f"Error checking websocket state for {self.connection_id}: {str(e)}")
            self.connection_active = False
            return False

    async def ping_connection(self):
        """Send a ping to verify the connection is still alive."""
        try:
            pong_waiter = await self.websocket.ping()
            await asyncio.wait_for(pong_waiter, timeout=5)
            # If we get here, the connection is still alive
            self.record_activity()
            return True
        except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed):
            print(f"Ping failed for connection {self.connection_id}, marking as inactive")
            self.connection_active = False
            return False
        except Exception as e:
            print(f"Error pinging connection {self.connection_id}: {str(e)}")
            return False

    async def monitor_connection(self):
        """Monitor the connection status continuously."""
        try:
            ping_counter = 0
            while self.connection_active:
                # Check if the websocket is still open using the state property
                try:
                    if self.websocket.state in (websockets.protocol.State.CLOSED, websockets.protocol.State.CLOSING):
                        print(f"Connection monitor detected closed connection: {self.connection_id}")
                        self.connection_active = False
                        break
                    
                    # Every 5th iteration, send a ping to check if client is still connected
                    ping_counter += 1
                    if ping_counter >= 5:
                        ping_counter = 0
                        ping_success = await self.ping_connection()
                        if not ping_success:
                            print(f"Ping failed for connection {self.connection_id}, breaking monitor loop")
                            self.connection_active = False
                            break
                    
                    # Check if the connection has been inactive for too long
                    inactive_time = time.time() - self.last_activity_time
                    if inactive_time > 300:  # 5 minutes (increased from 1 minute)
                        print(f"Connection {self.connection_id} inactive for {inactive_time:.1f} seconds")
                        # Send a system message to inform clients the connection is at risk
                        if inactive_time > 600:  # 10 minutes - send a warning (increased from 1.5 minutes)
                            system_msg = {
                                "is_system_message": True,
                                "text": "WARNING: Connection inactive for over 10 minutes. The connection may be closed soon if no activity is detected."
                            }
                            try:
                                await self.websocket.send(json.dumps(system_msg))
                            except:
                                # If we can't send the message, the connection is probably dead
                                self.connection_active = False
                                break
                except Exception as e:
                    print(f"Error in connection monitor for {self.connection_id}: {e}")
                    # If there's an error checking the connection, it might be dead
                    if "cannot access local variable" in str(e) or "not an attribute" in str(e):
                        print(f"Critical error in monitor, connection object may be invalid")
                        self.connection_active = False
                        break
                
                # Sleep briefly before checking again (5 seconds)
                await asyncio.sleep(5)
        except asyncio.CancelledError:
            print(f"Connection monitor for {self.connection_id} cancelled")
        except Exception as e:
            print(f"Unexpected error in connection monitor for {self.connection_id}: {e}")
        finally:
            # If the monitor exits, make sure we clean up
            if self.connection_active:
                self.connection_active = False
                print(f"Connection monitor exited while connection was still marked active: {self.connection_id}")

    async def safe_send(self, message):
        """Safely send a message through the websocket."""
        try:
            if not self.connection_active:
                print(f"Connection {self.connection_id} marked as inactive, cannot send message")
                return False
            
            # Double check the websocket state
            try:
                # Check if the connection is closed using the state property
                if self.websocket.state in (websockets.protocol.State.CLOSED, websockets.protocol.State.CLOSING):
                    print(f"WebSocket is closed (state: {self.websocket.state}) for connection {self.connection_id}")
                    self.connection_active = False
                    return False
                    
                # If we get here, the connection is open
                await self.websocket.send(message)
                # Update last activity time on successful send
                self.record_activity()
                return True
            except websockets.exceptions.ConnectionClosed as e:
                print(f"Connection {self.connection_id} closed during send: {e.code} - {e.reason}")
                self.connection_active = False
                return False
            except Exception as e:
                print(f"Error during send for connection {self.connection_id}: {str(e)}")
                self.connection_active = False
                return False
        except Exception as e:
            print(f"Error sending message to connection {self.connection_id}: {e}")
            self.connection_active = False
            return False

    async def monitor_connection_recovery(self):
        """Monitor connection and attempt recovery when issues are detected."""
        recovery_attempts = 0
        max_recovery_attempts = 5

        try:
            while self.connection_active and recovery_attempts < max_recovery_attempts:
                try:
                    # Check if connection appears healthy
                    if self.websocket.state in (websockets.protocol.State.CLOSED, websockets.protocol.State.CLOSING):
                        print(f"Connection {self.connection_id} appears closed, waiting for potential recovery...")
                        await asyncio.sleep(2)

                        # Check again after delay
                        if self.websocket.state in (websockets.protocol.State.CLOSED, websockets.protocol.State.CLOSING):
                            print(f"Connection {self.connection_id} still closed after recovery wait")
                            self.connection_active = False
                            break
                        else:
                            print(f"Connection {self.connection_id} recovered!")
                            recovery_attempts = 0  # Reset counter on successful recovery
                            continue

                    # Send a test ping to verify connection health
                    ping_success = await self.ping_connection()
                    if not ping_success:
                        recovery_attempts += 1
                        print(f"Connection {self.connection_id} ping failed (attempt {recovery_attempts}/{max_recovery_attempts})")

                        if recovery_attempts >= max_recovery_attempts:
                            print(f"Connection {self.connection_id} failed {max_recovery_attempts} recovery attempts, marking inactive")
                            self.connection_active = False
                            break

                        # Wait before retrying
                        await asyncio.sleep(3)
                    else:
                        # Connection is healthy, reset recovery attempts
                        if recovery_attempts > 0:
                            print(f"Connection {self.connection_id} recovered after {recovery_attempts} failed attempts")
                            recovery_attempts = 0

                        # Wait before next health check
                        await asyncio.sleep(10)

                except asyncio.CancelledError:
                    print(f"Connection recovery monitor cancelled for {self.connection_id}")
                    break
                except Exception as e:
                    print(f"Error in connection recovery monitor for {self.connection_id}: {e}")
                    recovery_attempts += 1
                    await asyncio.sleep(5)

        except asyncio.CancelledError:
            print(f"Connection recovery monitor cancelled for {self.connection_id}")
        except Exception as e:
            print(f"Unexpected error in connection recovery monitor for {self.connection_id}: {e}")
        finally:
            if not self.connection_active:
                print(f"Connection recovery monitor exiting for inactive connection {self.connection_id}") 