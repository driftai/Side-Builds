// Content script for AI Audiobook Floating Controls extension

let audioState = {
  isPlaying: false,
  currentIndex: -1,
  totalSentences: 0,
  currentSentence: ''
};

// Inject electronAPI simulation for communication with Electron app
console.log('AI Audiobook Extension: Content script loaded');
injectElectronAPI();

// Listen for messages from the extension popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  switch (request.action) {
    case 'getAudioState':
      // Get current state from the React app
      updateAudioStateFromDOM();
      sendResponse(audioState);
      break;

    case 'updateAudioState':
      // Send control commands to the React app
      sendCommandToReactApp(request.command);
      break;

    case 'electronCommand':
      // Forward command to simulated electronAPI
      if (window.electronAPI) {
        window.electronAPI[request.method]?.(request.args);
      }
      break;
  }
  return true;
});

// Inject simulated electronAPI for communication with Electron app
function injectElectronAPI() {
  console.log('AI Audiobook Extension: Checking for existing electronAPI...');
  if (window.electronAPI) {
    console.log('AI Audiobook Extension: electronAPI already exists');
    return;
  }

  console.log('AI Audiobook Extension: Injecting electronAPI...');

  // Create a communication bridge using postMessage
  window.electronAPI = {
    updateAudioState: (state) => {
      // Send message to Electron app via extension
      chrome.runtime.sendMessage({
        action: 'electronCommand',
        method: 'updateAudioState',
        args: state
      });
    },

    onAudioCommand: (callback) => {
      // Listen for commands from Electron app
      window.addEventListener('electronCommand', (event) => {
        callback(event.detail.event, event.detail.command);
      });
    },

    toggleControls: () => {
      // Send toggle command to Electron app
      chrome.runtime.sendMessage({
        action: 'electronCommand',
        method: 'toggleControls'
      });
    },

    removeAllListeners: () => {
      // Clean up event listeners
      window.removeEventListener('electronCommand', () => {});
    }
  };

  // Listen for messages from Electron app via extension
  chrome.runtime.onMessage.addListener((request, sender) => {
    if (request.action === 'electronToWeb') {
      // Forward to web app
      window.dispatchEvent(new CustomEvent('electronCommand', {
        detail: request
      }));
    }
  });

  console.log('AI Audiobook Extension: electronAPI injection complete');
}

// Function to extract audio state from the DOM/React app
function updateAudioStateFromDOM() {
  try {
    // This is a simplified approach - in a real implementation,
    // you might need to use React dev tools or inject code to access state

    // Look for playing/paused indicators in the DOM
    const playButtons = document.querySelectorAll('[aria-label*="Play"], [aria-label*="Pause"]');
    audioState.isPlaying = Array.from(playButtons).some(btn =>
      btn.getAttribute('aria-label')?.includes('Pause')
    );

    // Try to find progress indicators
    const progressElements = document.querySelectorAll('[class*="progress"], [class*="current"]');
    progressElements.forEach(el => {
      const text = el.textContent || '';
      const match = text.match(/(\d+)\s*\/\s*(\d+)/);
      if (match) {
        audioState.currentIndex = parseInt(match[1]) - 1; // Convert to 0-based
        audioState.totalSentences = parseInt(match[2]);
      }
    });

    // Try to find current sentence text
    const sentenceElements = document.querySelectorAll('[class*="sentence"], [class*="current"]');
    sentenceElements.forEach(el => {
      if (el.textContent && el.textContent.length > 10) {
        audioState.currentSentence = el.textContent.substring(0, 100);
      }
    });

  } catch (error) {
    console.error('Error updating audio state from DOM:', error);
  }
}

// Function to send commands to the React app by simulating clicks
function sendCommandToReactApp(command) {
  try {
    // First try using data attributes (preferred method)
    let selector = `[data-audio-control="${command}"]`;

    // Fallback to aria-labels if data attributes aren't found
    if (!document.querySelector(selector)) {
      switch (command) {
        case 'play':
          selector = '[aria-label*="Play"]';
          break;
        case 'pause':
          selector = '[aria-label*="Pause"]';
          break;
        case 'skipBackward':
          selector = '[data-audio-control="skip-backward"], [aria-label*="Previous"]';
          break;
        case 'skipForward':
          selector = '[data-audio-control="skip-forward"], [aria-label*="Next"]';
          break;
        default:
          return;
      }
    }

    const button = document.querySelector(selector);
    if (button) {
      button.click();
    } else {
      console.warn(`Button not found for command: ${command}`);
    }
  } catch (error) {
    console.error('Error sending command to React app:', error);
  }
}

// Periodically update audio state (every 500ms)
setInterval(updateAudioStateFromDOM, 500);

// Initial state update
updateAudioStateFromDOM();
