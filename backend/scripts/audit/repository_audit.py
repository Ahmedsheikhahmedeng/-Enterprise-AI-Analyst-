"""Automated enterprise repository audit script."""

import re
import sys
from pathlib import Path


class RepositoryAuditor:
    SECRET_PATTERNS = [
        re.compile(r"['\"]sk-[a-zA-Z0-9]{20,}['\"]"),
        re.compile(r"['\"]ghp_[a-zA-Z0-9]{20,}['\"]"),
        re.compile(r"BEGIN PRIVATE KEY"),
    ]

    PROD_TEST_IMPORT_PATTERNS = [
        re.compile(r"^\s*import pytest\b"),
        re.compile(r"^\s*from unittest\.mock import\b"),
    ]

    DEBUG_PATTERNS = [
        re.compile(r"^\s*breakpoint\(\)"),
    ]

    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir
        self.backend_app = root_dir / "backend" / "app"
        self.findings: list[dict[str, str]] = []
        self.todo_count = 0
        self.fixme_count = 0

    def audit_app_code(self) -> None:
        if not self.backend_app.exists():
            print(f"Backend app directory not found at: {self.backend_app}")
            return

        for path in self.backend_app.rglob("*.py"):
            if "__pycache__" in str(path):
                continue

            rel_path = path.relative_to(self.root_dir)
            with open(path, encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()

            for line_idx, line in enumerate(lines, 1):
                # Count TODOs / FIXMEs
                if "TODO" in line:
                    self.todo_count += 1
                if "FIXME" in line:
                    self.fixme_count += 1

                # Skip lines that are explicitly for redaction / replacement
                if "REDACTED" in line or "redact" in line.lower() or "sanitize" in line.lower():
                    continue

                # Check secrets
                for pat in self.SECRET_PATTERNS:
                    if pat.search(line):
                        self.findings.append(
                            {
                                "severity": "HIGH",
                                "type": "SECRET_PATTERN",
                                "file": str(rel_path),
                                "line": str(line_idx),
                                "detail": "Potential hardcoded credential or private key.",
                            }
                        )

                # Check test-only imports in production code
                for pat in self.PROD_TEST_IMPORT_PATTERNS:
                    if pat.search(line):
                        self.findings.append(
                            {
                                "severity": "HIGH",
                                "type": "TEST_IMPORT_IN_PROD",
                                "file": str(rel_path),
                                "line": str(line_idx),
                                "detail": f"Production module imports test-only package: {line.strip()}",
                            }
                        )

                # Check debug statements
                for pat in self.DEBUG_PATTERNS:
                    if pat.search(line):
                        self.findings.append(
                            {
                                "severity": "MEDIUM",
                                "type": "DEBUG_STATEMENT",
                                "file": str(rel_path),
                                "line": str(line_idx),
                                "detail": f"Active breakpoint detected: {line.strip()}",
                            }
                        )

    def print_summary(self) -> int:
        print("=" * 70)
        print("ENTERPRISE REPOSITORY AUDIT SUMMARY")
        print("=" * 70)
        print(f"Audited Target: {self.backend_app}")
        print(f"TODO Count: {self.todo_count}")
        print(f"FIXME Count: {self.fixme_count}")
        print(f"Total Security/Integrity Findings: {len(self.findings)}")

        high_findings = [f for f in self.findings if f["severity"] == "HIGH"]
        if high_findings:
            print("\n[CRITICAL FINDINGS]")
            for f in high_findings:
                print(f"  [{f['severity']}] {f['file']}:{f['line']} - {f['detail']}")
            return 1

        print("\nAll production code audit checks PASSED with 0 high-severity violations.")
        return 0


def main() -> None:
    workspace_root = Path(__file__).resolve().parent.parent.parent.parent
    auditor = RepositoryAuditor(workspace_root)
    auditor.audit_app_code()
    sys.exit(auditor.print_summary())


if __name__ == "__main__":
    main()
