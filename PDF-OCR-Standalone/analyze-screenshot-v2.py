#!/usr/bin/env python3
import sys, os, json, base64, imghdr, urllib.request, urllib.error, urllib.parse, random, time

def die(msg, code=1):
    print(msg, file=sys.stderr)
    sys.exit(code)

def load_config_for_inference():
    """Return an ordered list of (provider, model) to try.
    Handles both new array-based and legacy object-based configs."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cfg_path = os.path.join(script_dir, 'config.json')
    if not os.path.isfile(cfg_path):
        die(f"config.json not found at {cfg_path}. Create it or set NVIDIA_API_KEY env var.")
    try:
        with open(cfg_path) as f:
            cfg = json.load(f)
    except Exception as e:
        die(f"Failed to parse config.json: {e}")

    providers_cfg = cfg.get('providers', {})
    selected = cfg.get('selected')

    trials = []

    # New format: providers is a list (ordered)
    if isinstance(providers_cfg, list):
        for p_entry in providers_cfg:
            if not isinstance(p_entry, dict):
                continue
            pname = p_entry.get('name') or p_entry.get('id')
            if not pname:
                continue
            models = p_entry.get('models', [])
            if not models:
                if selected and selected.get('provider') == pname:
                    mid = selected.get('model')
                    if mid:
                        trials.append((p_entry, mid))
                continue
            for m in models:
                mid = m.get('id')
                if mid:
                    trials.append((p_entry, mid))
        if not trials and selected:
            pname = selected.get('provider')
            mid = selected.get('model')
            if pname and mid:
                for p_entry in providers_cfg:
                    if p_entry.get('name') == pname or p_entry.get('id') == pname:
                        trials.append((p_entry, mid))
                        break

    # Legacy format: providers is a dict; selected picks one
    elif isinstance(providers_cfg, dict):
        if selected:
            pname = selected.get('provider')
            mid = selected.get('model')
            if pname and mid and pname in providers_cfg:
                trials.append((providers_cfg[pname], mid))
        if not trials:
            for pname, p in providers_cfg.items():
                if p.get('api') != 'openai-completions':
                    continue
                for m in p.get('models', []):
                    if 'image' in [i.lower() for i in m.get('input', [])]:
                        trials.append((p, m['id']))
                        break
                if trials:
                    break
    else:
        die("Invalid config: 'providers' must be an object or array")

    if not trials:
        die("No provider/model combinations configured for inference")

    # Inject/override API key from environment for all providers
    env_key = os.getenv('NVIDIA_API_KEY', '')
    for i, (p, m) in enumerate(trials):
        api_key = env_key or p.get('apiKey', '')
        if not api_key:
            die(f"Missing API key for provider '{p.get('name')}' (model {m}). Set NVIDIA_API_KEY or add apiKey in config.")
        p = p.copy()
        p['apiKey'] = api_key
        trials[i] = (p, m)
    return trials

def attempt_request(payload, endpoint, api_key, max_retries=3):
    """Return (success, content or error_msg)."""
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    req = urllib.request.Request(endpoint, data=payload, headers=headers, method='POST')

    for attempt in range(1, max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=240) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                if "choices" in result:
                    content = result['choices'][0]['message']['content']
                    return True, content
                elif "error" in result:
                    err = result["error"]
                    msg = err.get('message', str(err))
                    status = err.get('status', 'error')
                    if status in (401, 403) or 'auth' in msg.lower():
                        return False, f"AUTH: HTTP {status} {msg}"
                    return False, f"API ERROR: {status} {msg}"
                else:
                    return False, "Unknown response format"
        except urllib.error.HTTPError as e:
            err_body = e.read().decode('utf-8') if e.fp else str(e)
            if e.code in (401, 403):
                return False, f"AUTH: HTTP {e.code} {e.reason}: {err_body[:200]}"
            if (e.code >= 500 or e.code in (429, 408)) and attempt < max_retries:
                backoff = 2 ** attempt + random.uniform(0, 1)
                time.sleep(backoff)
                continue
            return False, f"HTTP {e.code} {e.reason}: {err_body[:200]}"
        except urllib.error.URLError as e:
            if attempt < max_retries:
                backoff = 2 ** attempt + random.uniform(0, 1)
                time.sleep(backoff)
                continue
            return False, f"Network error: {e.reason}"
        except json.JSONDecodeError as e:
            return False, f"Invalid JSON: {e}"
        except Exception as e:
            if attempt < max_retries:
                backoff = 2 ** attempt + random.uniform(0, 1)
                time.sleep(backoff)
                continue
            return False, f"Unexpected: {e}"
    return False, "Max retries exhausted"

def main():
    if len(sys.argv) < 3:
        die("Usage: analyze-screenshot-v2.py <image_path> <prompt>")
    image_path, prompt = sys.argv[1], sys.argv[2]
    if not os.path.isfile(image_path):
        die(f"Image not found: {image_path}")

    trials = load_config_for_inference()

    try:
        with open(image_path, 'rb') as f:
            img_bytes = f.read()
        b64 = base64.b64encode(img_bytes).decode('utf-8')
        img_type = imghdr.what(image_path) or 'png'
        mime = {
            'jpeg': 'image/jpeg', 'jpg': 'image/jpeg',
            'png': 'image/png', 'gif': 'image/gif', 'webp': 'image/webp'
        }.get(img_type, 'image/png')
    except Exception as e:
        die(f"Failed to read image: {e}")

    system_content = """You are a precise visual analyst. Provide a thorough analysis and then answer the specific question.

CRITICAL: Temporal Awareness
- If the image contains chat logs, history, or previous conversation text, IGNORE them unless explicitly asked.
- Focus ONLY on the current live UI state or displayed content.
- Do not report values found only in chat logs as current.

Output format:
1. Overall scene description.
2. Detailed listing of text/UI elements observed (with coordinates if relevant).
3. Answer the user's question directly, referencing live UI only.
4. End with a one-line summary of the most critical finding."""

    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}
        ]}
    ]

    errors = []
    for idx, (provider, model) in enumerate(trials, start=1):
        base_url = provider.get('baseUrl', '').rstrip('/')
        if not base_url:
            errors.append(f"Provider {provider.get('name','?')} missing baseUrl")
            continue
        endpoint = f"{base_url}/chat/completions"
        payload = json.dumps({
            "model": model,
            "messages": messages,
            "max_tokens": 4096
        }).encode('utf-8')

        api_key = provider['apiKey']
        print(f"[TRY {idx}/{len(trials)}] {provider.get('name','?')} / {model}...", file=sys.stderr)
        success, result = attempt_request(payload, endpoint, api_key)
        if success:
            print(result)
            sys.exit(0)
        else:
            errors.append(f"{provider.get('name','?')}/{model}: {result}")
            if result.startswith("AUTH:"):
                print(f"    Auth failed, moving to next provider.", file=sys.stderr)
                continue
            time.sleep(1)

    print("All providers/models failed:", file=sys.stderr)
    for e in errors:
        print(f"  - {e}", file=sys.stderr)
    die("OCR failed: no working provider/model combination", code=1)

if __name__ == '__main__':
    main()
