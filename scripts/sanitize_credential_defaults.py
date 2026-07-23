#!/usr/bin/env python3
"""Strip community-* and hardcoded API-key defaults from hot legacy modules.

Env-only credentials after this pass. Does not invent replacements.
Rewrites only the listed hot files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOT = [
    "us_ipforce_deterministic_all.py",
    "court_ready_forensic_blueprint.py",
    "us_ipforce_abd_maximize.py",
    "us_ipforce_monolith.py",
    "us_ipforce_monolith_live.py",
]
OUT = ROOT / "docs" / "investigation" / "CUSTODY_SANITIZE_REPORT.json"

COMMUNITY_RE = re.compile(r'"community-[A-Za-z0-9_\-]+"')
COMMUNITY_RE_SQ = re.compile(r"'community-[A-Za-z0-9_\-]+'")
# os.getenv("X", "literal") / os.getenv('X', 'literal') with non-empty literal
GETENV_RE = re.compile(
    r"""(os\.getenv\(\s*(['"])([A-Z0-9_]+)\2\s*,\s*)(['"])([^'"]*)\4(\s*\))"""
)
# Nested: os.getenv("A", os.getenv("B", "secret"))
NESTED_TAIL_RE = re.compile(
    r"""(os\.getenv\(\s*(['"])([A-Z0-9_]+)\2\s*,\s*os\.getenv\(\s*(['"])([A-Z0-9_]+)\4\s*,\s*)(['"])([^'"]*)\6(\s*\)\s*\))"""
)


def _utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def sanitize_text(text: str) -> tuple[str, dict[str, int]]:
    counts = {
        "community_replaced": 0,
        "getenv_cleared": 0,
        "nested_getenv_cleared": 0,
        "default_key_cleared": 0,
    }

    def _comm(m: re.Match[str]) -> str:
        counts["community_replaced"] += 1
        q = m.group(0)[0]
        return f"{q}{q}"

    text2 = COMMUNITY_RE.sub(_comm, text)
    text2 = COMMUNITY_RE_SQ.sub(_comm, text2)

    def _nested(m: re.Match[str]) -> str:
        counts["nested_getenv_cleared"] += 1
        return f"{m.group(1)}{m.group(6)}{m.group(6)}{m.group(8)}"

    text2, n = NESTED_TAIL_RE.subn(_nested, text2)
    counts["nested_getenv_cleared"] = n

    def _getenv(m: re.Match[str]) -> str:
        key = m.group(3)
        default = m.group(5)
        # Keep benign empty/falsey short flags
        if default in {"", "0", "1", "true", "false", "True", "False"}:
            return m.group(0)
        counts["getenv_cleared"] += 1
        q = m.group(4)
        return f"{m.group(1)}{q}{q}{m.group(6)}"

    text2 = GETENV_RE.sub(_getenv, text2)

    # Explicit default-key remnants (single or double quotes)
    for pat in (
        r"""os\.getenv\(\s*['"]EVIDENCE_HMAC_KEY['"]\s*,\s*['"]default-key['"]\s*\)""",
    ):
        text2, n = re.subn(
            pat,
            'os.getenv("EVIDENCE_HMAC_KEY", "")',
            text2,
        )
        counts["default_key_cleared"] += n

    # Clear secret-like quoted values on credential assignment lines
    # e.g. "USPTO": "ymdzflszncdynzxoiktrcxabqpfbbz",
    line_re = re.compile(
        r'^(\s*["\'][A-Z][A-Z0-9_]*["\']\s*:\s*)(["\'])([^"\']*)\2(,?\s*)$'
    )
    out_lines: list[str] = []
    in_cred_dict = False
    cred_depth = 0
    for line in text2.splitlines(keepends=True):
        stripped = line.lstrip()
        if re.match(r'(DEFAULT_KEYS|EXPLICIT_KEYS|API_KEYS)\s*=\s*\{', stripped):
            in_cred_dict = True
            cred_depth = 0
        if in_cred_dict:
            cred_depth += line.count("{") - line.count("}")
            m = line_re.match(line.rstrip("\n"))
            if m:
                val = m.group(3)
                if val and not val.startswith("http") and (
                    len(val) >= 12 or val.startswith("community")
                ):
                    nl = "\n" if line.endswith("\n") else ""
                    line = f"{m.group(1)}{m.group(2)}{m.group(2)}{m.group(4)}{nl}"
                    counts["getenv_cleared"] += 1
            if cred_depth <= 0 and "{" not in stripped.split("=", 1)[-1][:3]:
                # closed dict
                if "}" in line:
                    in_cred_dict = False
            elif cred_depth <= 0 and "}" in line:
                in_cred_dict = False
        out_lines.append(line)
    text2 = "".join(out_lines)

    return text2, counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    report = {
        "generated_at": _utc(),
        "dry_run": args.dry_run,
        "files": [],
        "policy": "Credentials from environment only after sanitize. No secrets committed.",
    }
    for rel in HOT:
        path = ROOT / rel
        original = path.read_text(encoding="utf-8")
        updated, counts = sanitize_text(original)
        changed = updated != original
        entry = {
            "path": rel,
            "changed": changed,
            "counts": counts,
            "sha256_before": hashlib.sha256(original.encode()).hexdigest(),
            "sha256_after": hashlib.sha256(updated.encode()).hexdigest() if changed else None,
        }
        report["files"].append(entry)
        if changed and not args.dry_run:
            path.write_text(updated, encoding="utf-8")

    report["files_changed"] = sum(1 for f in report["files"] if f["changed"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"sanitize: changed={report['files_changed']}/{len(HOT)} "
        f"dry_run={args.dry_run} report={OUT.relative_to(ROOT)}"
    )
    for f in report["files"]:
        print(f"  {f['path']}: changed={f['changed']} {f['counts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
