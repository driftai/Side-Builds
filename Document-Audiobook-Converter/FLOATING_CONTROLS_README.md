# Floating Audio Controls - Complete Guide

Your AI Audiobook Converter now supports multiple ways to keep audio controls always visible and accessible!

## 🎯 Available Solutions

### 1. **Electron Always-On-Top Controls** (Recommended)
True system-level floating controls that stay above ALL applications.

**Features:**
- ✅ Stays on top of all windows and applications
- ✅ Works across different tabs and programs
- ✅ Global keyboard shortcut (Ctrl+Shift+B)
- ✅ Native desktop app performance
- ✅ Real-time audio state synchronization

**Setup:**
```bash
# Install Electron dependencies
npm install

# Run in development mode (React + Electron)
npm run electron-dev

# Or run built version
npm run build
npm run electron
```

**Usage:**
- Click the monitor icon (🖥️) in collapsed voice controls
- Or press `Ctrl+Shift+B` anywhere
- Drag the window by its header to reposition
- Controls stay visible above all other applications!

### 2. **Web-Based Floating Controls**
Browser-only floating controls within the current tab.

**Features:**
- ✅ Stays within browser context
- ✅ Works in any modern browser
- ✅ No additional setup required
- ✅ Good for web-only usage

**Usage:**
- Click the popout icon (🔲) in collapsed voice controls
- Drag to reposition within the browser window
- Stays on top within the current browser tab

### 3. **Browser Extension** (Alternative)
Chrome extension with always-on-top popup.

**Setup:**
- Load `extension/` folder as unpacked extension in Chrome
- Click extension icon to create floating controls
- Controls work across browser tabs

## 🎯 **Updated Popout Button**

The **blue monitor icon** (🖥️) in the collapsed voice controls now opens the **Electron always-on-top controls** instead of the old web-based floating controls.

### **What Changed:**
- **Before**: Popout button opened web-based floating controls (stuck within browser)
- **After**: Popout button opens Electron always-on-top controls (truly floating above all windows)

### **How to Access:**
1. **Install the browser extension** (see setup below)
2. **Run the Electron app**: `npm run electron` (in a separate terminal)
3. **Collapse voice controls** (click the ▼ in the voice controls header)
4. **Click the blue monitor icon** (🖥️) in the mini controls
5. **Electron floating controls appear** - they stay on top of ALL applications!

### **Keyboard Shortcut:**
- Press `Ctrl+Shift+B` anywhere to toggle the always-on-top controls

### **Browser Extension Setup:**
1. Open Chrome and go to `chrome://extensions/`
2. Enable "Developer mode"
3. Click "Load unpacked" and select the `extension/` folder
4. The extension should appear in your toolbar

### **How It Works:**
- **Web App** → **Browser Extension** → **Electron App** (via WebSocket)
- The extension acts as a bridge between your web browser and the Electron desktop app
- This allows the popout button to work even when running the React dev server separately!

## 🚀 Quick Start (Complete Setup)

1. **Install dependencies:**
   ```bash
   npm install
   ```

2. **Set up the browser extension:**
   - **For Chrome**: `chrome://extensions/`
   - **For Edge**: `edge://extensions/`
   - Enable "Developer mode"
   - Click "Load unpacked" → select `extension/` folder
   - **Important**: Make sure the extension is enabled and allowed on localhost

3. **Start the React dev server:**
   ```bash
   npm run dev
   ```

4. **Start the Electron app (in a separate terminal):**
   ```bash
   npm run electron
   ```

5. **Use the floating controls:**
   - Go to your React app (http://localhost:5180)
   - Upload an audiobook and collapse voice controls
   - Click the blue monitor icon (🖥️) in mini controls
   - **OR** press `Ctrl+Shift+B` anywhere!

6. **Enjoy always-on-top controls that work across applications!** 🎵✨

## 🎨 Control Features

All floating control solutions include:
- **Progress bar** with current position
- **Play/Pause button** with visual feedback
- **Skip backward/forward** controls
- **Current sentence preview**
- **Status indicators** (playing/paused/stopped)
- **Close button** to hide controls

## 🔧 Technical Comparison

| Feature | Electron | Web Float | Extension |
|---------|----------|-----------|-----------|
| Cross-app visibility | ✅ Yes | ❌ No | ⚠️ Limited |
| Global shortcuts | ✅ Yes | ❌ No | ❌ No |
| Installation | ⚠️ npm install | ✅ None | ⚠️ Manual |
| Performance | ✅ Native | ✅ Web | ⚠️ Extension |
| Browser support | ✅ All | ✅ Modern | ⚠️ Chrome only |

## 🐛 Troubleshooting

### Electron Issues
- **Controls not showing?** Ensure both React dev server and Electron are running
- **Window not on top?** Some fullscreen apps may temporarily override it
- **Sync not working?** Check browser console and Electron dev tools
- **SSL handshake errors?** These are harmless - just Electron accessing external resources
- **Wrong port displayed?** Vite may choose a different port (check console output)

### Web Controls Issues
- **Not floating?** Ensure browser supports CSS positioning
- **Disappearing?** Check if page is reloading or navigating

### Extension Issues
- **Not loading?** Ensure manifest.json is valid and all files present
- **Permissions?** Grant activeTab and windows permissions

## 📁 File Structure

```
project/
├── electron/              # Electron always-on-top controls
│   ├── main.js           # Main process
│   ├── preload.js        # Security bridge
│   ├── controls.html     # Floating UI
│   └── README.md         # Electron docs
├── extension/            # Browser extension
│   ├── manifest.json
│   ├── background.js
│   ├── popup.html
│   └── content.js
├── App.tsx               # Main React app (with integrations)
└── FLOATING_CONTROLS_README.md  # This file
```

## 🎉 Which One to Use?

- **For best experience**: Use Electron controls - they provide true always-on-top behavior
- **For simplicity**: Use web floating controls - no additional setup
- **For Chrome users**: Try the extension approach

All solutions automatically sync with your audiobook playback and provide the same control functionality!

---

**Happy listening! 🎧**
