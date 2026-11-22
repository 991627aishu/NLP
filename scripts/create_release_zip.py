import os
import sys
import zipfile
from pathlib import Path

def make_archive():
    root = Path(__file__).resolve().parent.parent
    out_dir = root.parent
    zip_path = out_dir / "AyurMitra_Final_Verified.zip"
    
    exclude_dirs = {".venv", ".git", "__pycache__", ".pytest_cache", ".system_generated"}
    exclude_exts = {".pyc", ".pyo"}
    
    print(f"Creating archive at: {zip_path}")
    count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in root.rglob("*"):
            # Check exclusions
            parts = p.relative_to(root).parts
            if any(part in exclude_dirs for part in parts):
                continue
            if p.suffix in exclude_exts:
                continue
            if p.is_file():
                arcname = str(Path("AyurMitra") / p.relative_to(root))
                zf.write(p, arcname)
                count += 1
                
    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"Successfully archived {count} files ({size_mb:.2f} MB) to {zip_path}")

if __name__ == "__main__":
    make_archive()

