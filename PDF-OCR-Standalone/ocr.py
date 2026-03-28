#!/usr/bin/env python3
import sys, os, tempfile, subprocess, time, shutil, json
from pathlib import Path

def die(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)

def check_config(analyzer_script):
    cfg_path = os.path.join(os.path.dirname(analyzer_script), 'config.json')
    if not os.path.exists(cfg_path):
        die(f"config.json not found at {cfg_path}. Create it and add providers with API keys.")
    try:
        with open(cfg_path) as f:
            cfg = json.load(f)
    except Exception as e:
        die(f"Failed to parse config.json: {e}")

    providers_cfg = cfg.get('providers', {})
    if isinstance(providers_cfg, dict):
        providers = list(providers_cfg.values())
    elif isinstance(providers_cfg, list):
        providers = providers_cfg
    else:
        providers = []

    env_key = os.getenv('NVIDIA_API_KEY', '')
    found = False
    for p in providers:
        if not isinstance(p, dict):
            continue
        if p.get('api') != 'openai-completions':
            continue
        models = p.get('models', [])
        for m in models:
            inputs = [i.lower() for i in m.get('input', [])]
            if 'image' in inputs:
                # Prefer env var over config (allows config to use placeholders)
                api_key = env_key or p.get('apiKey', '')
                if api_key and 'YOUR_' not in api_key and '***' not in api_key:
                    found = True
                    break
        if found:
            break
    if not found:
        die("config.json must contain at least one OpenAI-compatible provider with an image-capable model and a real API key (not placeholder). Set NVIDIA_API_KEY environment variable or replace '***' in config.json.")

def make_test_image(path):
    """Create a minimal 1x1 red PNG file."""
    png_data = bytes([
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
        0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
        0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
        0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
        0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,
        0x54, 0x08, 0xD7, 0x63, 0xF8, 0xCF, 0xC0, 0x00,
        0x00, 0x00, 0x03, 0x00, 0x01, 0x00, 0x18, 0xDD,
        0x8D, 0xB4, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45,
        0x4E, 0x44, 0xAE, 0x42, 0x60, 0x82
    ])
    with open(path, 'wb') as f:
        f.write(png_data)

def main():
    args = sys.argv[1:]
    test_mode = False
    if args and args[0] == '--test':
        test_mode = True
        args = args[1:]

    if not test_mode and len(args) < 1:
        die("Usage: ocr.py <pdf_path>\n   or: ocr.py --test")
    if test_mode:
        pdf_path = None
    else:
        pdf_path = Path(args[0]).resolve()
        if not pdf_path.exists():
            die(f"PDF not found: {pdf_path}")

    script_dir = Path(__file__).parent.resolve()
    analyzer = script_dir / "analyze-screenshot-v2.py"
    if not analyzer.exists():
        die(f"Analyzer not found: {analyzer}")

    # Check Python deps
    try:
        import fitz  # PyMuPDF
    except ImportError:
        die("PyMuPDF not installed. Run: pip install pymupdf")

    # Check config before proceeding
    check_config(analyzer)

    if test_mode:
        workdir = Path(tempfile.mkdtemp(prefix="ocr_test_"))
        test_img = workdir / "test.png"
        make_test_image(test_img)
        print("[TEST] Created test image. Running analyzer...", file=sys.stderr)
        prompt = "What color is this pixel?"
        cmd = [sys.executable, str(analyzer), str(test_img), prompt]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        print("Analyzer stdout:", result.stdout)
        if result.stderr:
            print("Analyzer stderr:", result.stderr, file=sys.stderr)
        shutil.rmtree(workdir, ignore_errors=True)
        print(f"[TEST] Analyzer exit code: {result.returncode}")
        sys.exit(result.returncode)

    # Normal PDF OCR flow
    workdir = Path(tempfile.mkdtemp(prefix="pdfocr_"))
    images_dir = workdir / "images"
    images_dir.mkdir()

    print("Converting PDF to images...")
    try:
        doc = fitz.open(pdf_path)
        page_count = len(doc)
        for i, page in enumerate(doc, start=1):
            mat = fitz.Matrix(2.0, 2.0)
            pix = page.get_pixmap(matrix=mat)
            img_path = images_dir / f"page-{i:04d}.png"
            pix.save(img_path)
        print(f"Generated {page_count} images.")
    except Exception as e:
        die(f"PDF conversion failed: {e}")
    finally:
        doc.close()

    final_output = script_dir / "full_output.txt"
    with open(final_output, "w", encoding="utf-8") as out_f:
        start_time = time.time()
        img_files = sorted(images_dir.iterdir(), key=lambda p: p.name)
        for idx, img_path in enumerate(img_files, start=1):
            out_txt = workdir / f"ocr_page-{idx}.txt"
            print(f"[{idx}/{page_count}] OCR page {idx}...", flush=True)
            page_start = time.time()
            cmd = [sys.executable, str(analyzer), str(img_path), "Extract all text verbatim with paragraph structure."]
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                if result.returncode == 0:
                    out_f.write(f"=== PAGE {idx} ===\n")
                    out_f.write(result.stdout.strip() + "\n")
                    out_f.write("\n")
                    status = "OK"
                else:
                    out_f.write(f"=== PAGE {idx} ===\n[OCR failed for this page]\n")
                    if result.stderr.strip():
                        out_f.write("STDERR:\n")
                        out_f.write(result.stderr.strip() + "\n")
                    out_f.write("\n")
                    status = "FAILED"
            except subprocess.TimeoutExpired:
                out_f.write(f"=== PAGE {idx} ===\n[OCR timeout]\n\n")
                status = "TIMEOUT"
            except Exception as e:
                out_f.write(f"=== PAGE {idx} ===\n[Error: {e}]\n\n")
                status = "ERROR"
            page_elapsed = time.time() - page_start
            remaining = (page_count - idx) * page_elapsed
            print(f"    Page {idx} {status} ({page_elapsed:.1f}s). Est. {remaining/60:.1f} min remaining.")
        total_elapsed = time.time() - start_time
        print(f"\nAll done in {total_elapsed/60:.1f} minutes. Output: {final_output}")

    shutil.rmtree(workdir, ignore_errors=True)
    print("Temporary files cleaned.")

if __name__ == "__main__":
    main()
