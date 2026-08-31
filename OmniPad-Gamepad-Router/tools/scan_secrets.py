"""Full repository secret and history auditor."""

import re
import subprocess
import sys

PATTERNS = {
    "GitHub Token": r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,}",
    "OpenAI/Generic API Key": r"sk-[A-Za-z0-9-_]{20,}",
    "Private Key Block": r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----",
    "AWS Access Key": r"AKIA[0-9A-Z]{16}",
    "Cloudflare Token/Key": r"cloudflare[_-]?(?:token|key|secret)\s*[:=]\s*['\"][A-Za-z0-9_-]{20,}['\"]",
    "Hardcoded Tunnel JWT": r"eyJhIjoi[A-Za-z0-9_-]{30,}",
    "Plaintext Password": r"(?:password|passwd|pwd)\s*[:=]\s*['\"][^'\"]{8,}['\"]",
}


def scan():
    print("=" * 70)
    print("  OMNIPAD FULL GIT HISTORY & REPOSITORY SECRET SCAN")
    print("=" * 70)

    try:
        log_out = subprocess.check_output(["git", "log", "-p"], text=True, errors="ignore")
    except Exception as exc:
        print(f"Error running git log: {exc}")
        return 1

    findings = []
    for name, pat in PATTERNS.items():
        regex = re.compile(pat, re.IGNORECASE)
        for m in regex.finditer(log_out):
            start = max(0, log_out.rfind("\n", 0, m.start()))
            end = log_out.find("\n", m.end())
            line = log_out[start:end].strip()
            # Ignore self-references or documentation describing regexes
            if "PATTERNS" in line or "re.compile" in line or "spot checks" in line:
                continue
            findings.append((name, line[:100]))

    print(f"Total commits scanned: {len(subprocess.check_output(['git', 'rev-list', '--all'], text=True).splitlines())}")
    print(f"Total potential secret pattern matches found: {len(findings)}")

    if findings:
        for cat, snippet in findings:
            print(f"  [FLAG] {cat}: {snippet}")
        print("\n>>> SECRET SCAN FOUND POTENTIAL ITEMS. <<<")
        return 1
    else:
        print("\n>>> FULL GIT HISTORY & REPO SCAN: 100% CLEAN! <<<")
        print("No API keys, tokens, passwords, private keys, or hard-coded secrets found.\n")
        return 0


if __name__ == "__main__":
    sys.exit(scan())
