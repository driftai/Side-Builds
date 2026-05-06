<div align="center">
<img width="1200" height="475" alt="GHBanner" src="https://github.com/user-attachments/assets/0aa67016-6eaf-458a-adb2-6e31a0763ed6" />
</div>

# Agentic Scribe Notetaker

This is a local-first Gemini notetaking project that has been substantially edited for local development, richer configuration, and more reliable local runs.

To create a similar starting point, make a Gemini app in Google AI Studio, export the code, then adapt the project for local Vite development, runtime configuration, and local smoke checks.

## Local Changes

- Vite local dev server configured to bind on `0.0.0.0` at port `3000`.
- Environment-based Gemini API key handling through `.env.local`.
- Added local build, type-check, preview, and smoke-test scripts.
- Expanded app configuration, workspace tooling, UI state, storage, export, and document handling beyond the original starter bundle.
- Local package lock included so dependency installs are reproducible.

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

Useful local checks:

```powershell
npm run lint
npm run build
npm run smoke:workspace-tools
```
