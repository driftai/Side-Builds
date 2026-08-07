const WebSocket = require('ws');

/**
 * Owns the local WebSocket transport used by browser tabs and the extension.
 * Electron window state stays in main.cjs and is changed only through the
 * callbacks supplied here.
 */
function createExtensionRelay({ onToggleControls, onUpdateAudioState, onQuit }) {
  let server;
  let lastToggleTime = 0;
  const connections = new Set();

  function broadcast(payload) {
    const message = JSON.stringify(payload);
    for (const client of connections) {
      try {
        if (client.readyState === WebSocket.OPEN) client.send(message);
      } catch (error) {
        console.error('Could not reach a socket client:', error.message);
      }
    }
  }

  function handleMessage(ws, rawMessage) {
    try {
      const data = JSON.parse(rawMessage.toString());
      switch (data.action) {
        case 'toggleControls': {
          const now = Date.now();
          if (now - lastToggleTime < 500) return;
          lastToggleTime = now;
          onToggleControls();
          return;
        }
        case 'updateAudioState':
          console.log('Updating audio state:', data.args);
          onUpdateAudioState(data.args);
          return;
        case 'quit':
          console.log('Received quit command from extension, shutting down...');
          onQuit();
          return;
        default:
          if (data.type === 'ping') ws.send(JSON.stringify({ type: 'pong' }));
      }
    } catch (error) {
      console.error('Error parsing WebSocket message:', error);
    }
  }

  function setupServer() {
    server.on('connection', (ws) => {
      console.log('Browser extension connected to WebSocket server');
      connections.add(ws);
      ws.isAlive = true;
      ws.on('message', message => handleMessage(ws, message));
      ws.on('close', (code) => {
        console.log('Browser extension disconnected (code:', code, ')');
        connections.delete(ws);
      });
      ws.on('error', (error) => {
        console.error('WebSocket connection error:', error.message);
        connections.delete(ws);
      });
      ws.on('pong', () => { ws.isAlive = true; });
    });

    const healthCheck = setInterval(() => {
      if (!server?.clients) return;
      server.clients.forEach((ws) => {
        if (ws.isAlive === false) {
          console.log('Terminating dead WebSocket connection');
          ws.terminate();
          return;
        }
        ws.isAlive = false;
        ws.ping();
      });
    }, 30000);

    server.on('close', () => {
      clearInterval(healthCheck);
      console.log('WebSocket server closed');
    });
    server.on('error', error => console.error('WebSocket server error:', error));
  }

  function start() {
    try {
      let remainingRetries = 5;
      const tryStartServer = (port) => {
        try {
          server = new WebSocket.Server({ port });
          console.log(`WebSocket server started on port ${port}`);
          setupServer();
        } catch (error) {
          if (error.code === 'EADDRINUSE' && remainingRetries > 0) {
            console.log(`Port ${port} in use, trying port ${port + 1}...`);
            remainingRetries -= 1;
            tryStartServer(port + 1);
          } else {
            console.error('Failed to start WebSocket server:', error.message);
          }
        }
      };
      tryStartServer(3001);
    } catch (error) {
      console.error('Failed to initialize WebSocket server:', error);
    }
  }

  function close() {
    if (!server) return;
    console.log('Closing WebSocket server...');
    server.clients.forEach(client => client.close(1000, 'Server shutting down'));
    server.close(() => console.log('WebSocket server closed successfully'));
  }

  return { start, broadcast, close };
}

module.exports = { createExtensionRelay };
