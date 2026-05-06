<div align="center">
<img width="1200" height="475" alt="GHBanner" src="https://github.com/user-attachments/assets/0aa67016-6eaf-458a-adb2-6e31a0763ed6" />
</div>

# Agentic Remix Function Calling

This started from an AI Studio app export, but this copy has been substantially edited for local development and repeatable desktop runs.

AI Studio reference: https://ai.studio/apps/9e35740a-a85b-432e-a51b-80d0388e274a

## Local Changes

- Vite/React project structure prepared for local installs, builds, and previews.
- Environment-based Gemini API key handling through `.env.local`.
- Local package lock included so dependency installs are reproducible.
- Windows-friendly `run.bat` launcher added for easier local startup.
- Source and configuration edits made beyond the original AI Studio bundle.

## Run Locally

**Prerequisites:** Node.js


1. Install dependencies:
   ```powershell
   npm install
   ```
2. Set the `GEMINI_API_KEY` in [.env.local](.env.local) to your Gemini API key
3. Run the app:
   ```powershell
   npm run dev
   ```

You can also use `run.bat` on Windows for a guided local launch.
