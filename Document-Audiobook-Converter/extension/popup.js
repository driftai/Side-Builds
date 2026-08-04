// Popup script for AI Audiobook Floating Controls extension

let currentState = {
  isPlaying: false,
  currentIndex: -1,
  totalSentences: 0,
  currentSentence: ''
};

// DOM elements
const playPauseBtn = document.getElementById('play-pause');
const skipBackwardBtn = document.getElementById('skip-backward');
const skipForwardBtn = document.getElementById('skip-forward');
const closeBtn = document.getElementById('close-btn');
const progressFill = document.getElementById('progress-fill');
const progressText = document.getElementById('progress-text');
const sentencePreview = document.getElementById('sentence-preview');
const playIcon = document.getElementById('play-icon');
const pauseIcon = document.getElementById('pause-icon');
const statusIndicator = document.getElementById('status-indicator');

// Initialize popup
document.addEventListener('DOMContentLoaded', () => {
  setupEventListeners();
  startStateUpdates();
});

// Set up event listeners
function setupEventListeners() {
  // Control buttons
  playPauseBtn.addEventListener('click', () => {
    const command = currentState.isPlaying ? 'pause' : 'play';
    sendCommand(command);
  });

  skipBackwardBtn.addEventListener('click', () => {
    sendCommand('skipBackward');
  });

  skipForwardBtn.addEventListener('click', () => {
    sendCommand('skipForward');
  });

  closeBtn.addEventListener('click', () => {
    chrome.runtime.sendMessage({ action: 'closeFloatingWindow' });
    window.close();
  });

  // Make window draggable
  makeDraggable();
}

// Send command to background script
function sendCommand(command) {
  chrome.runtime.sendMessage({
    action: 'updateAudioState',
    command: command
  });
}

// Update UI based on current state
function updateUI() {
  // Update play/pause button
  if (currentState.isPlaying) {
    playIcon.style.display = 'none';
    pauseIcon.style.display = 'block';
    playPauseBtn.title = 'Pause';
  } else {
    playIcon.style.display = 'block';
    pauseIcon.style.display = 'none';
    playPauseBtn.title = 'Play';
  }

  // Update progress
  const progressPercent = currentState.totalSentences > 0
    ? ((currentState.currentIndex + 1) / currentState.totalSentences) * 100
    : 0;
  progressFill.style.width = `${progressPercent}%`;
  progressText.textContent = `${currentState.currentIndex + 1} / ${currentState.totalSentences}`;

  // Update sentence preview
  sentencePreview.textContent = currentState.currentSentence || 'Ready to play';

  // Update status indicator
  statusIndicator.className = 'status-indicator';
  if (currentState.isPlaying) {
    statusIndicator.classList.add('playing');
  } else if (currentState.currentIndex >= 0) {
    statusIndicator.classList.add('paused');
  } else {
    statusIndicator.classList.add('stopped');
  }

  // Update button states
  skipBackwardBtn.disabled = currentState.currentIndex <= 0;
  skipForwardBtn.disabled = currentState.currentIndex >= currentState.totalSentences - 1;
  playPauseBtn.disabled = currentState.totalSentences === 0;
}

// Request state updates from background script
function startStateUpdates() {
  // Initial update
  requestStateUpdate();

  // Regular updates every 500ms
  setInterval(requestStateUpdate, 500);
}

function requestStateUpdate() {
  chrome.runtime.sendMessage({ action: 'getAudioState' }, (response) => {
    if (response) {
      currentState = response;
      updateUI();
    }
  });
}

// Make the popup window draggable
function makeDraggable() {
  const header = document.getElementById('header');
  let isDragging = false;
  let startX, startY, startLeft, startTop;

  header.addEventListener('mousedown', (e) => {
    isDragging = true;
    startX = e.clientX;
    startY = e.clientY;

    // Get current window position
    chrome.windows.getCurrent((window) => {
      startLeft = window.left;
      startTop = window.top;
    });

    document.body.style.cursor = 'grabbing';
    header.style.cursor = 'grabbing';
  });

  document.addEventListener('mousemove', (e) => {
    if (!isDragging) return;

    const deltaX = e.clientX - startX;
    const deltaY = e.clientY - startY;

    const newLeft = startLeft + deltaX;
    const newTop = startTop + deltaY;

    // Keep window within screen bounds
    const maxLeft = screen.width - window.outerWidth;
    const maxTop = screen.height - window.outerHeight;

    chrome.windows.update(chrome.windows.WINDOW_ID_CURRENT, {
      left: Math.max(0, Math.min(newLeft, maxLeft)),
      top: Math.max(0, Math.min(newTop, maxTop))
    });
  });

  document.addEventListener('mouseup', () => {
    if (isDragging) {
      isDragging = false;
      document.body.style.cursor = '';
      header.style.cursor = 'move';
    }
  });
}
