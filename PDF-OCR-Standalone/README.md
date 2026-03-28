# PDF-OCR-Standalone

Portable OCR from PDFs to full text using NVIDIA NIM multimodal models. Pure Windows Python, no WSL required.

## Quick start

1. Install Python dependencies:
   ```cmd
   pip install pymupdf
   ```
   (The `ocr.bat` menu can install this automatically.)

2. Create a `.env` file in this folder with your NVIDIA API key:
   ```
   NVIDIA_API_KEY=nvapi-...
   ```

3. Run `ocr.bat`:
   - Double-click for an interactive menu (set key, run PDF, rerun last, test)
   - Or drag a PDF file onto `ocr.bat` to run immediately.

4. Find results in `full_output.txt`.

## Features

- Interactive Windows batch UI with options for key management, testing, and rerunning
- Automatic multi‑provider failover if a model returns auth (401/403) or rate limiting (429)
- Drag‑and‑drop support; manual path entry handles spaces and parentheses
- Remembers last PDF for quick reruns
- Test mode (`--test`) verifies connectivity with a single API call
- No temporary files left behind

## Requirements

- Windows with Python 3.10+
- PyMuPDF (`pip install pymupdf`)
- Outbound HTTPS to `integrate.api.nvidia.com:443`
- NVIDIA API key for a multimodal model (e.g., `qwen/qwen3.5-122b-a10b`, `nvidia/neva-22b`, `microsoft/phi-3-vision-128k-instruct`)

## Configuration

Edit `config.json` to adjust the provider chain. Use `"***"` for `apiKey` if you store the real key in `.env`.

Example:

```json
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
      "name": "nvidia-backup",
      "baseUrl": "https://integrate.api.nvidia.com/v1",
      "apiKey": "***",
      "models": [
        { "id": "nvidia/neva-22b", "input": ["text","image"] }
      ]
    }
  ],
  "selected": { "provider": "nvidia", "model": "qwen/qwen3.5-122b-a10b" }
}
```

## Troubleshooting

- **No real API key**: Ensure `.env` contains `NVIDIA_API_KEY`, or replace `"***"` in a provider's `apiKey`.
- **404 on model**: Verify the model ID at [NVIDIA Build](https://build.nvidia.com) and use the bare ID (no provider prefix).
- **All providers fail (403)**: Your key may not have access to the selected model; try a different vision model.
- **PyMuPDF missing**: Run `pip install pymupdf` or let the batch install it automatically.
- **Batch window closes instantly**: Run `ocr.bat` from `cmd.exe` to see errors.
- **Manual entry truncates at `(` or `)`**: The fixed batch handles these correctly; just type or paste the full path.
- **OCR fails despite valid path**: Check `full_output.txt` for the analyzer’s stderr; it shows the exact API error.

## Advanced usage

- Call directly from Python: `python ocr.py "path\to\file.pdf"`
- Test mode: `python ocr.py --test` or use the menu option 4.
- To change the fallback order, reorder the `providers` array in `config.json`.

## Notes

- Temporary working folders are automatically deleted.
- The interactive menu avoids intrusive "Press any key" prompts; you choose whether to return to the menu or exit after each run.
- Keep your `.env` and `config.json` private; they contain credentials.

---

*Part of the Hermes Agent Utilities collection.*
