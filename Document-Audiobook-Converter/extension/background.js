// Background script for AI Audiobook Floating Controls extension

let floatingWindow = null;
let currentTab = null;
let electronConnection = null;

// Try to connect to Electron app via WebSocket
console.log('AI Audiobook Extension: Background script loaded');
connectToElectron();

// Listen for extension icon clicks
chrome.action.onClicked.addListener(async (tab) => {
  currentTab = tab;

  // Check if floating window already exists
  if (floatingWindow) {
    try {
      // Try to focus the existing window
      await chrome.windows.update(floatingWindow.id, { focused: true });
      return;
    } catch (error) {
      // Window was closed, create new one
      floatingWindow = null;
    }
  }

  // Create new always-on-top floating window
  try {
    floatingWindow = await chrome.windows.create({
      url: chrome.runtime.getURL('popup.html'),
      type: 'popup',
      width: 320,
      height: 180,
      top: 100,
      left: 100,
      focused: true,
      alwaysOnTop: true
    });

    // Store window ID for later reference
    chrome.windows.onRemoved.addListener((windowId) => {
      if (windowId === floatingWindow?.id) {
        floatingWindow = null;
      }
    });

  } catch (error) {
    console.error('Failed to create floating window:', error);
  }
});

// Handle messages from content script and popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  switch (request.action) {
    case 'getAudioState':
      // Forward request to content script in the current tab
      if (currentTab) {
        chrome.tabs.sendMessage(currentTab.id, request, (response) => {
          sendResponse(response);
        });
      }
      return true; // Keep message channel open for async response

    case 'updateAudioState':
      // Forward audio control commands to content script
      if (currentTab) {
        chrome.tabs.sendMessage(currentTab.id, request);
      }
      break;

    case 'electronCommand':
      // Forward command to Electron app via WebSocket
      console.log('AI Audiobook Extension: Received electronCommand:', request.method, request.args);

      // Function to send the message
      const sendMessage = () => {
        if (electronConnection && electronConnection.readyState === WebSocket.OPEN) {
          console.log('AI Audiobook Extension: Sending command to Electron app via WebSocket');
          const message = JSON.stringify({
            action: request.method,
            args: request.args
          });
          console.log('AI Audiobook Extension: Message content:', message);
          electronConnection.send(message);
        } else {
          console.log('AI Audiobook Extension: Electron app not connected, attempting to reconnect and send');
          // Try to reconnect and send the message
          connectToElectron();
          // Wait a bit for connection, then retry
          setTimeout(() => {
            if (electronConnection && electronConnection.readyState === WebSocket.OPEN) {
              console.log('AI Audiobook Extension: Reconnected, sending command');
              const message = JSON.stringify({
                action: request.method,
                args: request.args
              });
              electronConnection.send(message);
            } else {
              console.log('AI Audiobook Extension: Still cannot connect to Electron app');
            }
          }, 1000);
        }
      };

      sendMessage();
      break;

    case 'closeFloatingWindow':
      if (floatingWindow) {
        chrome.windows.remove(floatingWindow.id);
        floatingWindow = null;
      }
      break;
  }
});

// Listen for tab updates to maintain current tab reference
chrome.tabs.onActivated.addListener((activeInfo) => {
  chrome.tabs.get(activeInfo.tabId, (tab) => {
    // Only update if it's a relevant tab (localhost or audiobook app)
    if (tab.url && (tab.url.includes('localhost') || tab.url.includes('audiobook'))) {
      currentTab = tab;
    }
  });
});

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete' && tab.active) {
    // Only update if it's a relevant tab
    if (tab.url && (tab.url.includes('localhost') || tab.url.includes('audiobook'))) {
      currentTab = tab;
    }
  }
});

// Connect to Electron app via WebSocket
function connectToElectron() {
  // Don't connect if already connected or connecting
  if (electronConnection && (electronConnection.readyState === WebSocket.OPEN || electronConnection.readyState === WebSocket.CONNECTING)) {
    return;
  }

  // Close existing connection if it's in a bad state
  if (electronConnection && electronConnection.readyState !== WebSocket.CLOSED) {
    try {
      electronConnection.close();
    } catch (e) {
      // Ignore
    }
  }

  console.log('AI Audiobook Extension: Attempting to connect to Electron app...');
  try {
    // Try to connect to Electron app on localhost:3001
    electronConnection = new WebSocket('ws://localhost:3001');

    electronConnection.onopen = () => {
      console.log('AI Audiobook Extension: Successfully connected to Electron app');
    };

    electronConnection.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        console.log('AI Audiobook Extension: Received message from Electron:', message);

        // Forward messages from Electron to web app
        if (currentTab) {
          chrome.tabs.sendMessage(currentTab.id, {
            action: 'electronToWeb',
            ...message
          }).catch(error => {
            console.log('Failed to send message to tab:', error);
          });
        }
      } catch (error) {
        console.error('Error parsing message from Electron:', error);
      }
    };

    electronConnection.onclose = (event) => {
      const reason = event.reason || 'No reason provided';
      console.log('AI Audiobook Extension: Disconnected from Electron app (code:', event.code, 'reason:', reason, ')');
      electronConnection = null;

      // Don't auto-reconnect, let the on-demand reconnection handle it
    };

    electronConnection.onerror = (error) => {
      console.error('AI Audiobook Extension: WebSocket error:', error);
      electronConnection = null;
    };

  } catch (error) {
    console.error('AI Audiobook Extension: Failed to connect to Electron:', error);
    electronConnection = null;
  }
}
