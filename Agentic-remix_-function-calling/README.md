<div align="center">
<img width="1200" height="475" alt="GHBanner" src="https://github.com/user-attachments/assets/0aa67016-6eaf-458a-adb2-6e31a0763ed6" />
</div>

# Agentic Remix Function Calling

This is a local-first Gemini function-calling project that has been substantially edited for local development and repeatable desktop runs.

To create a similar starting point, make a Gemini app in Google AI Studio, export the code, then adapt the project for local Vite development and environment-based API keys.

## Local Changes

- Vite/React project structure prepared for local installs, builds, and previews.
- Environment-based Gemini API key handling through `.env.local`.
- Local package lock included so dependency installs are reproducible.
- Windows-friendly `run.bat` launcher added for easier local startup.
- Source and configuration edits made beyond the original starter bundle.

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
