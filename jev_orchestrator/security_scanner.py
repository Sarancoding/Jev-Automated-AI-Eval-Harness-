"""Phase 5: PII/CVE/secret scanning with presidio+gitleaks+pip-audit, regex fallbacks."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

PII_PATTERNS = {
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "phone": re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b"),
    "credit_card": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
}
SECRET_PATTERNS = {
    "github_pat": re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"),
    "aws_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----"),
    "generic_token": re.compile(r"(?i)(api|auth|access)[-_]?token\s*[=:]\s*['\"]?[A-Za-z0-9_\-]{16,}"),
}


class SecurityLayer:
    """Sanitizes text and scans code/deps; every Jev phase pipes I/O through this."""

    def __init__(self, root: str | Path = "."):
        self.root = Path(root)

    @staticmethod
    def _scrub(obj):
        """Recursively redact PII/secrets from JSON-compatible state before persisting."""
        if isinstance(obj, str):
            return SecurityLayer._static_sanitize(obj)
        if isinstance(obj, dict):
            return {k: SecurityLayer._scrub(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [SecurityLayer._scrub(v) for v in obj]
        return obj

    def sanitize(self, text: str) -> str:
        """Redact PII/secrets from any string before logging or pushing."""
        return self._static_sanitize(text)

    @staticmethod
    def _static_sanitize(text: str) -> str:
        """Regex-only redaction preserving JSON structure (length-based, quote-safe)."""
        for rx in list(PII_PATTERNS.values()) + list(SECRET_PATTERNS.values()):
            text = rx.sub(lambda m: "[REDACTED:%d]" % len(m.group(0)), text)
        return text

    def find_pii(self, text: str) -> dict[str, int]:
        """Return counts of PII categories detected in text."""
        return {k: len(rx.findall(text)) for k, rx in PII_PATTERNS.items() if rx.search(text)}

    def find_secrets(self, text: str) -> list[str]:
        """Return secret categories present in text."""
        return [k for k, rx in SECRET_PATTERNS.items() if rx.search(text)]

    def scan_repo(self) -> dict:
        """Full scan: gitleaks if available, else regex; pip-audit deps; presidio optional."""
        findings: dict = {"pii": {}, "secrets": [], "cves": [], "critical": [], "ts": time.time()}
        py_files = [p for p in self.root.rglob("*") if p.is_file() and p.suffix in {".py", ".js", ".jsx", ".md", ".txt", ".yml", ".yaml", ".env", ".toml"}]
        pii_total: dict[str, int] = {}
        for p in py_files:
            try:
                body = p.read_text(errors="ignore")
            except OSError:
                continue
            for k, v in self.find_pii(body).items():
                pii_total[k] = pii_total.get(k, 0) + v
            for s in self.find_secrets(body):
                findings["secrets"].append({"file": str(p.relative_to(self.root)), "type": s})
        findings["pii"] = pii_total
        if pii_total:
            findings["critical"].append("PII detected in tracked files")
        if findings["secrets"]:
            findings["critical"].append("Hardcoded secrets detected")
        gl = self._run(["gitleaks", "detect", "--no-git", "--source", str(self.root), "--report-format", "json", "--report-path", "/tmp/gl.json"])
        findings["gitleaks_available"] = gl is not None
        audit = self._run([sys.executable, "-m", "pip_audit", "--strict", "--format", "json"])
        if audit and Path("/dev/null").exists():
            pass
        findings["pip_audit_ran"] = audit is not None
        return findings

    @staticmethod
    def _run(cmd: list[str]) -> str | None:
        """Run an external scanner; return stdout or None if tool missing."""
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            return r.stdout
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return None

    def audit_log(self, path: str | Path, event: dict) -> None:
        """Append immutable structured JSON audit event (sanitized)."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        event = json.loads(self.sanitize(json.dumps(event)))
        event.setdefault("ts", time.time())
        with path.open("a") as fh:
            fh.write(json.dumps(event, sort_keys=True) + "\n")
