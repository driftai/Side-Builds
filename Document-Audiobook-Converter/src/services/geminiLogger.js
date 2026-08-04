/**
 * Gemini API Logger for React App
 * Communicates with the Python monitoring system
 */

class GeminiLogger {
    constructor() {
        this.monitoringPort = 8081; // Port for monitoring communication
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 2000; // 2 seconds
    }

    // Initialize the logger
    async initialize() {
        console.log('🎯 Gemini Logger: Initializing API activity monitoring...');
        this.connectToMonitor();
    }

    // Connect to the Python monitoring system
    async connectToMonitor() {
        try {
            // Try to connect to the monitoring system
            const response = await fetch(`http://localhost:${this.monitoringPort}/ping`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            if (response.ok) {
                this.isConnected = true;
                this.reconnectAttempts = 0;
                console.log('✅ Gemini Logger: Connected to monitoring system');
            } else {
                throw new Error('Monitor not responding');
            }
        } catch (error) {
            this.isConnected = false;
            console.log('⚠️ Gemini Logger: Monitor not available, logging to console only');

            // Attempt to reconnect if we haven't exceeded max attempts
            if (this.reconnectAttempts < this.maxReconnectAttempts) {
                this.reconnectAttempts++;
                setTimeout(() => this.connectToMonitor(), this.reconnectDelay);
            }
        }
    }

    // Log API call start
    logApiCallStart(callType, details = '') {
        const timestamp = new Date().toLocaleTimeString();

        // Always log to console
        console.log(`🔄 [${timestamp}] Starting ${callType}: ${details}`);

        // Send to monitoring system if connected
        if (this.isConnected) {
            this.sendLogMessage('api_call_start', { callType, details, timestamp });
        }
    }

    // Log API call completion
    logApiCallComplete(callType, success = true, details = '', duration = 0) {
        const timestamp = new Date().toLocaleTimeString();
        const status = success ? '✅ SUCCESS' : '❌ FAILED';
        const durationText = duration > 0 ? ` (${duration.toFixed(2)}s)` : '';

        // Always log to console
        console.log(`🎯 [${timestamp}] ${status}: ${callType}${durationText}`);
        if (details) console.log(`   Details: ${details}`);

        // Send to monitoring system if connected
        if (this.isConnected) {
            this.sendLogMessage('api_call_complete', {
                callType,
                success,
                details,
                duration,
                timestamp
            });
        }
    }

    // Log connection events
    logConnectionEvent(eventType, details = '') {
        const timestamp = new Date().toLocaleTimeString();
        const emoji = eventType === 'connect' ? '🔗' : eventType === 'disconnect' ? '🔌' : '⚠️';

        // Always log to console
        console.log(`${emoji} [${timestamp}] Connection ${eventType}: ${details}`);

        // Send to monitoring system if connected
        if (this.isConnected) {
            this.sendLogMessage('connection_event', { eventType, details, timestamp });
        }
    }

    // Log model activities
    logModelActivity(modelName, activity, details = '') {
        const timestamp = new Date().toLocaleTimeString();

        // Always log to console
        console.log(`🤖 [${timestamp}] ${modelName}: ${activity}`);
        if (details) console.log(`   ${details}`);

        // Send to monitoring system if connected
        if (this.isConnected) {
            this.sendLogMessage('model_activity', { modelName, activity, details, timestamp });
        }
    }

    // Log voice activities
    logVoiceActivity(voiceName, activity, details = '') {
        const timestamp = new Date().toLocaleTimeString();

        // Always log to console
        console.log(`🎤 [${timestamp}] Voice ${voiceName}: ${activity}`);
        if (details) console.log(`   ${details}`);

        // Send to monitoring system if connected
        if (this.isConnected) {
            this.sendLogMessage('voice_activity', { voiceName, activity, details, timestamp });
        }
    }

    // Log errors
    logError(errorType, message, details = null) {
        const timestamp = new Date().toLocaleTimeString();

        // Always log to console
        console.error(`❌ [${timestamp}] ${errorType}: ${message}`);
        if (details) console.error(`   Details:`, details);

        // Send to monitoring system if connected
        if (this.isConnected) {
            this.sendLogMessage('error', { errorType, message, details, timestamp });
        }
    }

    // Log configuration changes
    logConfigChange(configType, oldValue, newValue) {
        const timestamp = new Date().toLocaleTimeString();

        // Always log to console
        console.log(`⚙️ [${timestamp}] Config changed: ${configType}`);
        console.log(`   From: ${oldValue}`);
        console.log(`   To: ${newValue}`);

        // Send to monitoring system if connected
        if (this.isConnected) {
            this.sendLogMessage('config_change', {
                configType,
                oldValue,
                newValue,
                timestamp
            });
        }
    }

    // Send log message to monitoring system
    async sendLogMessage(eventType, data) {
        if (!this.isConnected) return;

        try {
            const response = await fetch(`http://localhost:${this.monitoringPort}/log`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    eventType,
                    data,
                    source: 'audiobook-converter'
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
        } catch (error) {
            // If we can't reach the monitor, mark as disconnected and try to reconnect
            this.isConnected = false;
            console.log('⚠️ Gemini Logger: Lost connection to monitoring system');

            // Attempt to reconnect
            setTimeout(() => this.connectToMonitor(), this.reconnectDelay);
        }
    }

    // Get logger status
    getStatus() {
        return {
            connected: this.isConnected,
            reconnectAttempts: this.reconnectAttempts,
            maxReconnectAttempts: this.maxReconnectAttempts
        };
    }
}

// Create and export singleton instance
export const geminiLogger = new GeminiLogger();

// Initialize when module loads
if (typeof window !== 'undefined') {
    // Only initialize in browser environment
    window.addEventListener('load', () => {
        geminiLogger.initialize();
    });
}

// Export convenience functions for easy logging
export const logApiStart = (callType, details) => geminiLogger.logApiCallStart(callType, details);
export const logApiComplete = (callType, success, details, duration) => geminiLogger.logApiCallComplete(callType, success, details, duration);
export const logConnection = (eventType, details) => geminiLogger.logConnectionEvent(eventType, details);
export const logModel = (modelName, activity, details) => geminiLogger.logModelActivity(modelName, activity, details);
export const logVoice = (voiceName, activity, details) => geminiLogger.logVoiceActivity(voiceName, activity, details);
export const logError = (errorType, message, details) => geminiLogger.logError(errorType, message, details);
export const logConfig = (configType, oldValue, newValue) => geminiLogger.logConfigChange(configType, oldValue, newValue);

export default geminiLogger;
