"""Map filename extensions to GitHub Linguist languages.

The MSR 2025 paper uses GitHub Linguist as the extension catalog and resolves
ambiguous extensions case-by-case. This module follows that approach: it builds
an extension map from Linguist, applies a small set of explicit overrides, and
skips remaining ambiguous extensions instead of silently guessing.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Dict, Tuple

import requests
import yaml

LINGUIST_URL = (
    "https://raw.githubusercontent.com/github-linguist/linguist/"
    "master/lib/linguist/languages.yml"
)

ALLOWED_TYPES = {"programming", "markup", "data"}

# The paper explicitly gives .pl -> Perl as an example of resolving ambiguity.
# .h is included here because it is central to the C/C++ history in this study.
AMBIGUOUS_EXTENSION_OVERRIDES = {
    "pl": "Perl",
    "h": "C",
}

# Fallback keeps the first-pass dashboard usable if GitHub Linguist cannot be
# downloaded. It is intentionally limited to the ten languages highlighted in
# the paper's Table II / Figures 6-10.
FALLBACK = {
    "json": ("JSON", "data"),
    "html": ("HTML", "markup"),
    "htm": ("HTML", "markup"),
    "xhtml": ("HTML", "markup"),
    "java": ("Java", "programming"),
    "js": ("JavaScript", "programming"),
    "mjs": ("JavaScript", "programming"),
    "cjs": ("JavaScript", "programming"),
    "xml": ("XML", "markup"),
    "xsd": ("XML", "markup"),
    "xsl": ("XML", "markup"),
    "xslt": ("XML", "markup"),
    "php": ("PHP", "programming"),
    "php3": ("PHP", "programming"),
    "php4": ("PHP", "programming"),
    "php5": ("PHP", "programming"),
    "phtml": ("PHP", "programming"),
    "py": ("Python", "programming"),
    "pyw": ("Python", "programming"),
    "pyi": ("Python", "programming"),
    "c": ("C", "programming"),
    "h": ("C", "programming"),
    "cs": ("C#", "programming"),
    "cpp": ("C++", "programming"),
    "cc": ("C++", "programming"),
    "cxx": ("C++", "programming"),
    "c++": ("C++", "programming"),
    "hpp": ("C++", "programming"),
    "hh": ("C++", "programming"),
    "hxx": ("C++", "programming"),
}


def _download_linguist(cache_path: Path) -> Path:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(LINGUIST_URL, timeout=30)
    response.raise_for_status()
    cache_path.write_bytes(response.content)
    return cache_path


def build_extension_language_map(
    cache_path: str | Path = "data/languages.yml",
) -> tuple[Dict[str, Tuple[str, str]], str, list[str]]:
    """Return extension -> (language, type), source label, ambiguous extensions.

    Remaining ambiguous extensions are excluded. This is preferable to silently
    assigning a language that the paper's authors may have resolved differently.
    """
    path = Path(cache_path)
    source = "GitHub Linguist"
    try:
        if not path.exists():
            _download_linguist(path)
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return dict(FALLBACK), "built-in top-10 fallback", []

    candidates: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for language, details in raw.items():
        language_type = details.get("type")
        if language_type not in ALLOWED_TYPES:
            continue
        for ext in details.get("extensions", []) or []:
            cleaned = str(ext).lower().lstrip(".")
            if cleaned:
                candidates[cleaned].append((language, language_type))

    mapping: Dict[str, Tuple[str, str]] = {}
    ambiguous: list[str] = []
    for ext, choices in candidates.items():
        # Deduplicate aliases that point to the same language/type.
        choices = list(dict.fromkeys(choices))
        if len(choices) == 1:
            mapping[ext] = choices[0]
            continue

        override = AMBIGUOUS_EXTENSION_OVERRIDES.get(ext)
        if override:
            selected = next((item for item in choices if item[0] == override), None)
            if selected:
                mapping[ext] = selected
                continue
        ambiguous.append(ext)

    return mapping, source, sorted(ambiguous)
