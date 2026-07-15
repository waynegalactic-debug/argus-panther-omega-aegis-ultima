#!/usr/bin/env python3
"""Universally rebrand product nomenclature to IP FORCE across a repository tree.

Rewrites display/brand strings in text files. Preserves technical module import
paths (us_ipforce_*) and env var names unless they are purely decorative.
Hard-skips .git, binary assets, and very large corpus blobs (>8 MiB).
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    "us_ipforce_output",
    "us_ip_force_output",
    "output_artifacts",
}

TEXT_SUFFIXES = {
    ".py",
    ".md",
    ".txt",
    ".json",
    ".jsonl",
    ".html",
    ".htm",
    ".css",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".yml",
    ".yaml",
    ".toml",
    ".ini",
    ".cfg",
    ".csv",
    ".sql",
    ".sh",
    ".env.example",
    ".mdc",
    ".rst",
    ".xml",
}

# Ordered replacements: longer / more specific first.
REPLACEMENTS: list[tuple[str, str]] = [
    # Unicode / stylized
    ("IP FORCE", "IP FORCE"),
    ("IP FORCE", "IP FORCE"),
    ("IP FORCE", "IP FORCE"),
    # Full product phrases
    ("IP FORCE", "IP FORCE"),
    ("IP FORCE", "IP FORCE"),
    ("IP FORCE", "IP FORCE"),
    ("IP FORCE", "IP FORCE"),
    ("IP FORCE", "IP FORCE"),
    ("IP FORCE", "IP FORCE"),
    ("IP FORCE", "IP FORCE"),
    ("IP FORCE", "IP FORCE"),
    ("IP FORCETE", "IP FORCE"),
    ("IP FORCEte", "IP FORCE"),
    ("IP FORCE", "IP FORCE"),
    ("IP FORCE", "IP FORCE"),
    ("IP FORCE", "IP FORCE"),
    ("IP FORCE", "IP FORCE"),
    ("IP FORCE", "IP FORCE"),
    ("IP FORCE", "IP FORCE"),
    ("IP FORCE", "IP FORCE"),
    ("IP FORCE", "IP FORCE"),
    ("IP FORCE", "IP FORCE"),
    # Existing IP FORCE brand → IP FORCE
    ("IP FORCE", "IP FORCE"),
    ("IP FORCE", "IP FORCE"),
    ("IP FORCE", "IP FORCE"),
    ("IP FORCE", "IP FORCE"),
    ("IP FORCE", "IP FORCE"),
    ("IP FORCE", "IP FORCE"),
    ("IP FORCE", "IP FORCE"),
    ("IP_FORCE", "IP_FORCE"),
    ("IP-FORCE", "IP-FORCE"),
    ("IP-FORCE", "IP-FORCE"),
    # Compact tokens in prose / titles (not Python identifiers)
    ("IP FORCE", "IP FORCE"),
    ("IP FORCE", "IP FORCE"),
    ("IP FORCE Unified Monolith", "IP FORCE Unified Monolith"),
    ("IP FORCE Unified", "IP FORCE Unified"),
    ("IP FORCE brand", "IP FORCE brand"),
    ("IP FORCE only", "IP FORCE only"),
]

# Identifier / constant renames for brand-facing constants only.
IDENTIFIER_REPLACEMENTS: list[tuple[str, str]] = [
    ("SYSTEM_NAME = \"IP FORCE\"", 'SYSTEM_NAME = "IP FORCE"'),
    ("SYSTEM_NAME = 'IP FORCE'", "SYSTEM_NAME = 'IP FORCE'"),
    ('"name": "IP FORCE"', '"name": "IP FORCE"'),
    ('"short_name": "IP FORCE"', '"short_name": "IP FORCE"'),
    ('"system": "IP FORCE Unified Monolith"', '"system": "IP FORCE Unified Monolith"'),
    ("brand = \"IP FORCE\"", 'brand = "IP FORCE"'),
    ('"brand": "IP FORCE"', '"brand": "IP FORCE"'),
    ("**Brand:** IP FORCE", "**Brand:** IP FORCE"),
    ("Brand: IP FORCE", "Brand: IP FORCE"),
    ("canonical brand is **IP FORCE**", "canonical brand is **IP FORCE**"),
    ("Canonical brand is **IP FORCE**", "Canonical brand is **IP FORCE**"),
    ("Canonical brand is IP FORCE", "Canonical brand is IP FORCE"),
]


def is_text_file(path: Path) -> bool:
    if path.suffix.lower() in TEXT_SUFFIXES:
        return True
    if path.name in {"README", "LICENSE", "Makefile", "Dockerfile", "AGENTS.md"}:
        return True
    if path.name.endswith(".mdc"):
        return True
    return False


def should_skip(path: Path, root: Path) -> bool:
    try:
        rel_parts = path.relative_to(root).parts
    except ValueError:
        return True
    if any(part in SKIP_DIRS for part in rel_parts):
        return True
    if path.is_symlink():
        return True
    try:
        if path.stat().st_size > 8 * 1024 * 1024:
            return True
    except OSError:
        return True
    return False


def transform(text: str) -> str:
    for old, new in REPLACEMENTS:
        text = text.replace(old, new)
    for old, new in IDENTIFIER_REPLACEMENTS:
        text = text.replace(old, new)

    # Logger / module decorative names that still say OMEGA_AEGIS in prose strings.
    text = re.sub(
        r'logging\.getLogger\(\s*["\']OMEGA_AEGIS[^"\']*["\']\s*\)',
        'logging.getLogger("IP_FORCE")',
        text,
    )
    text = re.sub(
        r'logger\s*=\s*logging\.getLogger\(\s*["\']omega[^"\']*["\']\s*\)',
        'logger = logging.getLogger("ip_force")',
        text,
        flags=re.IGNORECASE,
    )
    return text


def process_repo(root: Path, *, dry_run: bool = False) -> dict:
    changed: list[str] = []
    scanned = 0
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if should_skip(path, root):
            continue
        if not is_text_file(path):
            continue
        scanned += 1
        try:
            original = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        updated = transform(original)
        if updated != original:
            changed.append(str(path.relative_to(root)))
            if not dry_run:
                path.write_text(updated, encoding="utf-8")
    return {"root": str(root), "scanned": scanned, "changed": len(changed), "files": changed}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("roots", nargs="+", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    for root in args.roots:
        result = process_repo(root.resolve(), dry_run=args.dry_run)
        print(
            f"{result['root']}: scanned={result['scanned']} changed={result['changed']}"
        )
        for rel in result["files"][:40]:
            print(f"  - {rel}")
        if result["changed"] > 40:
            print(f"  ... +{result['changed'] - 40} more")


if __name__ == "__main__":
    main()
