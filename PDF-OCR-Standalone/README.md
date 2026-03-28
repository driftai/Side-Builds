# Hermes Agent Utilities

A collection of standalone tools for AI and productivity workflows.

## PDF-OCR-Standalone

Portable OCR from PDFs to full text using NVIDIA NIM multimodal models.

**Location:** `PDF-OCR-Standalone/`

**Quick start**
1. Install WSL dependencies (Ubuntu):
   ```
   sudo apt-get update
   sudo apt-get install -y poppler-utils imagemagick
   ```
2. Edit `PDF-OCR-Standalone/config.json` and set your NVIDIA API key (`apiKey`).
3. Drag a PDF onto `PDF-OCR-Standalone/ocr.bat` (Windows) or run `PDF-OCR-Standalone/ocr.sh` from WSL.
4. Output appears as `PDF-OCR-Standalone/full_output.txt`.

**What you’ll see**
- The console (batch window) shows progress: page count, per‑page timings, and remaining estimates.
- Final output file is saved in the package folder.
- Temporary images and per‑page files are auto‑deleted after 8 minutes.

**Requirements**
- WSL with Python 3
- `pdftoppm` (poppler-utils) or `convert` (imagemagick)
- Outbound HTTPS to `integrate.api.nvidia.com:443`
- NVIDIA API key for a multimodal model (e.g., `nvidia/qwen/qwen3.5-122b-a10b`)

**Configuration**
Open `PDF-OCR-Standalone/config.json`:
```json
{
  "providers": {
    "nvidia": {
      "baseUrl": "https://integrate.api.nvidia.com/v1",
      "apiKey": "YOUR_NVIDIA_API_KEY_HERE",
      "auth": "api-key",
      "api": "openai-completions",
      "headers": {},
      "models": [
        {
          "id": "nvidia/qwen/qwen3.5-122b-a10b",
          "name": "Qwen 3.5 122B (multimodal)",
          "input": ["text", "image"],
          "maxTokens": 4096,
          "contextWindow": 131072
        }
      ]
    }
  },
  "selected": {
    "provider": "nvidia",
    "model": "nvidia/qwen/qwen3.5-122b-a10b"
  }
}
```
Replace `YOUR_NVIDIA_API_KEY_HERE` with your actual key. You can change the `model` ID if you prefer another multimodal model.

**Troubleshooting**
- “Neither pdftoppm nor convert installed”: install `poppler-utils` or `imagemagick` in WSL.
- “No OpenAI-compatible provider with image support”: check `config.json` `providers.nvidia.models[0].input` includes `"image"`.
- Network/SSL errors: update CA certificates in WSL: `sudo apt-get install -y ca-certificates && sudo update-ca-certificates --fresh`.
- Slow pages: typical 30–90s per page; larger PDFs take longer. Adjust timeout in `analyze-screenshot-v2.py` if needed.
- Batch window closes immediately: run `ocr.bat` from a command prompt to see output.

**Notes**
- All temporary files are under `/tmp` and removed after 8 minutes.
- The package is self-contained; no external paths are used.
- Do not share your `config.json` publicly; it contains your API key.

---
*More tools may be added to this repository over time.*
