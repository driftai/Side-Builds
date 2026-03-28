PDF-OCR-Standalone
===================

A portable, self-contained OCR tool for PDFs using NVIDIA NIM multimodal models.

What's inside
-------------
- ocr.bat                : Windows wrapper (drag/drop a PDF)
- ocr.sh                 : Bash driver (PDF -> PNG -> OCR -> full_output.txt)
- analyze-screenshot-v2.py : OCR engine (OpenAI-compatible client)
- config.json            : Provider configuration (EDIT THIS with your API key)
- images/                : Temporary folder (auto-created, auto-deleted after 8 min)
- README.txt             : This file

Setup (one-time)
----------------
1. Get an NVIDIA API key from https://build.nvidia.com
   - You need access to a multimodal model (e.g., qwen/qwen3.5-122b-a10b or llama-3.2-90b-vision-instruct)
2. Edit `config.json` in this folder:
   - Replace `YOUR_NVIDIA_API_KEY_HERE` with your actual key
   - Optionally change `providers.nvidia.models[0].id` to your preferred model ID
3. Ensure WSL has required packages:
   sudo apt-get update && sudo apt-get install -y poppler-utils imagemagick

Usage (Windows)
---------------
- Drag a PDF file onto `ocr.bat`, or from cmd:
    ocr.bat "W:\path\to\file.pdf"
- Output is written to `full_output.txt` in this folder.
- Intermediate images are deleted after 8 minutes (no manual cleanup needed).

How it works
------------
1. ocr.bat converts the Windows path to WSL and runs ocr.sh
2. ocr.sh converts each PDF page to PNG (pdftoppm or convert)
3. Each PNG is processed by analyze-screenshot-v2.py using the settings in config.json
4. Results are concatenated into full_output.txt
5. Temporary files (images, per-page outputs) are scheduled for deletion after 8 minutes

Requirements
------------
- WSL (Ubuntu) with Python 3
- System packages: pdftoppm (poppler-utils) or convert (imagemagick)
- Outbound HTTPS access to integrate.api.nvidia.com:443
- NVIDIA API key with permission to a multimodal chat.completions model

Troubleshooting
---------------
- "Config not found": Ensure config.json exists in the same folder as analyze-screenshot-v2.py
- "Provider missing apiKey": Edit config.json and put your NVIDIA API key
- "Neither pdftoppm nor convert installed": Install poppler-utils or imagemagick in WSL
- Network/SSL errors: Update CA certificates:
    sudo apt-get install -y ca-certificates && sudo update-ca-certificates --fresh
- Slow pages: Each OCR may take 30–90 seconds depending on model and network.
- Timeouts: Adjust the `timeout=240` value in analyze-screenshot-v2.py if needed.

Notes
-----
- The config.json is your responsibility; it contains your API key. Do not share it publicly.
- All temporary files live under /tmp and are removed after 8 minutes.
- To use a different model, change the `id` in config.json (must support image input).

Version: 2026-03-27 (standalone, no external dependencies)
