PDF-OCR-Standalone
===================

A portable, self-contained OCR tool for PDFs using NVIDIA NIM multimodal models.

What's inside
-------------
- ocr.bat                : Interactive Windows wrapper (drag/drop, menu, rerun)
- ocr.py                 : Python driver (PDF -> PNG -> OCR -> full_output.txt)
- analyze-screenshot-v2.py : OCR engine with multi-provider failover
- config.json            : Provider configuration (apiKey fields are "***")
- .env                   : (Optional) NVIDIA_API_KEY=your_key_here
- full_output.txt        : OCR results (created after run)
- last_pdf.txt           : Remembered PDF path for quick rerun (created after first run)

Setup (one-time)
----------------
1. Get an NVIDIA API key from https://build.nvidia.com
   - You need access to a multimodal model (e.g., qwen/qwen3.5-122b-a10b, nvidia/neva-22b, or phi-3/phi-3.5 vision).
2. Create a `.env` file in this folder containing:
     NVIDIA_API_KEY=nvapi-...
   Or, edit `config.json` and replace `"***"` with your key in one provider's `apiKey`.
3. Install Python dependencies:
     pip install pymupdf
   (The batch file will offer to install this automatically on first run.)

Usage (Windows)
---------------
- Double-click `ocr.bat` to open the interactive menu:
    1) Set/Update NVIDIA API key
    2) Run OCR on a PDF
    3) Rerun last PDF
    4) Test OCR (quick sanity check)
    5) Exit
- Drag a PDF file onto `ocr.bat` to run immediately without the menu.
- Output is written to `full_output.txt` in this folder.
- Intermediate images are deleted after processing (no manual cleanup needed).

How it works
------------
1. PyMuPDF renders each PDF page to a PNG image.
2. Each image is sent to analyze-screenshot-v2.py, which reads config.json (or NVIDIA_API_KEY from environment) and calls an OpenAI-compatible vision API.
3. If the first provider/model fails (auth 401/403 or rate limits), it automatically tries the next provider in the config's ordered list.
4. Results are concatenated into full_output.txt.
5. Temporary working directories are deleted automatically.

Requirements
------------
- Windows with Python 3 (tested on Python 3.10+)
- PyMuPDF (`pip install pymupdf`)
- Outbound HTTPS access to integrate.api.nvidia.com:443
- NVIDIA API key with permission to a multimodal chat.completions model

Configuration
-------------
Open `config.json` to adjust fallback chain or model IDs. Example:

{
  "providers": [
    {
      "name": "nvidia",
      "baseUrl": "https://integrate.api.nvidia.com/v1",
      "apiKey": "***",
      "api": "openai-completions",
      "models": [
        { "id": "qwen/qwen3.5-122b-a10b", "input": ["text","image"] }
      ]
    },
    {
      "name": "nvidia-backup-1",
      "baseUrl": "https://integrate.api.nvidia.com/v1",
      "apiKey": "***",
      "models": [
        { "id": "nvidia/neva-22b", "input": ["text","image"] }
      ]
    }
  ],
  "selected": { "provider": "nvidia", "model": "qwen/qwen3.5-122b-a10b" }
}

Key points:
- Providers are tried in order.
- Keep apiKey as "***" when using .env. Otherwise put your real key there (not recommended for shared repos).
- Change model IDs if you have access to different vision models.

Troubleshooting
---------------
- "No real API key": ensure .env exists with NVIDIA_API_KEY, or replace "***" in a provider's apiKey.
- 404 on model: Wrong model ID; verify at https://build.nvidia.com and use the bare ID (no provider prefix).
- All providers fail (403): Your key lacks access to the requested model. Try a different model or check your NVIDIA account.
- Python/PyMuPDF errors: run `pip install pymupdf` in the same environment you run ocr.bat.
- Batch window closes instantly: run from cmd.exe to see error messages.
- Manual entry path truncates at '(' or ')': just type or paste the full path; the batch now handles parentheses safely.
- OCR fails with valid path: check full_output.txt for the analyzer's stderr output; it contains the exact API error.

Notes
-----
- The interactive menu avoids "Press any key" loops and lets you rerun the last PDF quickly.
- Test mode (option 4) verifies connectivity with a tiny PNG; useful to confirm your key and model.
- All temporary files live in a /tmp-style folder and are cleaned up automatically.
- Do not share config.json or .env if they contain real API keys.

Version: 2026-03-27 (pure Windows Python; multi-provider failover; .env support)
