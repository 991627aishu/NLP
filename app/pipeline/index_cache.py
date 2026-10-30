"""
AyurMitra — Index cache provenance (F9)
=======================================
Pickled scikit-learn objects are only safe to load with the library version
that wrote them. Every index we write now carries a ``_stamp`` (library
versions + corpus hash). On load, a missing or mismatching stamp means the
index is rebuilt from ``corpus_chunks.jsonl`` -- after the old file has been
copied to ``Data/processed/_v1_backup/`` (never overwritten once backed up).
"""
from __future__ import annotations

import hashlib
import logging
import shutil
import sys
from pathlib import Path
from typing import Any, Dict

from app.config import INDEX_BACKUP_DIR

log = logging.getLogger("ayurmitra.index")


def _ver(mod: str) -> str:
    try:
        m = __import__(mod)
        return getattr(m, "__version__", "unknown")
    except Exception:
        return "missing"


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(1 << 20), b""):
                h.update(block)
        return h.hexdigest()
    except OSError:
        return "missing"


def make_stamp(corpus_path: Path, extra: Dict[str, Any] | None = None) -> Dict[str, Any]:
    stamp = {
        "python": sys.version.split()[0],
        "sklearn": _ver("sklearn"),
        "numpy": _ver("numpy"),
        "corpus_sha256": file_sha256(corpus_path),
    }
    if extra:
        stamp.update(extra)
    return stamp


def stamp_matches(stored: Dict[str, Any] | None, corpus_path: Path, keys=("sklearn", "corpus_sha256")) -> bool:
    if not stored:
        return False
    current = make_stamp(corpus_path)
    return all(stored.get(k) == current.get(k) for k in keys)


def backup_once(path: Path) -> Path | None:
    """Copy an index file to _v1_backup/ the first time it is about to be replaced."""
    if not path.exists():
        return None
    INDEX_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    dest = INDEX_BACKUP_DIR / path.name
    if not dest.exists():
        shutil.copy2(path, dest)
        log.warning("Backed up %s -> %s before rebuild", path.name, dest)
    return dest
