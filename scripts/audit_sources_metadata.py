# -*- coding: utf-8 -*-
"""
AUDIT 3 — Verify all 8 dataset metadata entries in DATA_SOURCES_CATALOG against actual local files.
"""
import sys
import os
import json
import hashlib
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from api.main import DATA_SOURCES_CATALOG
from app.config import (
    WHO_PDF, NAMASTE_XLSX, PLANT_TSV, THERAPEUTIC_TSV,
    FORMULATIONS_TSV, HI_PARQUET, KN_PARQUET, QA_CSV
)

def audit_sources():
    print("=" * 80)
    print("AUDITING DATA_SOURCES_CATALOG AGAINST LOCAL CORPUS AND METADATA")
    print("=" * 80)

    # Load expected SHA-256 hashes
    hash_map = {}
    with open("docs/raw_data_hashes.sha256", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                h, p = line.split()
                clean = p.strip("*")
                hash_map[Path(clean).name] = (h, clean)

    print(f"Total sources defined in catalog: {len(DATA_SOURCES_CATALOG)}")
    findings = []

    for src in DATA_SOURCES_CATALOG:
        sid = src["id"]
        title = src["title"]
        cat = src["category"]
        pub = src["publisher"]
        lic = src["license"]
        recs = src["records"]
        raw_file = src.get("raw_file")

        file_exists = False
        hash_verified = False
        actual_size = 0

        # Check file
        candidates = [Path(raw_file), Path("Data") / raw_file, Path("data") / raw_file] if raw_file else []
        matched_file = None
        for c in candidates:
            if c.exists():
                matched_file = c
                file_exists = True
                actual_size = c.stat().st_size
                break

        if matched_file and matched_file.name in hash_map:
            exp_hash, _ = hash_map[matched_file.name]
            with open(matched_file, "rb") as bf:
                cur_hash = hashlib.sha256(bf.read()).hexdigest()
            hash_verified = (cur_hash.lower() == exp_hash.lower())

        findings.append({
            "id": sid,
            "title": title,
            "category": cat,
            "publisher": pub,
            "license": lic,
            "claimed_records": recs,
            "raw_file": raw_file,
            "file_exists": file_exists,
            "hash_verified": hash_verified,
            "file_size_bytes": actual_size
        })

        print(f"[{'OK' if hash_verified else 'WARN'}] {sid}: {title}")
        print(f"       File: {raw_file} (Exists: {file_exists}, SHA256 Match: {hash_verified})")
        print(f"       Publisher: {pub} | Licence: {lic}")

    return findings

if __name__ == "__main__":
    audit_sources()
